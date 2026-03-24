"""
Synthesizer for claude-note.

Calls headless Claude to extract knowledge from transcripts.
"""

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config
from . import knowledge_pack
from . import transcript_reader
from . import vault_indexer
from . import qmd_search
from . import localization


def _get_lang() -> str:
    """Get current language code from config."""
    return config.LANGUAGE_CODE


def _format_user_prompts(prompts: list[str], max_total: int = 8000) -> str:
    """Format user prompts for synthesis, with truncation."""
    if not prompts:
        return localization.get_label("no_user_prompts", _get_lang())

    formatted = []
    total_len = 0

    for i, prompt in enumerate(prompts, 1):
        # Truncate individual prompts
        if len(prompt) > config.SYNTH_MAX_PROMPT_LEN:
            prompt = prompt[:config.SYNTH_MAX_PROMPT_LEN] + "..."

        entry = f"{i}. {prompt}"
        if total_len + len(entry) > max_total:
            formatted.append(f"... and {len(prompts) - i + 1} more prompts")
            break

        formatted.append(entry)
        total_len += len(entry)

    return "\n".join(formatted)


def _format_tool_summary(tool_uses: list, max_entries: int = None) -> str:
    """Format tool uses as summary."""
    if max_entries is None:
        max_entries = config.SYNTH_MAX_TOOL_ENTRIES
    lang = _get_lang()
    if not tool_uses:
        return localization.get_label("no_tool_uses", lang)

    # Count by tool type
    counts = {}
    for tool in tool_uses:
        name = tool.name if hasattr(tool, "name") else tool.get("name", "unknown")
        counts[name] = counts.get(name, 0) + 1

    lines = [localization.get_label("tool_usage_summary", lang)]
    for name, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  - {name}: {count} uses")

    # Add notable tool uses (first few of each type)
    lines.append(f"\n{localization.get_label('notable_operations', lang)}")
    seen_types = {}  # dict to count how many of each type we've shown
    entries = 0

    for tool in tool_uses:
        if entries >= max_entries:
            break

        name = tool.name if hasattr(tool, "name") else tool.get("name", "unknown")
        tool_input = tool.input if hasattr(tool, "input") else tool.get("input", {})

        # Skip if we've shown enough of this type
        if seen_types.get(name, 0) >= config.SYNTH_MAX_TOOL_EXAMPLES_PER_TYPE:
            continue

        # Format based on tool type
        if name == "Read":
            path = tool_input.get("file_path", "")
            if path:
                lines.append(f"  - Read: {Path(path).name}")
                entries += 1
        elif name == "Write":
            path = tool_input.get("file_path", "")
            if path:
                lines.append(f"  - Write: {Path(path).name}")
                entries += 1
        elif name == "Edit":
            path = tool_input.get("file_path", "")
            if path:
                lines.append(f"  - Edit: {Path(path).name}")
                entries += 1
        elif name == "Bash":
            cmd = tool_input.get("command", "")
            if cmd:
                if len(cmd) > 60:
                    cmd = cmd[:60] + "..."
                lines.append(f"  - Bash: {cmd}")
                entries += 1

        seen_types[name] = seen_types.get(name, 0) + 1

    return "\n".join(lines)


def _format_files_list(files: list[str], max_files: int = None) -> str:
    """Format list of files touched."""
    if max_files is None:
        max_files = config.SYNTH_MAX_FILES_SHOWN
    lang = _get_lang()
    if not files:
        return localization.get_label("no_files_touched", lang)

    if len(files) <= max_files:
        return "\n".join(f"  - {f}" for f in files)

    shown = files[:max_files]
    return "\n".join(f"  - {f}" for f in shown) + f"\n  ... and {len(files) - max_files} more"


