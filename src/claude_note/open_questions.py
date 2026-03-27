"""Open question detection and promotion to open-questions.md.

Includes LLM-based quality filtering to prevent conversation fragments
and debugging chatter from polluting the open questions file.
"""

import json
import os
import subprocess
from datetime import datetime

from . import config
from . import note_writer


# =============================================================================
# LLM-Based Quality Filter
# =============================================================================

QUALITY_FILTER_PROMPT = """You are evaluating whether a question extracted from a Claude Code conversation is worth tracking as an "open research question" for a technical project.

A question is worth tracking if it:
1. Represents a genuine knowledge gap about a system, data pipeline, ML model, or technical architecture
2. Would be valuable to answer for the project's long-term success
3. Is specific enough to be actionable
4. Is NOT already answered by the question itself

A question should be REJECTED if it:
1. Is a conversation fragment or debugging chatter ("is it running?", "what happened?")
2. Is a status check ("how's the gif going?", "whats up?")
3. Is too vague to be actionable ("can you help?")
4. Is a command/request disguised as a question ("can you run clustering?")
5. Is truncated/incomplete (ends with "...")
6. Is a greeting or small talk ("whats up?", "hello?")
7. Is asking Claude to do something rather than seeking knowledge

Evaluate this question:
"{question}"

Respond with EXACTLY one of these JSON objects (no other text):
{{"action": "KEEP", "reason": "<brief reason>"}}
{{"action": "DELETE", "reason": "<brief reason>"}}
"""


def filter_questions_with_llm(questions: list) -> list:
    """
    Use Claude CLI to filter out junk questions, keeping only legitimate research questions.

    Uses the Claude CLI (via subprocess) which leverages your Pro/Max subscription
    instead of API credits.

    Returns list of questions that passed the quality filter.
    """
    if not questions:
        return []

    filtered = []

    # Use Haiku 4.5 for fast, cheap filtering (via CLI = uses subscription)
    model = "claude-haiku-4-5-20251001"

    # Disable hooks to prevent recursion
    env = os.environ.copy()
    env["CLAUDE_CODE_HOOKS_ENABLED"] = "false"
    env["CLAUDE_NOTE_SYNTHESIS"] = "1"

    for question in questions:
        # Skip obviously short/junk questions without LLM call
        if len(question.strip()) < 15:
            continue
        if question.strip().endswith("..."):
            continue

        prompt = QUALITY_FILTER_PROMPT.format(question=question)

        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", model],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,  # Short timeout for simple classification
            )

            if result.returncode != 0:
                # CLI failed, skip this question
                continue

            result_text = result.stdout.strip()

            # Parse the JSON response
            try:
                parsed = json.loads(result_text)
                if parsed.get("action") == "KEEP":
                    filtered.append(question)
            except json.JSONDecodeError:
                # If we can't parse the response, be conservative and skip
                pass

        except subprocess.TimeoutExpired:
            # Timeout, skip this question
            pass
        except FileNotFoundError:
            # Claude CLI not installed, fall back to keeping all questions
            return questions
        except Exception:
            # On any error, skip this question (fail safe)
            pass

    return filtered


def extract_questions_from_events(state) -> list:
    """
    Extract potential open questions from session events.

    Looks for user prompts that contain question patterns.
    """
    questions = []

    for event_dict in state.events:
        # Only look at user prompts for questions
        if event_dict.get("event") != "UserPromptSubmit":
            continue

        description = event_dict.get("description", "")

        # Extract the actual prompt text
        if description.startswith('User prompt: "'):
            prompt = description[14:]  # Remove prefix
            if prompt.endswith('"'):
                prompt = prompt[:-1]
            elif prompt.endswith('..."'):
                prompt = prompt[:-4] + "..."

            # Check if it matches question patterns
            prompt_lower = prompt.lower()
            is_question = False

            for pattern in config.QUESTION_PATTERNS:
                if pattern.lower() in prompt_lower:
                    is_question = True
                    break

            # Also check for literal question mark at end
            if prompt.rstrip().endswith("?"):
                is_question = True

            if is_question:
                # Clean up the question for display
                clean_question = prompt.strip()
                if len(clean_question) > 200:
                    clean_question = clean_question[:197] + "..."
                questions.append(clean_question)

    return questions


def get_session_link(state) -> str:
    """Get wiki-link to session note."""
    filename = note_writer.get_note_filename(state)
    # Remove .md extension for wiki link
    note_name = filename[:-3] if filename.endswith(".md") else filename
    return f"[[{note_name}]]"


def append_questions_to_open_questions(state, questions: list) -> int:
    """
    Append discovered questions to open-questions.md.

    Returns number of questions added.
    """
    if not questions:
        return 0

    if not config.OPEN_QUESTIONS_FILE.exists():
        # Don't create the file if it doesn't exist
        return 0

    session_link = get_session_link(state)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    # Read existing content
    existing = config.OPEN_QUESTIONS_FILE.read_text(encoding="utf-8")

    # Check which questions are already present (avoid duplicates)
    new_questions = []
    for q in questions:
        # Simple check: is the question text already in the file?
        if q not in existing:
            new_questions.append(q)

    if not new_questions:
        return 0

    # Build new entries
    entries = []
    for q in new_questions:
        entry = f"- [ ] {q} (source: {session_link}, {date_str})"
        entries.append(entry)

    # Append to file
    # Add some spacing if file doesn't end with newline
    suffix = ""
    if existing and not existing.endswith("\n"):
        suffix = "\n"

    new_content = existing + suffix + "\n".join(entries) + "\n"

    # Atomic write
    temp_path = config.OPEN_QUESTIONS_FILE.with_suffix(".tmp")
    temp_path.write_text(new_content, encoding="utf-8", errors="surrogatepass")
    # Windows: use os.replace() to overwrite existing file
    os.replace(temp_path, config.OPEN_QUESTIONS_FILE)

    return len(new_questions)


def promote_session_questions(state) -> int:
    """
    Main entry point: extract questions from session and add to open questions.

    Should be called on Stop/SessionEnd events.
    Returns number of questions promoted.

    Questions are filtered through an LLM quality gate to prevent conversation
    fragments and debugging chatter from polluting the open questions file.
    """
    questions = extract_questions_from_events(state)

    # Apply LLM quality filter
    filtered_questions = filter_questions_with_llm(questions)

    return append_questions_to_open_questions(state, filtered_questions)
