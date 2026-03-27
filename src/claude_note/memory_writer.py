"""
Memory writer for Claude Code auto-memory integration.

After synthesis, curates KnowledgePack entries into concise memory entries
and updates ~/.claude/projects/{project}/memory/MEMORY.md so future
Claude Code sessions start with accumulated project knowledge.
"""

import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from . import config
from . import knowledge_pack
from .file_lock import file_lock


# =============================================================================
# Project Dir Resolution
# =============================================================================

def _resolve_project_dir(transcript_path: str) -> Optional[Path]:
    """
    Derive the Claude Code project directory from a transcript path.

    Transcripts live at ~/.claude/projects/{project}/{session}.jsonl.
    Walk up parents until parent.parent.name == "projects".

    Returns:
        Path to the project dir, or None if not resolvable.
    """
    if not transcript_path:
        return None

    path = Path(transcript_path).resolve()

    # Walk up to find the projects/ parent
    for parent in path.parents:
        if parent.parent.name == "projects":
            return parent

    return None


# =============================================================================
# MEMORY.md Parsing / Writing
# =============================================================================

MEMORY_HEADER = """# Project Knowledge

Auto-maintained by claude-note. Edit freely — manual edits are preserved.
"""

SECTIONS = ["Decisions", "Patterns", "Gotchas", "How-tos"]

_SECTION_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)
_ENTRY_PATTERN = re.compile(r"^- .+$", re.MULTILINE)


def _parse_memory(content: str) -> dict[str, list[str]]:
    """
    Parse MEMORY.md into sections with their entries.

    Returns:
        Dict mapping section name to list of entry lines (including "- " prefix).
    """
    sections: dict[str, list[str]] = {s: [] for s in SECTIONS}
    current_section = None

    for line in content.split("\n"):
        stripped = line.strip()

        # Check for section header
        match = _SECTION_PATTERN.match(stripped)
        if match:
            name = match.group(1)
            if name in sections:
                current_section = name
            else:
                current_section = None
            continue

        # Collect entries under a known section
        if current_section and stripped.startswith("- "):
            sections[current_section].append(stripped)

    return sections


def _render_memory(sections: dict[str, list[str]]) -> str:
    """Render sections back into MEMORY.md content."""
    lines = [MEMORY_HEADER]

    for section_name in SECTIONS:
        lines.append(f"## {section_name}")
        entries = sections.get(section_name, [])
        for entry in entries:
            lines.append(entry)
        lines.append("")  # blank line after section

    return "\n".join(lines)


def _bootstrap_memory(memory_path: Path) -> str:
    """Create initial MEMORY.md with section headers and no entries."""
    content = _render_memory({s: [] for s in SECTIONS})
    return content


# =============================================================================
# Deduplication
# =============================================================================

def _extract_entry_text(entry_line: str) -> str:
    """Extract the text portion from an entry line, stripping date suffix and bullet."""
    text = entry_line
    if text.startswith("- "):
        text = text[2:]
    # Remove trailing date like (2026-02-05)
    text = re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)\s*$", "", text)
    return text.strip().lower()


def _compute_similarity(text1: str, text2: str) -> float:
    """Compute Jaccard similarity between two texts (word-level)."""
    words1 = set(text1.split())
    words2 = set(text2.split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union) if union else 0.0


def _is_duplicate(new_text: str, existing_entries: list[str], threshold: float) -> bool:
    """Check if new_text is similar enough to any existing entry to be a duplicate."""
    new_normalized = _extract_entry_text(new_text)
    for existing in existing_entries:
        existing_normalized = _extract_entry_text(existing)
        if _compute_similarity(new_normalized, existing_normalized) >= threshold:
            return True
    return False


# =============================================================================
# Staleness Pruning
# =============================================================================

def _extract_date(entry_line: str) -> Optional[datetime]:
    """Extract date from entry's trailing date suffix."""
    match = re.search(r"\((\d{4}-\d{2}-\d{2})\)\s*$", entry_line)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None


def _prune_stale_entries(
    sections: dict[str, list[str]], max_lines: int, stale_days: int
) -> dict[str, list[str]]:
    """
    Prune entries to stay under max_lines budget.

    Strategy: remove oldest entries first (by date suffix).
    Only prunes entries older than stale_days.
    """
    total_lines = sum(len(entries) for entries in sections.values())
    # Account for header + section headers + blank lines
    overhead = 5 + len(SECTIONS) * 2  # header lines + "## Section" + blank per section
    total_lines += overhead

    if total_lines <= max_lines:
        return sections

    cutoff = datetime.utcnow() - timedelta(days=stale_days)

    # Collect all entries with dates, sorted oldest first
    dated_entries: list[tuple[datetime, str, str]] = []  # (date, section, entry)
    for section_name, entries in sections.items():
        for entry in entries:
            date = _extract_date(entry)
            if date and date < cutoff:
                dated_entries.append((date, section_name, entry))

    dated_entries.sort(key=lambda x: x[0])  # oldest first

    # Remove entries until under budget
    for date, section_name, entry in dated_entries:
        if total_lines <= max_lines:
            break
        sections[section_name].remove(entry)
        total_lines -= 1

    return sections