def _format_vault_summary(vault_index: vault_indexer.VaultIndex) -> str:
    """Format vault index summary for context."""
    lang = _get_lang()
    if not vault_index or not vault_index.notes:
        return localization.get_label("no_vault_notes", lang)

    lines = [localization.get_label("vault_has_notes", lang).format(count=len(vault_index.notes))]

    # Get all tags
    all_tags = set()
    for note in vault_index.notes.values():
        all_tags.update(note.tags)

    if all_tags:
        lines.append(f"{localization.get_label('available_tags', lang)} {', '.join(sorted(all_tags))}")

    # List ALL note names so LLM knows what exists (critical for routing)
    note_names = sorted([Path(n.path).stem for n in vault_index.notes.values()])
    lines.append(f"{localization.get_label('existing_notes', lang)} {', '.join(note_names)}")

    return "\n".join(lines)


def _get_related_note_snippets(transcript: transcript_reader.TranscriptContent, vault_index: vault_indexer.VaultIndex, max_notes: int = 5) -> str:
    """
    Find notes semantically related to session content using qmd vector search.

    This provides the synthesis LLM with actual content context, not just note names.

    Args:
        transcript: TranscriptContent object
        vault_index: VaultIndex object (for fallback)
        max_notes: Maximum number of related notes to include

    Returns:
        Formatted string with related note snippets, or fallback message
    """
    lang = _get_lang()
    # Check if qmd synthesis is enabled
    if not config.QMD_SYNTH_ENABLED:
        return localization.get_label("semantic_search_disabled", lang)

    try:
        if not qmd_search.is_qmd_available():
            return localization.get_label("qmd_not_available", lang)

        # Build query from user prompts and file names
        query_parts = []

        # Add first few user prompts (most relevant context)
        for prompt in transcript.user_prompts[:3]:
            # Take first 200 chars of each prompt
            truncated = prompt[:200].strip()
            if truncated:
                query_parts.append(truncated)

        # Add notable file names (without extensions)
        for f in transcript.files_touched[:5]:
            stem = Path(f).stem
            # Skip common/generic names
            if stem not in ["index", "main", "test", "config", "utils", "__init__"]:
                query_parts.append(stem.replace("-", " ").replace("_", " "))

        if not query_parts:
            return localization.get_label("no_query_context", lang)

        query = " ".join(query_parts)
        min_score = config.QMD_MIN_SCORE

        # Search for related notes
        results = qmd_search.search_vector(query, limit=max_notes, min_score=min_score)

        if not results:
            return localization.get_label("no_related_notes", lang)

        # Format results with snippets
        lines = [localization.get_label("found_related_notes", lang).format(count=len(results))]

        for r in results:
            note_name = Path(r.path).stem
            lines.append(f"\n### [[{note_name}]] (score: {r.score:.2f})")

            # Include snippet if available
            if r.snippet:
                snippet = r.snippet.strip()
                if len(snippet) > 300:
                    snippet = snippet[:300] + "..."
                lines.append(snippet)
            elif r.title:
                lines.append(f"Title: {r.title}")

        return "\n".join(lines)

    except Exception as e:
        # Silent fallback - don't break synthesis
        return f"(Semantic search unavailable: {type(e).__name__})"


def build_synthesis_prompt(
    transcript: transcript_reader.TranscriptContent,
    vault_index: vault_indexer.VaultIndex,
    cwd: str = "",
    date: str = "",
) -> str:
    """
    Build the prompt for synthesis.

    Args:
        transcript: TranscriptContent object
        vault_index: VaultIndex object
        cwd: Working directory
        date: Session date

    Returns:
        Complete prompt string
    """
    lang = _get_lang()
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    user_prompts = _format_user_prompts(transcript.user_prompts)
    tool_summary = _format_tool_summary(transcript.tool_uses)
    files_list = _format_files_list(transcript.files_touched)
    vault_summary = _format_vault_summary(vault_index)
    schema = knowledge_pack.get_schema_description(lang)

    # Get semantically related notes for better context
    max_related = config.QMD_SYNTH_MAX_NOTES
    related_context = _get_related_note_snippets(transcript, vault_index, max_notes=max_related)

    # Format errors
    errors = "\n".join(transcript.errors) if transcript.errors else localization.get_label("no_errors", lang)

    # Use localized prompt builder
    return localization.format_synthesis_prompt(
        lang=lang,
        cwd=cwd or localization.get_label("unknown", lang),
        date=date,
        session_id=transcript.session_id,
        user_prompts=user_prompts,
        tool_summary=tool_summary,
        files_list=files_list,
        errors=errors,
        related_context=related_context,
        vault_summary=vault_summary,
        schema=schema,
    )


