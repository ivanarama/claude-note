#!/usr/bin/env python3
"""
Background worker daemon for claude-note.

Polls the queue and processes sessions when debounce expires.
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime

from . import config
from . import models
from . import queue_manager
from . import session_tracker
from . import note_writer
from . import open_questions
from . import synthesizer
from . import note_router
from . import vault_indexer
from . import version_checker
from . import prompts_archive
from . import transcript_reader
from . import memory_writer


# Global flag for graceful shutdown
_shutdown = False


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the worker."""
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    log_file = config.LOGS_DIR / f"worker-{datetime.utcnow().strftime('%Y-%m-%d')}.log"

    level = logging.DEBUG if verbose else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler() if verbose else logging.NullHandler(),
        ],
    )

    return logging.getLogger("claude-note")


def handle_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown
    _shutdown = True


def update_session_summary(state: models.SessionState, pack, logger: logging.Logger) -> bool:
    """
    Update session note's Summary section with synthesis results.

    Args:
        state: SessionState object
        pack: KnowledgePack with synthesis results
        logger: Logger instance

    Returns:
        True if summary was updated
    """
    import re

    try:
        note_path = note_writer.get_note_path(state)
        if not note_path.exists():
            return False

        content = note_path.read_text(encoding="utf-8")

        # Build summary content
        summary_lines = [f"**{pack.title}**", ""]

        # Add model info if available
        if pack.model_used:
            summary_lines.append(f"*Synthesized with: {pack.model_used}*")
            summary_lines.append("")

        if pack.highlights:
            summary_lines.append("Key outcomes:")
            for h in pack.highlights:
                summary_lines.append(f"- {h}")
            summary_lines.append("")

        if pack.concepts:
            summary_lines.append(f"Concepts: {', '.join(c.name for c in pack.concepts[:5])}")
        if pack.decisions:
            summary_lines.append(f"Decisions: {len(pack.decisions)}")
        if pack.open_questions:
            summary_lines.append(f"Open questions: {len(pack.open_questions)}")

        summary_text = "\n".join(summary_lines)

        # Replace placeholder in Summary section
        # Look for the placeholder text
        placeholder = "(Updated on Stop/SessionEnd with session highlights)"

        if placeholder in content:
            new_content = content.replace(placeholder, summary_text)
        else:
            # Try to find and replace the Summary section content
            pattern = r"(## Summary\n\n).*?(\n\n## )"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                new_content = content[:match.start()] + match.group(1) + summary_text + match.group(2) + content[match.end():]
            else:
                # Couldn't find Summary section
                return False

        # Write atomically
        temp_path = note_path.with_suffix(".tmp")
        temp_path.write_text(new_content, encoding="utf-8", errors="surrogatepass")
        # Windows: use os.replace() to overwrite existing file
        os.replace(temp_path, note_path)

        model_info = f" ({pack.model_used})" if pack.model_used else ""
        logger.info(f"Updated session summary: {pack.title}{model_info}")
        return True

    except Exception as e:
        logger.error(f"Failed to update session summary: {e}")
        return False


def run_synthesis(state: models.SessionState, logger: logging.Logger) -> bool:
    """
    Run synthesis for a session.

    Returns True if synthesis succeeded.
    """
    # Skip if mode is just logging
    if config.SYNTH_MODE == "log":
        return False

    # Skip if no transcript
    if not state.transcript_path:
        logger.debug(f"Session {state.session_id[:8]}: no transcript, skipping synthesis")
        return False

    try:
        # Get vault index
        vault_index = vault_indexer.get_index()

        # Run synthesis
        logger.info(f"Synthesizing session {state.session_id[:8]}...")
        pack = synthesizer.synthesize_from_state(state, vault_index)

        if pack and pack.model_used:
            logger.info(f"Session {state.session_id[:8]}: synthesized with {pack.model_used}")

        if pack is None or pack.is_empty():
            logger.info(f"Session {state.session_id[:8]}: no knowledge extracted")
            return False

        # Update session note summary with synthesis results
        update_session_summary(state, pack, logger)

        # Save model used to state
        if pack.model_used:
            state.synth_model = pack.model_used
            session_tracker.save_session_state(state)

        # Apply note ops
        results = note_router.apply_note_ops(pack, mode=config.SYNTH_MODE)

        # Log results
        if results["inbox_updated"]:
            logger.info(f"Updated inbox with {len(pack.concepts)} concepts, {len(pack.decisions)} decisions")
        if results["notes_created"]:
            logger.info(f"Created notes: {', '.join(results['notes_created'])}")
        if results["notes_updated"]:
            logger.info(f"Updated notes: {', '.join(results['notes_updated'])}")
        if results["errors"]:
            for err in results["errors"]:
                logger.warning(f"Synthesis error: {err}")

        # Archive user prompts (if enabled)
        if prompts_archive.is_prompts_archive_enabled():
            try:
                transcript = transcript_reader.read_transcript_from_state(state)
                if prompts_archive.append_prompts_to_archive(
                    session_id=state.session_id,
                    cwd=state.cwd,
                    user_prompts=transcript.user_prompts,
                    plan=transcript.plan,
                    summary=transcript.summary,
                ):
                    archived_count = len(transcript.user_prompts)
                    if transcript.plan:
                        archived_count += 1  # Count plan as an item
                    if transcript.summary:
                        archived_count += 1  # Count summary as an item
                    logger.debug(f"Archived {archived_count} items (prompts, plan, summary)")
            except Exception as e:
                # Don't fail synthesis if prompts archive fails
                logger.warning(f"Failed to archive prompts: {e}")

        # Update auto-memory (if enabled)
        if config.MEMORY_ENABLED:
            try:
                result = memory_writer.update_memory(
                    pack=pack,
                    cwd=state.cwd,
                    transcript_path=state.transcript_path or "",
                    logger=logger,
                )
                if result["memory_updated"]:
                    logger.info(
                        f"Memory: +{result['entries_added']}/-{result['entries_removed']} entries"
                    )
            except Exception as e:
                # Don't fail synthesis if memory update fails
                logger.warning(f"Failed to update memory: {e}")

        return True

    except Exception as e:
        logger.error(f"Synthesis failed for session {state.session_id[:8]}: {e}")
        return False