# =============================================================================
# File Locking
# =============================================================================

def _memory_lock(memory_path: Path, timeout: float = 30.0):
    """
    Context manager for locking MEMORY.md writes.

    Uses cross-platform file_lock from file_lock module.
    """
    lock_file = memory_path.parent / f".memory-{memory_path.name}.lock"
    return file_lock(lock_file, timeout=timeout)


# =============================================================================
# Claude Curation Call
# =============================================================================

CATEGORY_TO_SECTION = {
    "decision": "Decisions",
    "pattern": "Patterns",
    "gotcha": "Gotchas",
    "howto": "How-tos",
}


def _build_curation_prompt(
    pack: knowledge_pack.KnowledgePack,
    current_memory: str,
) -> str:
    """Build prompt for Claude to curate memory entries from a KnowledgePack."""

    # Format relevant KnowledgePack fields
    pack_parts = []

    if pack.decisions:
        pack_parts.append("Decisions made:")
        for d in pack.decisions:
            pack_parts.append(f"  - {d.decision}")
            if d.rationale:
                pack_parts.append(f"    Rationale: {d.rationale}")

    if pack.concepts:
        pack_parts.append("Concepts learned:")
        for c in pack.concepts:
            pack_parts.append(f"  - {c.name}: {c.summary}")

    if pack.howtos:
        pack_parts.append("How-tos:")
        for h in pack.howtos:
            pack_parts.append(f"  - {h.title}")
            for step in h.steps[:3]:
                pack_parts.append(f"    {step}")
            if h.gotchas:
                for g in h.gotchas:
                    pack_parts.append(f"    Gotcha: {g}")

    if pack.highlights:
        pack_parts.append("Session highlights:")
        for h in pack.highlights:
            pack_parts.append(f"  - {h}")

    pack_content = "\n".join(pack_parts)

    prompt = f"""You are curating a project knowledge memory file for Claude Code.

## Current MEMORY.md
{current_memory if current_memory.strip() else "(empty - first time setup)"}

## New Session Knowledge
Title: {pack.title}
Date: {pack.date}

{pack_content}

## Your Task

Decide which pieces of knowledge are worth adding to the project memory. Memory entries should be:
- **Concise**: Single bullet, max ~120 characters
- **Reusable**: Useful for future sessions (not session-specific details)
- **Actionable**: Patterns, decisions, gotchas, how-tos that help avoid mistakes or speed up work
- **Non-redundant**: Don't duplicate what's already in the memory file

Also identify any existing entries that are now outdated or superseded by this session's findings.

The memory file has a strict 200-line budget. Only add entries that are genuinely valuable.

Categories:
- "decision": Architectural or design choices made
- "pattern": Recurring patterns or best practices for this codebase
- "gotcha": Things that don't work as expected, pitfalls to avoid
- "howto": Short commands or procedures to accomplish tasks

Return ONLY valid JSON:
{{
    "entries_to_add": [
        {{"category": "decision|pattern|gotcha|howto", "text": "concise one-liner"}}
    ],
    "entries_to_remove": ["exact full text of superseded entry line, including '- ' prefix"],
    "skip_reason": null
}}

Set skip_reason to a string explaining why if this session has nothing worth memorizing (trivial session, no durable knowledge). In that case, entries_to_add and entries_to_remove should be empty arrays.

Return ONLY the JSON object, no markdown fences, no explanation."""

    return prompt


def _parse_curation_response(output: str) -> dict:
    """Parse Claude's curation response into structured operations."""
    output = output.strip()

    # Remove markdown code blocks if present
    if output.startswith("```"):
        first_newline = output.find("\n")
        if first_newline > 0:
            output = output[first_newline + 1:]
        if output.endswith("```"):
            output = output[:-3].strip()

    # Find JSON object
    json_match = re.search(r"\{[\s\S]*\}", output)
    if json_match:
        output = json_match.group()

    data = json.loads(output)

    # Validate structure
    result = {
        "entries_to_add": [],
        "entries_to_remove": [],
        "skip_reason": data.get("skip_reason"),
    }

    for entry in data.get("entries_to_add", []):
        if isinstance(entry, dict) and "category" in entry and "text" in entry:
            if entry["category"] in CATEGORY_TO_SECTION:
                result["entries_to_add"].append(entry)

    for removal in data.get("entries_to_remove", []):
        if isinstance(removal, str):
            result["entries_to_remove"].append(removal)

    return result