def parse_knowledge_pack(output: str) -> knowledge_pack.KnowledgePack:
    """
    Parse Claude output into KnowledgePack.

    Handles various output formats Claude might produce.
    """
    # Try to extract JSON from output
    output = output.strip()

    # Remove markdown code blocks if present
    if output.startswith("```"):
        # Find the end of the opening fence
        first_newline = output.find("\n")
        if first_newline > 0:
            output = output[first_newline + 1:]
        # Remove closing fence
        if output.endswith("```"):
            output = output[:-3].strip()

    # Try to find JSON object
    json_match = re.search(r'\{[\s\S]*\}', output)
    if json_match:
        output = json_match.group()

    try:
        data = json.loads(output)
        return knowledge_pack.KnowledgePack.from_dict(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\nOutput was: {output[:500]}")


def synthesize_session(
    transcript: transcript_reader.TranscriptContent,
    vault_index: vault_indexer.VaultIndex,
    cwd: str = "",
    model: str = None,
    timeout: int = 120,
) -> Optional[knowledge_pack.KnowledgePack]:
    """
    Synthesize a session into a KnowledgePack.

    Args:
        transcript: TranscriptContent object
        vault_index: VaultIndex object
        cwd: Working directory
        model: Claude model to use (defaults to config)
        timeout: Timeout in seconds

    Returns:
        KnowledgePack or None on failure
    """
    if model is None:
        model = config.SYNTH_MODEL

    now = datetime.utcnow()
    date = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    prompt = build_synthesis_prompt(transcript, vault_index, cwd=cwd, date=date)

    # Call claude CLI in print mode
    # Set marker so enqueue.py skips events from synthesis sessions
    env = os.environ.copy()
    env["CLAUDE_NOTE_SYNTHESIS"] = "1"

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", model],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")

        pack = parse_knowledge_pack(result.stdout)

        # Set the time (Claude doesn't return this, we set it ourselves)
        if not pack.time:
            pack.time = time_str

        # Validate
        warnings = knowledge_pack.validate_knowledge_pack(pack)
        if warnings:
            # Log warnings but don't fail
            pass

        return pack

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Synthesis timed out after {timeout}s")
    except FileNotFoundError:
        raise RuntimeError("Claude CLI not found. Is it installed?")


def synthesize_from_state(state, vault_index: vault_indexer.VaultIndex = None, model: str = None) -> Optional[knowledge_pack.KnowledgePack]:
    """
    Convenience function to synthesize from SessionState.

    Args:
        state: SessionState object
        vault_index: Optional VaultIndex (will be loaded if not provided)
        model: Optional model override

    Returns:
        KnowledgePack or None
    """
    # Read transcript
    transcript = transcript_reader.read_transcript_from_state(state)

    # Get vault index
    if vault_index is None:
        vault_index = vault_indexer.get_index()

    return synthesize_session(
        transcript,
        vault_index,
        cwd=state.cwd,
        model=model,
    )


def resynthesize_session(session_id: str, model: str = None) -> Optional[knowledge_pack.KnowledgePack]:
    """
    Re-run synthesis for a previously completed session.

    Args:
        session_id: Session ID to resynthesize
        model: Optional model override (e.g., "claude-opus-4-20250514")

    Returns:
        KnowledgePack or None
    """
    from . import session_tracker

    # Load session state
    state = session_tracker.load_session_state(session_id)
    if not state:
        raise ValueError(f"Session not found: {session_id}")

    if not state.transcript_path:
        raise ValueError(f"Session has no transcript: {session_id}")

    # Read transcript
    transcript = transcript_reader.read_transcript(state.transcript_path)

    # Get fresh vault index
    vault_index = vault_indexer.build_index()

    return synthesize_session(
        transcript,
        vault_index,
        cwd=state.cwd,
        model=model,
    )
