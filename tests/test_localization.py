"""Tests for localization module."""

import unittest

from claude_note import localization


class TestGetLabel(unittest.TestCase):
    """Tests for get_label()."""

    def test_returns_english_label(self):
        result = localization.get_label("no_user_prompts", "en")
        self.assertEqual(result, "(No user prompts)")

    def test_returns_russian_label(self):
        result = localization.get_label("no_user_prompts", "ru")
        self.assertEqual(result, "(Нет пользовательских запросов)")

    def test_missing_key_returns_key(self):
        result = localization.get_label("nonexistent_key", "en")
        self.assertEqual(result, "nonexistent_key")

    def test_unsupported_language_falls_back_to_english(self):
        result = localization.get_label("no_user_prompts", "fr")
        self.assertEqual(result, "(No user prompts)")

    def test_all_english_keys_exist_in_russian(self):
        en_keys = set(localization._TRANSLATIONS["en"].keys())
        ru_keys = set(localization._TRANSLATIONS["ru"].keys())
        missing = en_keys - ru_keys
        self.assertEqual(missing, set(), f"Russian translation missing keys: {missing}")

    def test_all_russian_keys_exist_in_english(self):
        en_keys = set(localization._TRANSLATIONS["en"].keys())
        ru_keys = set(localization._TRANSLATIONS["ru"].keys())
        extra = ru_keys - en_keys
        self.assertEqual(extra, set(), f"Russian has extra keys not in English: {extra}")


class TestGetSchemaDescription(unittest.TestCase):
    """Tests for get_schema_description()."""

    def test_english_schema_contains_session_id(self):
        schema = localization.get_schema_description("en")
        self.assertIn("session_id", schema)

    def test_russian_schema_contains_session_id(self):
        schema = localization.get_schema_description("ru")
        self.assertIn("session_id", schema)

    def test_unsupported_language_falls_back(self):
        schema = localization.get_schema_description("de")
        en_schema = localization.get_schema_description("en")
        self.assertEqual(schema, en_schema)


class TestFormatSynthesisPrompt(unittest.TestCase):
    """Tests for format_synthesis_prompt()."""

    def _make_prompt(self, lang="en"):
        return localization.format_synthesis_prompt(
            lang=lang,
            cwd="/test/dir",
            date="2025-01-01",
            session_id="test-session-123",
            user_prompts="1. Hello",
            tool_summary="Tool usage summary:",
            files_list="  - test.py",
            errors="(None)",
            related_context="(No related notes)",
            vault_summary="Vault has 5 notes.",
            schema='{"session_id": "string"}',
        )

    def test_english_prompt_contains_context(self):
        prompt = self._make_prompt("en")
        self.assertIn("/test/dir", prompt)
        self.assertIn("2025-01-01", prompt)
        self.assertIn("test-session-123", prompt)

    def test_russian_prompt_contains_context(self):
        prompt = self._make_prompt("ru")
        self.assertIn("/test/dir", prompt)
        self.assertIn("Правила", prompt)

    def test_no_unformatted_placeholders(self):
        prompt = self._make_prompt("en")
        # Should not contain any {placeholder} patterns
        import re
        unformatted = re.findall(r"\{[a-z_]+\}", prompt)
        self.assertEqual(unformatted, [], f"Unformatted placeholders found: {unformatted}")

    def test_russian_no_unformatted_placeholders(self):
        prompt = self._make_prompt("ru")
        import re
        unformatted = re.findall(r"\{[a-z_]+\}", prompt)
        self.assertEqual(unformatted, [], f"Unformatted placeholders found: {unformatted}")


class TestGetSynthesisPromptTemplate(unittest.TestCase):
    """Tests for get_synthesis_prompt_template()."""

    def test_unsupported_language_falls_back(self):
        template = localization.get_synthesis_prompt_template("ja")
        en_template = localization.get_synthesis_prompt_template("en")
        self.assertEqual(template, en_template)


if __name__ == "__main__":
    unittest.main()
