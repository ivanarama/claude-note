"""
Prompts archive for claude-note.

Saves user prompts, plan, and summary to a dedicated Obsidian note.
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config
from .file_lock import file_lock

logger = logging.getLogger("claude-note")


def _validate_archive_path() -> bool:
    """Check if archive path is within vault root."""
    try:
        archive = get_prompts_archive_path().resolve()
        vault = config.VAULT_ROOT.resolve()
        return str(archive).startswith(str(vault))
    except Exception:
        return False


def is_prompts_archive_enabled() -> bool:
    """
    Check if prompts archive is enabled.

    Returns:
        True if prompts archive is enabled
    """
    return config.PROMPTS_ARCHIVE_ENABLED


def get_prompts_archive_path() -> Path:
    """
    Get the path to the prompts archive file.

    Returns:
        Path to the prompts archive file
    """
    return config.PROMPTS_ARCHIVE_PATH


def _ensure_archive_exists() -> bool:
    """
    Ensure the prompts archive file exists with proper frontmatter.

    Returns:
        True if file exists or was created successfully
    """
    archive_path = get_prompts_archive_path()

    if archive_path.exists():
        return True

    try:
        # Create parent directory if needed
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        # Create with frontmatter
        content = """---
tags: [log, claude-note, prompts-archive]
---

# Claude Code Prompts Archive

This note archives all user prompts from Claude Code sessions.

---

"""
        archive_path.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        logger.debug(f"Failed to create prompts archive: {e}")
        return False


def append_prompts_to_archive(
    session_id: str,
    cwd: str,
    user_prompts: list[str],
    timestamp: Optional[str] = None,
    plan: Optional[str] = None,
    summary: Optional[str] = None,
) -> bool:
    """
    Append prompts from a session to the archive.

    Args:
        session_id: Session identifier
        cwd: Working directory during session
        user_prompts: List of user prompts from the session
        timestamp: Optional timestamp (ISO format), defaults to now
        plan: Optional plan content (if include_plan_summary is enabled)
        summary: Optional summary content (if include_plan_summary is enabled)

    Returns:
        True if prompts were appended successfully
    """
    if not is_prompts_archive_enabled():
        return False

    if not _validate_archive_path():
        logger.warning(f"Prompts archive path is outside vault root, skipping: {get_prompts_archive_path()}")
        return False

    if not user_prompts and not plan and not summary:
        return False  # Nothing to archive

    if not _ensure_archive_exists():
        return False

    archive_path = get_prompts_archive_path()

    try:
        # Use current time if no timestamp provided
        if timestamp is None:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Format the entry
        lines = [
            f"### {timestamp} - {session_id[:16]}",
            f"**Working directory:** `{cwd}`",
            "",
        ]

        # Add plan if available and enabled
        include_plan = config.PROMPTS_ARCHIVE_INCLUDE_PLAN_SUMMARY
        if include_plan and plan:
            lines.append("**Plan:**")
            lines.append("")
            lines.append("```")
            lines.append(plan)
            lines.append("```")
            lines.append("")

        # Add user prompts
        if user_prompts:
            lines.append("**User Prompts:**")
            lines.append("")
            for i, prompt in enumerate(user_prompts, 1):
                lines.append(f"{i}. {prompt}")
            lines.append("")

        # Add summary if available and enabled
        if include_plan and summary:
            lines.append("**Summary:**")
            lines.append("")
            lines.append("```")
            lines.append(summary)
            lines.append("```")
            lines.append("")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Append to file with locking
        entry = "\n".join(lines)
        lock_file = archive_path.parent / f".{archive_path.name}.lock"

        with file_lock(lock_file, timeout=config.LOCK_TIMEOUT):
            with open(archive_path, "a", encoding="utf-8") as f:
                f.write(entry)

        return True

    except Exception as e:
        logger.debug(f"Failed to append to prompts archive: {e}")
        return False


def get_archive_stats() -> dict:
    """
    Get statistics about the prompts archive.

    Returns:
        Dictionary with stats:
        - exists: bool
        - path: str
        - enabled: bool
        - entry_count: int
        - total_prompts: int
        - last_updated: str or None
        - recent_entries: list of dicts
    """
    archive_path = get_prompts_archive_path()

    stats = {
        "exists": archive_path.exists(),
        "path": str(archive_path),
        "enabled": is_prompts_archive_enabled(),
        "entry_count": 0,
        "total_prompts": 0,
        "last_updated": None,
        "recent_entries": [],
    }

    if not archive_path.exists():
        return stats

    try:
        content = archive_path.read_text(encoding="utf-8")

        # Parse entries (look for ### timestamps)
        lines = content.split("\n")
        entries = []
        current_entry = None
        prompt_count = 0

        for line in lines:
            if line.startswith("### ") and " - " in line:
                # New entry
                if current_entry:
                    entries.append(current_entry)
                current_entry = {
                    "timestamp": line[4:].strip(),
                    "prompts": [],
                }
            elif current_entry and re.match(r"^\d+\.\s", line.strip()):
                # Count prompts (any numbered list item)
                current_entry["prompts"].append(line.strip())
                prompt_count += 1

        if current_entry:
            entries.append(current_entry)

        stats["entry_count"] = len(entries)
        stats["total_prompts"] = prompt_count

        if entries:
            stats["last_updated"] = entries[-1]["timestamp"].split(" - ")[0] if " - " in entries[-1]["timestamp"] else entries[-1]["timestamp"]
            stats["recent_entries"] = [
                {"timestamp": e["timestamp"], "prompt_count": len(e["prompts"])}
                for e in entries[-5:]  # Last 5 entries
            ]

    except Exception:
        pass  # Return default stats on error

    return stats
