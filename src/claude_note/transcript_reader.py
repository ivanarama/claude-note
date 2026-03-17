"""
Transcript reader for claude-note synthesizer.

Parses Claude Code transcript JSONL and extracts content for synthesis.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union


@dataclass
class ToolUse:
    """A single tool invocation."""
    name: str
    input: dict
    output_summary: Optional[str] = None
    success: bool = True


@dataclass
class TranscriptContent:
    """Extracted content from a transcript."""
    session_id: str
    user_prompts: list[str] = field(default_factory=list)
    assistant_texts: list[str] = field(default_factory=list)
    tool_uses: list[ToolUse] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    thinking_snippets: list[str] = field(default_factory=list)
    plan: Optional[str] = None  # Plan content from plan mode
    summary: Optional[str] = None  # Summary of session/plan

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "user_prompts": self.user_prompts,
            "assistant_texts": self.assistant_texts,
            "tool_uses": [
                {
                    "name": t.name,
                    "input": t.input,
                    "output_summary": t.output_summary,
                    "success": t.success,
                }
                for t in self.tool_uses
            ],
            "files_touched": self.files_touched,
            "errors": self.errors,
            "thinking_snippets": self.thinking_snippets,
            "plan": self.plan,
            "summary": self.summary,
        }


def _extract_file_paths(tool_name: str, tool_input: dict) -> list[str]:
    """Extract file paths from tool input."""
    paths = []

    # Direct file_path parameter
    if "file_path" in tool_input:
        paths.append(tool_input["file_path"])

    # Bash commands that might touch files
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        # Simple heuristic: extract paths from common commands
        # This is intentionally conservative
        pass

    # Glob/Grep paths
    if tool_name in ("Glob", "Grep"):
        if "path" in tool_input:
            paths.append(tool_input["path"])

    return paths


def _summarize_tool_output(tool_name: str, output: str, max_len: int = 200) -> str:
    """Create a brief summary of tool output."""
    if not output:
        return ""

    # For file reads, just note the length
    if tool_name == "Read":
        lines = output.count("\n") + 1
        return f"({lines} lines)"

    # For search tools, count matches
    if tool_name in ("Glob", "Grep"):
        matches = output.count("\n") + 1 if output.strip() else 0
        return f"({matches} matches)"

    # For bash, truncate output
    if tool_name == "Bash":
        if len(output) > max_len:
            return output[:max_len] + "..."
        return output

    # Default: truncate
    if len(output) > max_len:
        return output[:max_len] + "..."
    return output


def read_transcript(transcript_path: Union[str, Path]) -> TranscriptContent:
    """
    Read and parse a transcript JSONL file.

    Args:
        transcript_path: Path to the transcript JSONL file

    Returns:
        TranscriptContent with extracted data
    """
    transcript_path = Path(transcript_path)

    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    # Extract session_id from path (last component before .jsonl)
    session_id = transcript_path.stem

    content = TranscriptContent(session_id=session_id)
    files_seen = set()
    current_tool_uses = {}  # Track tool uses by id for matching with results
    plan_sections = []  # Collect potential plan sections
    summary_sections = []  # Collect potential summary sections

    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")

            # Handle user messages
            if entry_type == "user":
                message = entry.get("message", {})
                msg_content = message.get("content", "")
                if isinstance(msg_content, str) and msg_content.strip():
                    content.user_prompts.append(msg_content.strip())
                elif isinstance(msg_content, list):
                    # Handle content blocks
                    for block in msg_content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text = block.get("text", "")
                                if text.strip():
                                    content.user_prompts.append(text.strip())

            # Handle assistant messages
            elif entry_type == "assistant":
                message = entry.get("message", {})
                msg_content = message.get("content", [])

                if isinstance(msg_content, list):
                    for block in msg_content:
                        if not isinstance(block, dict):
                            continue

                        block_type = block.get("type")

                        # Text response
                        if block_type == "text":
                            text = block.get("text", "")
                            if text.strip():
                                content.assistant_texts.append(text.strip())

                        # Tool use
                        elif block_type == "tool_use":
                            tool_name = block.get("name", "unknown")
                            tool_input = block.get("input", {})
                            tool_id = block.get("id", "")

                            tool_use = ToolUse(
                                name=tool_name,
                                input=tool_input,
                            )
                            content.tool_uses.append(tool_use)

                            # Track for later result matching
                            if tool_id:
                                current_tool_uses[tool_id] = tool_use

                            # Extract file paths
                            for path in _extract_file_paths(tool_name, tool_input):
                                if path and path not in files_seen:
                                    content.files_touched.append(path)
                                    files_seen.add(path)

                        # Thinking blocks - may contain plan
                        elif block_type == "thinking":
                            thinking = block.get("thinking", "")
                            if thinking.strip():
                                # Only keep first 500 chars of each thinking block
                                snippet = thinking.strip()[:500]
                                content.thinking_snippets.append(snippet)

                                # Check if thinking contains plan-related content
                                thinking_lower = thinking.lower()
                                if any(keyword in thinking_lower for keyword in ["plan:", "## plan", "implementation plan", "steps:"]):
                                    plan_sections.append(thinking.strip())

            # Handle tool results (progress messages)
            elif entry_type == "progress":
                # Progress messages can contain tool results
                tool_use_id = entry.get("tool_use_id")
                result = entry.get("result", {})

                if tool_use_id and tool_use_id in current_tool_uses:
                    tool_use = current_tool_uses[tool_use_id]

                    # Check for errors
                    if result.get("is_error"):
                        error_msg = result.get("content", "")
                        if error_msg:
                            content.errors.append(f"{tool_use.name}: {error_msg[:200]}")
                            tool_use.success = False

                    # Summarize output
                    output = result.get("content", "")
                    if output:
                        tool_use.output_summary = _summarize_tool_output(
                            tool_use.name, output
                        )

            # Handle tool result messages
            elif entry_type == "tool_result":
                tool_use_id = entry.get("tool_use_id")
                content_data = entry.get("content", "")
                is_error = entry.get("is_error", False)

                if tool_use_id and tool_use_id in current_tool_uses:
                    tool_use = current_tool_uses[tool_use_id]

                    if is_error:
                        error_msg = content_data if isinstance(content_data, str) else str(content_data)
                        content.errors.append(f"{tool_use.name}: {error_msg[:200]}")
                        tool_use.success = False

                    if isinstance(content_data, str):
                        tool_use.output_summary = _summarize_tool_output(
                            tool_use.name, content_data
                        )

            # Check for special events that might contain plan/summary
            elif entry_type in ("enter_plan_mode", "exit_plan_mode"):
                # These events might have additional data
                if "data" in entry:
                    data = entry.get("data", {})
                    if isinstance(data, dict):
                        if entry_type == "enter_plan_mode":
                            plan_content = data.get("plan") or data.get("content")
                            if plan_content:
                                plan_sections.append(str(plan_content))
                        elif entry_type == "exit_plan_mode":
                            summary_content = data.get("summary") or data.get("content")
                            if summary_content:
                                summary_sections.append(str(summary_content))

    # Extract plan from collected sections (join if multiple)
    if plan_sections:
        # Take the longest plan section as it's likely the most complete
        content.plan = max(plan_sections, key=len)

    # Extract summary from collected sections or from last assistant message
    if summary_sections:
        content.summary = max(summary_sections, key=len)
    elif content.assistant_texts:
        # Try to extract summary from the last assistant text
        last_text = content.assistant_texts[-1]
        # Look for summary patterns
        for marker in ["## Summary", "**Summary**", "Summary:", "Итого:", "## Итог"]:
            if marker in last_text:
                parts = last_text.split(marker)
                if len(parts) > 1:
                    content.summary = parts[-1].strip()
                    break

    return content


def read_transcript_from_state(state) -> TranscriptContent:
    """
    Read transcript for a session from its state.

    Args:
        state: SessionState object

    Returns:
        TranscriptContent with extracted data
    """
    if not state.transcript_path:
        raise ValueError("Session state has no transcript_path")

    return read_transcript(state.transcript_path)


def get_transcript_summary(content: TranscriptContent) -> dict:
    """
    Get a summary of transcript content for synthesis prompt.

    Returns a dict with counts and key snippets.
    """
    return {
        "num_user_prompts": len(content.user_prompts),
        "num_assistant_texts": len(content.assistant_texts),
        "num_tool_uses": len(content.tool_uses),
        "num_files_touched": len(content.files_touched),
        "num_errors": len(content.errors),
        "tool_breakdown": _count_tool_types(content.tool_uses),
    }


def _count_tool_types(tool_uses: list[ToolUse]) -> dict[str, int]:
    """Count tool uses by type."""
    counts = {}
    for tool in tool_uses:
        counts[tool.name] = counts.get(tool.name, 0) + 1
    return counts
