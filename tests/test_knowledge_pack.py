"""Tests for knowledge_pack module."""

import json
import unittest

from claude_note.knowledge_pack import (
    Concept,
    Decision,
    HowTo,
    KnowledgePack,
    NoteOp,
    OpenQuestion,
    validate_knowledge_pack,
)


class TestKnowledgePackSerialization(unittest.TestCase):
    """Tests for KnowledgePack to_dict / from_dict round-trip."""

    def _make_pack(self, **overrides):
        defaults = dict(
            session_id="sess-001",
            date="2025-01-15",
            title="Test session",
            time="14:30:00",
            highlights=["did stuff"],
            concepts=[Concept(name="X", summary="About X", tags=["t"], links_suggested=["note-a"])],
            decisions=[Decision(decision="Use Y", rationale="Because", evidence=["fact1"])],
            open_questions=[OpenQuestion(question="Why?", context="Matters", suggested_next_step="Ask")],
            howtos=[HowTo(title="Do Z", steps=["step1"], gotchas=["watch out"])],
            note_ops=[NoteOp(op="create", path="new.md", body_markdown="# Hi", frontmatter={"tags": ["x"]})],
        )
        defaults.update(overrides)
        return KnowledgePack(**defaults)

    def test_round_trip(self):
        pack = self._make_pack()
        data = pack.to_dict()
        restored = KnowledgePack.from_dict(data)
        self.assertEqual(restored.session_id, pack.session_id)
        self.assertEqual(restored.title, pack.title)
        self.assertEqual(len(restored.concepts), 1)
        self.assertEqual(restored.concepts[0].name, "X")

    def test_json_round_trip(self):
        pack = self._make_pack()
        json_str = pack.to_json()
        restored = KnowledgePack.from_json(json_str)
        self.assertEqual(restored.to_dict(), pack.to_dict())

    def test_from_dict_with_missing_fields(self):
        """from_dict should handle missing optional fields gracefully."""
        data = {"session_id": "s", "date": "2025-01-01", "title": "T"}
        pack = KnowledgePack.from_dict(data)
        self.assertEqual(pack.concepts, [])
        self.assertEqual(pack.note_ops, [])
        self.assertEqual(pack.time, "")

    def test_is_empty_true(self):
        pack = self._make_pack(highlights=[], concepts=[], decisions=[], open_questions=[], howtos=[])
        self.assertTrue(pack.is_empty())

    def test_is_empty_false(self):
        pack = self._make_pack()
        self.assertFalse(pack.is_empty())

    def test_note_op_to_dict_strips_none(self):
        op = NoteOp(op="append", path="x.md", body_markdown="hi")
        d = op.to_dict()
        self.assertNotIn("frontmatter", d)
        self.assertNotIn("managed_block_id", d)


class TestValidateKnowledgePack(unittest.TestCase):
    """Tests for validate_knowledge_pack()."""

    def test_valid_pack_no_warnings(self):
        pack = KnowledgePack(
            session_id="s1", date="2025-01-01", title="Title",
            concepts=[Concept(name="C", summary="Short summary")],
        )
        warnings = validate_knowledge_pack(pack)
        self.assertEqual(warnings, [])

    def test_missing_required_fields(self):
        pack = KnowledgePack(session_id="", date="", title="")
        warnings = validate_knowledge_pack(pack)
        self.assertIn("Missing session_id", warnings)
        self.assertIn("Missing date", warnings)
        self.assertIn("Missing title", warnings)

    def test_concept_missing_name(self):
        pack = KnowledgePack(
            session_id="s", date="d", title="t",
            concepts=[Concept(name="", summary="ok")],
        )
        warnings = validate_knowledge_pack(pack)
        self.assertTrue(any("missing name" in w for w in warnings))

    def test_concept_summary_too_long(self):
        pack = KnowledgePack(
            session_id="s", date="d", title="t",
            concepts=[Concept(name="C", summary="x" * 501)],
        )
        warnings = validate_knowledge_pack(pack)
        self.assertTrue(any("too long" in w for w in warnings))

    def test_invalid_note_op(self):
        pack = KnowledgePack(
            session_id="s", date="d", title="t",
            note_ops=[NoteOp(op="invalid", path="x.md", body_markdown="hi")],
        )
        warnings = validate_knowledge_pack(pack)
        self.assertTrue(any("invalid op" in w for w in warnings))

    def test_create_without_frontmatter(self):
        pack = KnowledgePack(
            session_id="s", date="d", title="t",
            note_ops=[NoteOp(op="create", path="x.md", body_markdown="hi")],
        )
        warnings = validate_knowledge_pack(pack)
        self.assertTrue(any("missing frontmatter" in w for w in warnings))

    def test_upsert_block_without_id(self):
        pack = KnowledgePack(
            session_id="s", date="d", title="t",
            note_ops=[NoteOp(op="upsert_block", path="x.md", body_markdown="hi")],
        )
        warnings = validate_knowledge_pack(pack)
        self.assertTrue(any("missing managed_block_id" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
