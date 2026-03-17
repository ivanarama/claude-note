"""Tests for transcript_reader module."""

import json
import tempfile
import unittest
from pathlib import Path

from claude_note.transcript_reader import (
    TranscriptContent,
    ToolUse,
    read_transcript,
    get_transcript_summary,
    _extract_file_paths,
    _summarize_tool_output,
    _count_tool_types,
)


def _write_jsonl(path: Path, entries: list[dict]):
    """Write list of dicts as JSONL."""
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TestReadTranscript(unittest.TestCase):
    """Tests for read_transcript()."""

    def test_extracts_user_prompts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "session-abc.jsonl"
            _write_jsonl(path, [
                {"type": "user", "message": {"content": "Hello Claude"}},
                {"type": "user", "message": {"content": "Do something"}},
            ])
            content = read_transcript(path)
        self.assertEqual(content.session_id, "session-abc")
        self.assertEqual(content.user_prompts, ["Hello Claude", "Do something"])

    def test_extracts_user_prompts_from_content_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "session-abc.jsonl"
            _write_jsonl(path, [
                {"type": "user", "message": {"content": [
                    {"type": "text", "text": "Block prompt"},
                ]}},
            ])
            content = read_transcript(path)
        self.assertEqual(content.user_prompts, ["Block prompt"])

    def test_extracts_assistant_texts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sess.jsonl"
            _write_jsonl(path, [
                {"type": "assistant", "message": {"content": [
                    {"type": "text", "text": "Here is my answer"},
                ]}},
            ])
            content = read_transcript(path)
        self.assertEqual(content.assistant_texts, ["Here is my answer"])

    def test_extracts_tool_uses_and_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sess.jsonl"
            _write_jsonl(path, [
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/src/main.py"}},
                    {"type": "tool_use", "id": "t2", "name": "Edit", "input": {"file_path": "/src/utils.py"}},
                ]}},
            ])
            content = read_transcript(path)
        self.assertEqual(len(content.tool_uses), 2)
        self.assertEqual(content.tool_uses[0].name, "Read")
        self.assertIn("/src/main.py", content.files_touched)
        self.assertIn("/src/utils.py", content.files_touched)

    def test_deduplicates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sess.jsonl"
            _write_jsonl(path, [
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/a.py"}},
                    {"type": "tool_use", "id": "t2", "name": "Edit", "input": {"file_path": "/a.py"}},
                ]}},
            ])
            content = read_transcript(path)
        self.assertEqual(content.files_touched, ["/a.py"])

    def test_extracts_errors_from_progress(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sess.jsonl"
            _write_jsonl(path, [
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "exit 1"}},
                ]}},
                {"type": "progress", "tool_use_id": "t1", "result": {"is_error": True, "content": "command failed"}},
            ])
            content = read_transcript(path)
        self.assertEqual(len(content.errors), 1)
        self.assertIn("Bash", content.errors[0])

    def test_extracts_plan_from_thinking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sess.jsonl"
            _write_jsonl(path, [
                {"type": "assistant", "message": {"content": [
                    {"type": "thinking", "thinking": "## Plan\n1. Do A\n2. Do B\n3. Do C"},
                ]}},
            ])
            content = read_transcript(path)
        self.assertIsNotNone(content.plan)
        self.assertIn("Do A", content.plan)

    def test_extracts_summary_from_last_assistant(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sess.jsonl"
            _write_jsonl(path, [
                {"type": "assistant", "message": {"content": [
                    {"type": "text", "text": "Did stuff. ## Summary\nEverything is done."},
                ]}},
            ])
            content = read_transcript(path)
        self.assertIsNotNone(content.summary)
        self.assertIn("Everything is done", content.summary)

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            read_transcript("/nonexistent/path.jsonl")

    def test_skips_invalid_json_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sess.jsonl"
            with open(path, "w", encoding="utf-8") as f:
                f.write("not json\n")
                f.write(json.dumps({"type": "user", "message": {"content": "valid"}}) + "\n")
            content = read_transcript(path)
        self.assertEqual(content.user_prompts, ["valid"])

    def test_empty_transcript(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sess.jsonl"
            path.write_text("", encoding="utf-8")
            content = read_transcript(path)
        self.assertEqual(content.user_prompts, [])
        self.assertEqual(content.tool_uses, [])


class TestExtractFilePaths(unittest.TestCase):
    """Tests for _extract_file_paths()."""

    def test_read_tool(self):
        paths = _extract_file_paths("Read", {"file_path": "/src/main.py"})
        self.assertEqual(paths, ["/src/main.py"])

    def test_glob_tool(self):
        paths = _extract_file_paths("Glob", {"path": "/src"})
        self.assertEqual(paths, ["/src"])

    def test_no_path(self):
        paths = _extract_file_paths("Bash", {"command": "ls"})
        self.assertEqual(paths, [])


class TestSummarizeToolOutput(unittest.TestCase):
    """Tests for _summarize_tool_output()."""

    def test_read_shows_line_count(self):
        result = _summarize_tool_output("Read", "line1\nline2\nline3")
        self.assertIn("3 lines", result)

    def test_grep_shows_match_count(self):
        result = _summarize_tool_output("Grep", "match1\nmatch2")
        self.assertIn("2 matches", result)

    def test_bash_truncates(self):
        long_output = "x" * 300
        result = _summarize_tool_output("Bash", long_output, max_len=100)
        self.assertTrue(result.endswith("..."))
        self.assertLessEqual(len(result), 104)  # 100 + "..."

    def test_empty_output(self):
        result = _summarize_tool_output("Read", "")
        self.assertEqual(result, "")


class TestTranscriptContentToDict(unittest.TestCase):
    """Tests for TranscriptContent.to_dict()."""

    def test_to_dict(self):
        content = TranscriptContent(
            session_id="s1",
            user_prompts=["hello"],
            tool_uses=[ToolUse(name="Read", input={"file_path": "/a.py"})],
            plan="my plan",
            summary="my summary",
        )
        d = content.to_dict()
        self.assertEqual(d["session_id"], "s1")
        self.assertEqual(d["user_prompts"], ["hello"])
        self.assertEqual(d["plan"], "my plan")
        self.assertEqual(d["summary"], "my summary")
        self.assertEqual(len(d["tool_uses"]), 1)
        self.assertEqual(d["tool_uses"][0]["name"], "Read")


class TestCountToolTypes(unittest.TestCase):
    """Tests for _count_tool_types()."""

    def test_counts(self):
        tools = [
            ToolUse(name="Read", input={}),
            ToolUse(name="Read", input={}),
            ToolUse(name="Edit", input={}),
        ]
        counts = _count_tool_types(tools)
        self.assertEqual(counts, {"Read": 2, "Edit": 1})

    def test_empty(self):
        self.assertEqual(_count_tool_types([]), {})


class TestGetTranscriptSummary(unittest.TestCase):
    """Tests for get_transcript_summary()."""

    def test_summary_fields(self):
        content = TranscriptContent(
            session_id="s",
            user_prompts=["a", "b"],
            tool_uses=[ToolUse(name="Read", input={})],
            files_touched=["/x.py"],
            errors=["err"],
        )
        summary = get_transcript_summary(content)
        self.assertEqual(summary["num_user_prompts"], 2)
        self.assertEqual(summary["num_tool_uses"], 1)
        self.assertEqual(summary["num_files_touched"], 1)
        self.assertEqual(summary["num_errors"], 1)
        self.assertEqual(summary["tool_breakdown"], {"Read": 1})


if __name__ == "__main__":
    unittest.main()
