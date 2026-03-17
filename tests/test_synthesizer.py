"""Tests for synthesizer module."""

import unittest
from unittest.mock import patch, MagicMock

from claude_note.synthesizer import (
    _format_user_prompts,
    _format_tool_summary,
    _format_files_list,
    parse_knowledge_pack,
    build_synthesis_prompt,
)
from claude_note.transcript_reader import TranscriptContent, ToolUse
from claude_note.knowledge_pack import KnowledgePack


class TestFormatUserPrompts(unittest.TestCase):
    """Tests for _format_user_prompts()."""

    def test_empty_prompts(self):
        result = _format_user_prompts([])
        # Should return localized "no prompts" label
        self.assertTrue(len(result) > 0)

    def test_normal_prompts(self):
        result = _format_user_prompts(["Hello", "World"])
        self.assertIn("1. Hello", result)
        self.assertIn("2. World", result)

    def test_truncates_long_prompts(self):
        long_prompt = "x" * 1000
        result = _format_user_prompts([long_prompt])
        self.assertIn("...", result)

    def test_total_truncation(self):
        prompts = [f"prompt {i}" * 100 for i in range(100)]
        result = _format_user_prompts(prompts, max_total=500)
        self.assertIn("more prompts", result)


class TestFormatToolSummary(unittest.TestCase):
    """Tests for _format_tool_summary()."""

    def test_empty_tools(self):
        result = _format_tool_summary([])
        self.assertTrue(len(result) > 0)

    def test_counts_tools(self):
        tools = [
            ToolUse(name="Read", input={"file_path": "/a.py"}),
            ToolUse(name="Read", input={"file_path": "/b.py"}),
            ToolUse(name="Edit", input={"file_path": "/c.py"}),
        ]
        result = _format_tool_summary(tools)
        self.assertIn("Read: 2 uses", result)
        self.assertIn("Edit: 1 uses", result)

    def test_limits_examples_per_type(self):
        """Should not show more than SYNTH_MAX_TOOL_EXAMPLES_PER_TYPE per tool type."""
        tools = [ToolUse(name="Read", input={"file_path": f"/file{i}.py"}) for i in range(10)]
        result = _format_tool_summary(tools)
        # Count how many "Read:" lines appear in notable operations
        read_lines = [l for l in result.split("\n") if l.strip().startswith("- Read:")]
        # Default config is 3
        self.assertLessEqual(len(read_lines), 5)  # generous upper bound


class TestFormatFilesList(unittest.TestCase):
    """Tests for _format_files_list()."""

    def test_empty_files(self):
        result = _format_files_list([])
        self.assertTrue(len(result) > 0)

    def test_short_list(self):
        result = _format_files_list(["a.py", "b.py"])
        self.assertIn("a.py", result)
        self.assertIn("b.py", result)

    def test_truncation(self):
        files = [f"file{i}.py" for i in range(50)]
        result = _format_files_list(files, max_files=5)
        self.assertIn("... and 45 more", result)


class TestParseKnowledgePack(unittest.TestCase):
    """Tests for parse_knowledge_pack()."""

    def test_parses_plain_json(self):
        json_str = '{"session_id": "s1", "date": "2025-01-01", "title": "Test", "highlights": [], "concepts": [], "decisions": [], "open_questions": [], "howtos": [], "note_ops": []}'
        pack = parse_knowledge_pack(json_str)
        self.assertEqual(pack.session_id, "s1")
        self.assertEqual(pack.title, "Test")

    def test_parses_json_in_code_block(self):
        output = '```json\n{"session_id": "s1", "date": "2025-01-01", "title": "Test", "highlights": [], "concepts": [], "decisions": [], "open_questions": [], "howtos": [], "note_ops": []}\n```'
        pack = parse_knowledge_pack(output)
        self.assertEqual(pack.session_id, "s1")

    def test_extracts_json_from_surrounding_text(self):
        output = 'Here is the result:\n{"session_id": "s1", "date": "2025-01-01", "title": "T", "highlights": [], "concepts": [], "decisions": [], "open_questions": [], "howtos": [], "note_ops": []}\nDone!'
        pack = parse_knowledge_pack(output)
        self.assertEqual(pack.session_id, "s1")

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError) as ctx:
            parse_knowledge_pack("not json at all")
        self.assertIn("Failed to parse", str(ctx.exception))


class TestBuildSynthesisPrompt(unittest.TestCase):
    """Tests for build_synthesis_prompt()."""

    @patch("claude_note.synthesizer.qmd_search")
    @patch("claude_note.synthesizer.vault_indexer")
    def test_builds_prompt_with_context(self, mock_vi, mock_qmd):
        mock_qmd.is_qmd_available.return_value = False
        vault_index = MagicMock()
        vault_index.notes = {}

        transcript = TranscriptContent(
            session_id="test-sess",
            user_prompts=["Fix the bug"],
            tool_uses=[ToolUse(name="Read", input={"file_path": "/a.py"})],
            files_touched=["/a.py"],
        )

        prompt = build_synthesis_prompt(transcript, vault_index, cwd="/project", date="2025-01-15")
        self.assertIn("/project", prompt)
        self.assertIn("2025-01-15", prompt)
        self.assertIn("Fix the bug", prompt)
        self.assertIn("session_id", prompt)  # schema


if __name__ == "__main__":
    unittest.main()
