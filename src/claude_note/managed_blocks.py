"""
Managed blocks for safe note updates.

Allows claude-note to update specific regions of notes without
touching user-written content.

Block format:
<!-- claude-note:{block_id}:start -->
Content here...
<!-- claude-note:{block_id}:end -->
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Optional, Union

from . import config
from .file_lock import file_lock


# Block markers
BLOCK_START_PATTERN = re.compile(r"<!--\s*claude-note:([^:]+):start\s*-->")
BLOCK_END_PATTERN = re.compile(r"<!--\s*claude-note:([^:]+):end\s*-->")


def _make_start_marker(block_id: str) -> str:
    """Generate start marker for a block."""
    return f"<!-- claude-note:{block_id}:start -->"


def _make_end_marker(block_id: str) -> str:
    """Generate end marker for a block."""
    return f"<!-- claude-note:{block_id}:end -->"


def _note_lock(note_path: Path, timeout: float = 30.0):
    """
    Context manager for per-note locking.

    Uses file-based locking to prevent concurrent modifications.
    """
    lock_dir = config.STATE_DIR / "note_locks"
    lock_dir.mkdir(parents=True, exist_ok=True)

    # Use hash of path for lock file name
    path_hash = hashlib.sha256(str(note_path).encode()).hexdigest()[:16]
    lock_file = lock_dir / f"{path_hash}.lock"

    return file_lock(lock_file, timeout=timeout)


def _atomic_write(path: Path, content: str) -> None:
    """Write file atomically using temp file + rename."""
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    # Windows: use os.replace() to overwrite existing file
    os.replace(temp_path, path)


def read_managed_block(note_path: Union[Path, str], block_id: str) -> Optional[str]:
    """
    Read the content of a managed block.

    Args:
        note_path: Path to the note file
        block_id: ID of the block to read

    Returns:
        Block content (without markers), or None if not found
    """
    note_path = Path(note_path)
    if not note_path.exists():
        return None

    content = note_path.read_text(encoding="utf-8")

    start_marker = _make_start_marker(block_id)
    end_marker = _make_end_marker(block_id)

    start_idx = content.find(start_marker)
    if start_idx == -1:
        return None

    end_idx = content.find(end_marker, start_idx)
    if end_idx == -1:
        return None

    # Extract content between markers
    block_start = start_idx + len(start_marker)
    block_content = content[block_start:end_idx].strip()

    return block_content


def write_managed_block(
    note_path: Union[Path, str],
    block_id: str,
    content: str,
    create_if_missing: bool = False,
) -> bool:
    """
    Write content to a managed block.

    If the block exists, replaces its content.
    If create_if_missing is True and the note exists but block doesn't,
    appends the block at the end.

    Args:
        note_path: Path to the note file
        block_id: ID of the block
        content: Content to write (without markers)
        create_if_missing: If True, create block if it doesn't exist

    Returns:
        True if block was written, False if note doesn't exist
    """
    note_path = Path(note_path)
    if not note_path.exists():
        return False

    with _note_lock(note_path):
        file_content = note_path.read_text(encoding="utf-8")

        start_marker = _make_start_marker(block_id)
        end_marker = _make_end_marker(block_id)

        start_idx = file_content.find(start_marker)

        if start_idx != -1:
            # Block exists - replace content
            end_idx = file_content.find(end_marker, start_idx)
            if end_idx == -1:
                # Malformed block - remove old start and append new block
                file_content = file_content.replace(start_marker, "")
                start_idx = -1
            else:
                # Replace block content
                new_block = f"{start_marker}\n{content}\n{end_marker}"
                file_content = (
                    file_content[:start_idx]
                    + new_block
                    + file_content[end_idx + len(end_marker):]
                )
                _atomic_write(note_path, file_content)
                return True

        if start_idx == -1:
            # Block doesn't exist
            if not create_if_missing:
                return False

            # Append block at end
            new_block = f"\n{start_marker}\n{content}\n{end_marker}\n"
            file_content = file_content.rstrip() + new_block
            _atomic_write(note_path, file_content)
            return True

    return False


def delete_managed_block(note_path: Union[Path, str], block_id: str) -> bool:
    """
    Delete a managed block from a note.

    Args:
        note_path: Path to the note file
        block_id: ID of the block to delete

    Returns:
        True if block was deleted, False if not found
    """
    note_path = Path(note_path)
    if not note_path.exists():
        return False

    with _note_lock(note_path):
        file_content = note_path.read_text(encoding="utf-8")

        start_marker = _make_start_marker(block_id)
        end_marker = _make_end_marker(block_id)

        start_idx = file_content.find(start_marker)
        if start_idx == -1:
            return False

        end_idx = file_content.find(end_marker, start_idx)
        if end_idx == -1:
            return False

        # Remove the entire block including markers
        block_end = end_idx + len(end_marker)

        # Also remove trailing newline if present
        if block_end < len(file_content) and file_content[block_end] == "\n":
            block_end += 1

        # Also remove leading newline if present
        if start_idx > 0 and file_content[start_idx - 1] == "\n":
            start_idx -= 1

        file_content = file_content[:start_idx] + file_content[block_end:]
        _atomic_write(note_path, file_content)
        return True


def list_managed_blocks(note_path: Union[Path, str]) -> list[str]:
    """
    List all managed block IDs in a note.

    Args:
        note_path: Path to the note file

    Returns:
        List of block IDs
    """
    note_path = Path(note_path)
    if not note_path.exists():
        return []

    content = note_path.read_text(encoding="utf-8")
    return BLOCK_START_PATTERN.findall(content)


def append_to_section(
    note_path: Union[Path, str],
    section_heading: str,
    content: str,
    create_section: bool = True,
) -> bool:
    """
    Append content to a section in a note.

    Args:
        note_path: Path to the note file
        section_heading: Section heading (e.g., "## Synthesized")
        content: Content to append
        create_section: If True, create section if it doesn't exist

    Returns:
        True if content was appended
    """
    note_path = Path(note_path)
    if not note_path.exists():
        return False

    with _note_lock(note_path):
        file_content = note_path.read_text(encoding="utf-8")
        lines = file_content.split("\n")

        # Find section
        section_idx = None
        for i, line in enumerate(lines):
            if line.strip() == section_heading:
                section_idx = i
                break

        if section_idx is None:
            if not create_section:
                return False
            # Add section at end
            lines.append("")
            lines.append(section_heading)
            lines.append("")
            lines.append(content)
        else:
            # Find end of section (next heading or EOF)
            insert_idx = section_idx + 1
            while insert_idx < len(lines):
                line = lines[insert_idx]
                if line.startswith("#") and not line.startswith("###"):
                    # Found next section of same or higher level
                    break
                insert_idx += 1

            # Insert content before next section
            lines.insert(insert_idx, "")
            lines.insert(insert_idx + 1, content)

        _atomic_write(note_path, "\n".join(lines))
        return True


def find_section_content(note_path: Union[Path, str], section_heading: str) -> Optional[str]:
    """
    Find and return the content of a section.

    Args:
        note_path: Path to the note file
        section_heading: Section heading (e.g., "## Summary")

    Returns:
        Section content, or None if section not found
    """
    note_path = Path(note_path)
    if not note_path.exists():
        return None

    content = note_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Find section
    section_idx = None
    for i, line in enumerate(lines):
        if line.strip() == section_heading:
            section_idx = i
            break

    if section_idx is None:
        return None

    # Find end of section
    end_idx = section_idx + 1
    heading_level = section_heading.count("#")

    while end_idx < len(lines):
        line = lines[end_idx]
        # Check if this is a heading of same or higher level
        if line.startswith("#"):
            line_level = len(line) - len(line.lstrip("#"))
            if line_level <= heading_level:
                break
        end_idx += 1

    # Extract section content
    section_lines = lines[section_idx + 1:end_idx]
    return "\n".join(section_lines).strip()