def process_session(session_id: str, events: list, logger: logging.Logger) -> tuple[bool, bool]:
    """
    Process a single session.

    Returns:
        Tuple of (written, should_remove):
        - written: True if note was written
        - should_remove: True if events can be removed from queue
    """
    with session_tracker.session_lock(session_id) as acquired:
        if not acquired:
            logger.debug(f"Could not acquire lock for session {session_id[:8]}")
            return False, False  # Don't remove, may need retry

        try:
            # Update session state from events
            state = session_tracker.update_session_from_events(session_id, events)

            # Skip synthesis/empty sessions (no user prompts)
            has_user_prompt = any(
                e.get("event") == "UserPromptSubmit"
                for e in state.events
            )
            if not has_user_prompt:
                logger.debug(f"Session {session_id[:8]}: no user prompt, skipping")
                return False, True  # Remove, no processing needed

            # Check if we should write now
            immediate = session_tracker.should_flush_immediately(events)
            debounce_ok = state.should_write(config.DEBOUNCE_SECONDS)

            # Skip if already written after last event (even for immediate events)
            already_written = session_tracker.is_session_written(state)
            if already_written:
                logger.debug(f"Session {session_id[:8]}: already written, skipping")
                return False, True  # Remove, already processed

            if not immediate and not debounce_ok:
                # Save state but don't write note yet
                session_tracker.save_session_state(state)
                logger.debug(f"Session {session_id[:8]}: debounce not ready")
                return False, False  # Don't remove, needs more time

            # Write the note
            note_path = note_writer.update_session_note(state)
            logger.info(f"Wrote note: {note_path.name}")

            # Promote questions on Stop/SessionEnd
            if immediate:
                count = open_questions.promote_session_questions(state)
                if count > 0:
                    logger.info(f"Promoted {count} questions to open-questions.md")

                # Run synthesis on Stop/SessionEnd (if enabled)
                run_synthesis(state, logger)

            # Mark as written (update state object directly, then save once)
            state.last_write_ts = datetime.utcnow().isoformat() + "Z"
            session_tracker.save_session_state(state)

            return True, True  # Written, can remove

        except Exception as e:
            logger.error(f"Error processing session {session_id[:8]}: {e}")
            return False, False  # Don't remove on error, may retry


def poll_once(logger: logging.Logger) -> int:
    """
    Process all pending sessions once.

    Returns number of notes written.
    """
    # Group events by session and track all event IDs
    sessions: dict[str, list] = {}
    session_event_ids: dict[str, set] = {}

    for event in queue_manager.read_all_events():
        if event.session_id not in sessions:
            sessions[event.session_id] = []
            session_event_ids[event.session_id] = set()
        sessions[event.session_id].append(event)
        session_event_ids[event.session_id].add(event.event_id)

    notes_written = 0
    events_to_remove: set = set()

    for session_id, events in sessions.items():
        written, should_remove = process_session(session_id, events, logger)
        if written:
            notes_written += 1
        # Always remove events if they don't need further processing
        if should_remove:
            events_to_remove.update(session_event_ids[session_id])

    # Remove processed events from queue
    if events_to_remove:
        removed = queue_manager.remove_event_ids(events_to_remove)
        if removed > 0:
            logger.debug(f"Removed {removed} processed events from queue")

    return notes_written


def run_worker(foreground: bool = False, verbose: bool = False) -> int:
    """
    Run the worker daemon.

    Args:
        foreground: If True, log to stdout as well
        verbose: If True, enable debug logging
    """
    logger = setup_logging(verbose=verbose or foreground)
    logger.info("Worker starting")

    # Check for updates (non-blocking)
    try:
        version_checker.check_for_update(logger)
    except Exception:
        pass  # Never let version check break worker

    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Main poll loop
    while not _shutdown:
        try:
            notes_written = poll_once(logger)
            if notes_written > 0:
                logger.debug(f"Poll cycle: wrote {notes_written} notes")

            # Clean up old queue files periodically (once per poll)
            queue_manager.cleanup_old_queue_files(keep_days=7)

        except Exception as e:
            logger.error(f"Error in poll cycle: {e}")

        # Sleep until next poll
        time.sleep(config.POLL_INTERVAL)

    logger.info("Worker shutting down")
    return 0


def main() -> int:
    """Main entry point for worker command."""
    parser = argparse.ArgumentParser(description="Claude Note background worker")
    parser.add_argument(
        "--foreground", "-f", action="store_true", help="Run in foreground with output"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    args = parser.parse_args()

    return run_worker(foreground=args.foreground, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())


# Allow running as module: python -m claude_note.worker
def _run_as_module() -> None:
    """Entry point when run as python -m claude_note.worker."""
    import argparse
    parser = argparse.ArgumentParser(description="Claude Note background worker")
    parser.add_argument("--foreground", "-f", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    sys.exit(run_worker(foreground=args.foreground, verbose=args.verbose))


if __name__ == "__mp_main__":  # Set by multiprocessing when spawning
    _run_as_module()
