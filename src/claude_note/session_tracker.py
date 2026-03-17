"""Session state tracking with locks and debouncing."""

import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from . import config
from . import models
from .file_lock import file_lock


def get_state_file(session_id: str) -> Path:
    """Get the state file path for a session."""
    return config.STATE_DIR / f"{session_id}.json"


def get_lock_file(session_id: str) -> Path:
    """Get the lock file path for a session."""
    return config.STATE_DIR / f"{session_id}.lock"


@contextmanager
def session_lock(session_id: str, timeout: float = None) -> Iterator[bool]:
    """
    Context manager for session locking.

    Yields True if lock acquired.
    """
    if timeout is None:
        timeout = config.LOCK_TIMEOUT

    lock_file = get_lock_file(session_id)

    with file_lock(lock_file, timeout=timeout):
        yield True


def load_session_state(session_id: str) -> Optional[models.SessionState]:
    """Load session state from file."""
    state_file = get_state_file(session_id)
    if not state_file.exists():
        return None

    try:
        return models.SessionState.from_json(state_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_session_state(state: models.SessionState) -> None:
    """Save session state to file."""
    state_file = get_state_file(state.session_id)
    state_file.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write via temp file
    temp_file = state_file.with_suffix(".tmp")
    temp_file.write_text(state.to_json(), encoding="utf-8")
    # Windows: use os.replace() to overwrite existing file
    os.replace(temp_file, state_file)


def is_recursive_event(event: models.QueuedEvent) -> bool:
    """Check if event is from claude-note itself (recursion prevention)."""
    import os

    # Normalize paths for comparison
    cwd_normalized = os.path.normpath(event.cwd).lower()
    vault_normalized = os.path.normpath(str(config.VAULT_ROOT)).lower()

    # Check if cwd is inside vault internals (claude-note working directory)
    if cwd_normalized.startswith(vault_normalized) and ".claude-note" in cwd_normalized:
        return True

    # Check tool inputs in data
    data = event.data
    tool_input = data.get("tool_input", {})

    # Check file paths - only filter if inside vault internals
    file_path = tool_input.get("file_path", "")
    if file_path:
        fp_normalized = os.path.normpath(file_path).lower()
        if fp_normalized.startswith(vault_normalized) and ".claude-note" in fp_normalized:
            return True

    # Check bash commands for synthesis-specific patterns
    command = tool_input.get("command", "")
    synthesis_indicators = ["extracting durable knowledge", "claude-note inbox"]
    if any(indicator in command.lower() for indicator in synthesis_indicators):
        return True

    # Check grep/glob patterns - only for synthesis-related queries
    pattern = tool_input.get("pattern", "")
    if any(marker in pattern.lower() for marker in config.RECURSION_MARKERS):
        # Additional check: only filter if pattern looks like a synthesis query
        if any(indicator in pattern.lower() for indicator in synthesis_indicators):
            return True

    # Check path parameter - only filter if inside vault internals
    path = tool_input.get("path", "")
    if path:
        path_normalized = os.path.normpath(path).lower()
        if path_normalized.startswith(vault_normalized) and ".claude-note" in path_normalized:
            return True

    # Check user prompt for synthesis markers (more specific)
    prompt = data.get("prompt", "")
    if "extracting durable knowledge" in prompt.lower():
        return True

    return False


def extract_event_summary(event: models.QueuedEvent) -> models.EventSummary:
    """Extract a human-readable summary from an event."""
    ts = event.ts
    event_type = event.event
    data = event.data

    if event_type == "SessionStart":
        description = "Session started"
    elif event_type == "SessionEnd":
        description = "Session ended"
    elif event_type == "Stop":
        description = "Session stopped"
    elif event_type == "PreCompact":
        description = "Context compaction"
    elif event_type == "UserPromptSubmit":
        prompt = data.get("prompt", "")
        if len(prompt) > 80:
            prompt = prompt[:77] + "..."
        description = f'User prompt: "{prompt}"'
    elif event_type in ("PostToolUse", "PostToolUseFailure"):
        tool_name = data.get("tool_name", "unknown")
        tool_input = data.get("tool_input", {})

        # Build tool-specific description
        if tool_name == "Read":
            file_path = tool_input.get("file_path", "")
            description = f"**Read** `{Path(file_path).name}`"
        elif tool_name == "Write":
            file_path = tool_input.get("file_path", "")
            description = f"**Write** `{Path(file_path).name}`"
        elif tool_name == "Edit":
            file_path = tool_input.get("file_path", "")
            description = f"**Edit** `{Path(file_path).name}`"
        elif tool_name == "Bash":
            command = tool_input.get("command", "")
            if len(command) > 60:
                command = command[:57] + "..."
            description = f"**Bash** `{command}`"
        elif tool_name == "Grep":
            pattern = tool_input.get("pattern", "")
            description = f"**Grep** `{pattern}`"
        elif tool_name == "Glob":
            pattern = tool_input.get("pattern", "")
            description = f"**Glob** `{pattern}`"
        elif tool_name == "Task":
            desc = tool_input.get("description", "")
            description = f"**Task** {desc}"
        else:
            description = f"**{tool_name}**"

        if event_type == "PostToolUseFailure":
            description += " (failed)"
    else:
        description = event_type

    return models.EventSummary(ts=ts, event=event_type, description=description)


def update_session_from_events(session_id: str, events: list) -> models.SessionState:
    """
    Update or create session state from events.

    Filters out recursive events and deduplicates by event_id.
    """
    state = load_session_state(session_id)

    if state is None:
        if not events:
            raise ValueError("Cannot create session state with no events")
        first_event = events[0]
        state = models.SessionState(
            session_id=session_id,
            first_event_ts=first_event.ts,
            last_event_ts=first_event.ts,
            cwd=first_event.cwd,
            transcript_path=first_event.transcript_path,
        )

    processed_ids = set(state.processed_event_ids)

    for event in events:
        # Skip already processed
        if event.event_id in processed_ids:
            continue

        # Skip recursive events
        if is_recursive_event(event):
            continue

        # Update state
        state.last_event_ts = event.ts
        state.processed_event_ids.append(event.event_id)
        processed_ids.add(event.event_id)

        # Update cwd/transcript if newer
        if event.cwd:
            state.cwd = event.cwd
        if event.transcript_path:
            state.transcript_path = event.transcript_path

        # Add event summary
        summary = extract_event_summary(event)
        state.events.append(summary.to_dict())

    return state


def should_flush_immediately(events: list) -> bool:
    """Check if session should be flushed immediately (Stop/SessionEnd)."""
    immediate_events = {"Stop", "SessionEnd"}
    return any(e.event in immediate_events for e in events)


def get_sessions_ready_for_write(debounce_seconds: float = None) -> list[str]:
    """Get session IDs that are ready for note writing."""
    if debounce_seconds is None:
        debounce_seconds = config.DEBOUNCE_SECONDS

    ready = []

    if not config.STATE_DIR.exists():
        return ready

    for state_file in config.STATE_DIR.glob("*.json"):
        session_id = state_file.stem
        state = load_session_state(session_id)
        if state and state.should_write(debounce_seconds):
            ready.append(session_id)

    return ready


def mark_session_written(session_id: str) -> None:
    """Mark session as having been written."""
    state = load_session_state(session_id)
    if state:
        state.last_write_ts = datetime.utcnow().isoformat() + "Z"
        save_session_state(state)


def is_session_written(state: models.SessionState) -> bool:
    """Check if session has already been written after its last event."""
    if not state.last_write_ts or not state.last_event_ts:
        return False
    last_write = datetime.fromisoformat(state.last_write_ts.rstrip("Z"))
    last_event = datetime.fromisoformat(state.last_event_ts.rstrip("Z"))
    return last_write >= last_event