def _call_claude_for_curation(
    pack: knowledge_pack.KnowledgePack,
    current_memory: str,
    model: str,
    timeout: int,
) -> dict:
    """Call Claude CLI to curate memory entries."""
    prompt = _build_curation_prompt(pack, current_memory)

    env = os.environ.copy()
    env["CLAUDE_CODE_HOOKS_ENABLED"] = "false"

    result = subprocess.run(
        ["claude", "-p", prompt, "--model", model],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {result.stderr}")

    return _parse_curation_response(result.stdout)


# =============================================================================
# Main Entry Point
# =============================================================================

def update_memory(
    pack: knowledge_pack.KnowledgePack,
    cwd: str,
    transcript_path: str,
    logger,
) -> dict:
    """
    Curate and write memory entries from a KnowledgePack.

    Args:
        pack: KnowledgePack with synthesis results
        cwd: Working directory of the session
        transcript_path: Path to session transcript (used to find project dir)
        logger: Logger instance

    Returns:
        Dict with results:
            - memory_updated: bool
            - entries_added: int
            - entries_removed: int
            - skip_reason: str or None
            - memory_path: str or None
    """
    result = {
        "memory_updated": False,
        "entries_added": 0,
        "entries_removed": 0,
        "skip_reason": None,
        "memory_path": None,
    }

    # Skip if pack is empty
    if pack.is_empty():
        result["skip_reason"] = "empty knowledge pack"
        return result

    # Resolve project directory from transcript path
    project_dir = _resolve_project_dir(transcript_path)
    if project_dir is None:
        result["skip_reason"] = "could not resolve project directory"
        logger.debug(f"Memory: cannot resolve project dir from {transcript_path}")
        return result

    # Check that the project dir exists (don't create it)
    if not project_dir.exists():
        result["skip_reason"] = "project directory does not exist"
        logger.debug(f"Memory: project dir does not exist: {project_dir}")
        return result

    memory_dir = project_dir / "memory"
    memory_path = memory_dir / "MEMORY.md"
    result["memory_path"] = str(memory_path)

    # Read current memory (or bootstrap)
    if memory_path.exists():
        current_memory = memory_path.read_text(encoding="utf-8")
    else:
        current_memory = _bootstrap_memory(memory_path)

    # Determine model
    model = config.MEMORY_MODEL or config.SYNTH_MODEL

    # Call Claude for curation
    logger.debug(f"Memory: calling Claude for curation ({model})")
    curation = _call_claude_for_curation(
        pack, current_memory, model, config.MEMORY_TIMEOUT
    )

    # Check if skipped
    if curation.get("skip_reason"):
        result["skip_reason"] = curation["skip_reason"]
        logger.debug(f"Memory: skipped - {curation['skip_reason']}")
        return result

    entries_to_add = curation.get("entries_to_add", [])
    entries_to_remove = curation.get("entries_to_remove", [])

    if not entries_to_add and not entries_to_remove:
        result["skip_reason"] = "no changes needed"
        return result

    # Parse current memory into sections
    sections = _parse_memory(current_memory)

    # Apply removals (exact match on full entry line)
    removed = 0
    for removal_text in entries_to_remove:
        removal_text = removal_text.strip()
        for section_name, entries in sections.items():
            if removal_text in entries:
                entries.remove(removal_text)
                removed += 1
                break

    # Apply additions with dedup
    today = datetime.utcnow().strftime("%Y-%m-%d")
    added = 0
    all_existing = [e for entries in sections.values() for e in entries]

    for entry in entries_to_add:
        category = entry["category"]
        text = entry["text"].strip()

        # Truncate to ~120 chars
        if len(text) > 120:
            text = text[:117] + "..."

        entry_line = f"- {text} ({today})"
        section_name = CATEGORY_TO_SECTION.get(category)

        if not section_name:
            continue

        # Dedup check
        if _is_duplicate(entry_line, all_existing, config.MEMORY_DEDUP_THRESHOLD):
            logger.debug(f"Memory: skipping duplicate entry: {text[:50]}")
            continue

        sections[section_name].append(entry_line)
        all_existing.append(entry_line)
        added += 1

    if added == 0 and removed == 0:
        result["skip_reason"] = "all entries were duplicates"
        return result

    # Prune stale entries if over budget
    sections = _prune_stale_entries(
        sections, config.MEMORY_MAX_LINES, config.MEMORY_STALE_DAYS
    )

    # Render and write
    new_content = _render_memory(sections)

    # Ensure memory dir exists
    memory_dir.mkdir(parents=True, exist_ok=True)

    # Atomic write with lock
    with _memory_lock(memory_path):
        temp_path = memory_path.with_suffix(".tmp")
        temp_path.write_text(new_content, encoding="utf-8")
        temp_path.rename(memory_path)

    result["memory_updated"] = True
    result["entries_added"] = added
    result["entries_removed"] = removed

    logger.info(
        f"Memory: updated {memory_path} (+{added}/-{removed} entries)"
    )

    return result
