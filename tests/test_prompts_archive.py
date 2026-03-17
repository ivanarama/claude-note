"""Tests for prompts_archive module."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_note import prompts_archive


class TestEnsureArchiveExists(unittest.TestCase):
    """Tests for _ensure_archive_exists()."""

    def test_creates_file_with_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "archive.md"
            with patch.object(prompts_archive, "get_prompts_archive_path", return_value=path):
                result = prompts_archive._ensure_archive_exists()
            self.assertTrue(result)
            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8")
            self.assertIn("tags:", content)
            self.assertIn("Prompts Archive", content)

    def test_existing_file_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "archive.md"
            path.write_text("existing content", encoding="utf-8")
            with patch.object(prompts_archive, "get_prompts_archive_path", return_value=path):
                result = prompts_archive._ensure_archive_exists()
            self.assertTrue(result)
            self.assertEqual(path.read_text(encoding="utf-8"), "existing content")


class TestAppendPromptsToArchive(unittest.TestCase):
    """Tests for append_prompts_to_archive()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.archive_path = Path(self.tmpdir) / "archive.md"
        self.archive_path.write_text("---\ntags: [log]\n---\n\n", encoding="utf-8")

        self.patches = [
            patch.object(prompts_archive, "is_prompts_archive_enabled", return_value=True),
            patch.object(prompts_archive, "get_prompts_archive_path", return_value=self.archive_path),
            patch.object(prompts_archive, "_validate_archive_path", return_value=True),
            patch("claude_note.prompts_archive.config"),
        ]
        for p in self.patches:
            mock = p.start()
        # Set LOCK_TIMEOUT on the config mock
        prompts_archive.config.LOCK_TIMEOUT = 5
        prompts_archive.config.PROMPTS_ARCHIVE_INCLUDE_PLAN_SUMMARY = True

    def tearDown(self):
        for p in self.patches:
            p.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_appends_prompts(self):
        result = prompts_archive.append_prompts_to_archive(
            session_id="abc123def456ghij",
            cwd="/test",
            user_prompts=["hello", "world"],
            timestamp="2025-01-15 10:00:00",
        )
        self.assertTrue(result)
        content = self.archive_path.read_text(encoding="utf-8")
        self.assertIn("2025-01-15 10:00:00", content)
        self.assertIn("1. hello", content)
        self.assertIn("2. world", content)

    def test_appends_plan_and_summary(self):
        result = prompts_archive.append_prompts_to_archive(
            session_id="abc123def456ghij",
            cwd="/test",
            user_prompts=["do stuff"],
            plan="Step 1: do thing",
            summary="Did the thing",
            timestamp="2025-01-15 10:00:00",
        )
        self.assertTrue(result)
        content = self.archive_path.read_text(encoding="utf-8")
        self.assertIn("**Plan:**", content)
        self.assertIn("Step 1: do thing", content)
        self.assertIn("**Summary:**", content)
        self.assertIn("Did the thing", content)

    def test_empty_prompts_no_plan_returns_false(self):
        result = prompts_archive.append_prompts_to_archive(
            session_id="abc123",
            cwd="/test",
            user_prompts=[],
        )
        self.assertFalse(result)

    def test_disabled_returns_false(self):
        with patch.object(prompts_archive, "is_prompts_archive_enabled", return_value=False):
            result = prompts_archive.append_prompts_to_archive(
                session_id="abc",
                cwd="/test",
                user_prompts=["hello"],
            )
        self.assertFalse(result)

    def test_path_outside_vault_returns_false(self):
        with patch.object(prompts_archive, "_validate_archive_path", return_value=False):
            result = prompts_archive.append_prompts_to_archive(
                session_id="abc",
                cwd="/test",
                user_prompts=["hello"],
            )
        self.assertFalse(result)


class TestGetArchiveStats(unittest.TestCase):
    """Tests for get_archive_stats()."""

    def test_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.md"
            with patch.object(prompts_archive, "get_prompts_archive_path", return_value=path), \
                 patch.object(prompts_archive, "is_prompts_archive_enabled", return_value=True):
                stats = prompts_archive.get_archive_stats()
        self.assertFalse(stats["exists"])
        self.assertEqual(stats["entry_count"], 0)

    def test_parses_entries_and_prompts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "archive.md"
            content = """---
tags: [log]
---

### 2025-01-15 10:00:00 - abc123def456gh
**Working directory:** `/test`

**User Prompts:**

1. first prompt
2. second prompt

---

### 2025-01-16 11:00:00 - def456abc123gh
**Working directory:** `/test2`

**User Prompts:**

1. third prompt

---
"""
            path.write_text(content, encoding="utf-8")
            with patch.object(prompts_archive, "get_prompts_archive_path", return_value=path), \
                 patch.object(prompts_archive, "is_prompts_archive_enabled", return_value=True):
                stats = prompts_archive.get_archive_stats()

        self.assertTrue(stats["exists"])
        self.assertEqual(stats["entry_count"], 2)
        self.assertEqual(stats["total_prompts"], 3)
        self.assertEqual(len(stats["recent_entries"]), 2)

    def test_handles_double_digit_prompts(self):
        """Regression: numbering >9 should be counted correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "archive.md"
            lines = ["### 2025-01-15 10:00:00 - session1234567", ""]
            for i in range(1, 12):
                lines.append(f"{i}. prompt number {i}")
            lines.append("\n---\n")
            path.write_text("\n".join(lines), encoding="utf-8")

            with patch.object(prompts_archive, "get_prompts_archive_path", return_value=path), \
                 patch.object(prompts_archive, "is_prompts_archive_enabled", return_value=True):
                stats = prompts_archive.get_archive_stats()

        self.assertEqual(stats["total_prompts"], 11)


class TestValidateArchivePath(unittest.TestCase):
    """Tests for _validate_archive_path()."""

    def test_path_inside_vault(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir) / "vault"
            vault.mkdir()
            archive = vault / "archive.md"
            with patch.object(prompts_archive, "get_prompts_archive_path", return_value=archive), \
                 patch("claude_note.prompts_archive.config") as mock_config:
                mock_config.VAULT_ROOT = vault
                result = prompts_archive._validate_archive_path()
        self.assertTrue(result)

    def test_path_outside_vault(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir) / "vault"
            vault.mkdir()
            outside = Path(tmpdir) / "outside" / "archive.md"
            with patch.object(prompts_archive, "get_prompts_archive_path", return_value=outside), \
                 patch("claude_note.prompts_archive.config") as mock_config:
                mock_config.VAULT_ROOT = vault
                result = prompts_archive._validate_archive_path()
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
