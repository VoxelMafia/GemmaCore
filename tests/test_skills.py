"""
tests/test_skills.py — Unit tests for skill execution (no I/O mocking).
Run with: python -m pytest tests/
"""
import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ── BaseSkill ──────────────────────────────────────────────────────────────────

class TestBaseSkill:
    def test_execute_calls_run(self):
        from skills.base_skill import BaseSkill

        class EchoSkill(BaseSkill):
            @property
            def name(self): return "echo"
            @property
            def description(self): return "Echoes input"
            def _run(self, inputs): return inputs.get("msg", "")

        skill = EchoSkill()
        result = skill.execute({"msg": "hello"})
        assert result == "hello"

    def test_execute_handles_exception_gracefully(self):
        from skills.base_skill import BaseSkill

        class BrokenSkill(BaseSkill):
            @property
            def name(self): return "broken"
            @property
            def description(self): return "Always fails"
            def _run(self, inputs): raise RuntimeError("intentional failure")

        skill = BrokenSkill()
        result = skill.execute({})
        assert "SKILL ERROR" in result
        assert "intentional failure" in result


# ── SkillRegistry ──────────────────────────────────────────────────────────────

class TestSkillRegistry:
    def setup_method(self):
        from skills.registry import SkillRegistry
        self.reg = SkillRegistry()

    def _make_skill(self, skill_name):
        from skills.base_skill import BaseSkill

        class DummySkill(BaseSkill):
            @property
            def name(self): return skill_name
            @property
            def description(self): return f"Dummy {skill_name}"
            def _run(self, inputs): return f"ran {skill_name}"

        return DummySkill()

    def test_register_and_get(self):
        skill = self._make_skill("alpha")
        self.reg.register(skill)
        assert self.reg.get("alpha") is skill

    def test_get_unknown_returns_none(self):
        assert self.reg.get("nonexistent") is None

    def test_run_dispatches_correctly(self):
        self.reg.register(self._make_skill("beta"))
        result = self.reg.run("beta", {})
        assert result == "ran beta"

    def test_run_unknown_raises_key_error(self):
        with pytest.raises(KeyError):
            self.reg.run("missing_skill", {})

    def test_list_skills(self):
        self.reg.register(self._make_skill("gamma"))
        listing = self.reg.list_skills()
        assert "gamma" in listing
        assert "description" in listing["gamma"]

    def test_len(self):
        self.reg.register(self._make_skill("one"))
        self.reg.register(self._make_skill("two"))
        assert len(self.reg) == 2

    def test_overwrite_same_name(self):
        self.reg.register(self._make_skill("dup"))
        self.reg.register(self._make_skill("dup"))
        assert len(self.reg) == 1


# ── FileOpsSkill ───────────────────────────────────────────────────────────────

class TestFileOpsSkill:
    def setup_method(self):
        import tempfile
        from skills.file_ops import FileOpsSkill
        self._tmpdir = tempfile.mkdtemp()
        # Patch workspace path for isolation
        from config.settings import settings
        settings.agent.workspace_path = self._tmpdir
        self.skill = FileOpsSkill(agent=None)
        self.skill._base = self._tmpdir

    def test_write_and_read(self):
        self.skill.execute({"action": "write_text", "path": "test.txt", "content": "hello world"})
        result = self.skill.execute({"action": "read_text", "path": "test.txt"})
        assert result == "hello world"

    def test_read_nonexistent(self):
        result = self.skill.execute({"action": "read_text", "path": "nope.txt"})
        assert "not found" in result.lower() or "Error" in result

    def test_list_files(self):
        self.skill.execute({"action": "write_text", "path": "a.txt", "content": "A"})
        self.skill.execute({"action": "write_text", "path": "b.txt", "content": "B"})
        listing = self.skill.execute({"action": "list_files"})
        assert "a.txt" in listing
        assert "b.txt" in listing

    def test_save_document_creates_file(self):
        result = self.skill.save_document("My Chapter Title", "Content goes here.")
        assert "Saved" in result or "workspace" in result.lower()
        # File should exist
        files = self.skill.execute({"action": "list_files"})
        assert "my-chapter-title" in files

    def test_path_traversal_blocked(self):
        with pytest.raises(PermissionError):
            self.skill.execute({"action": "read_text", "path": "../../etc/passwd"})

    def test_slugify_cleans_title(self):
        slug = FileOpsSkill._slugify("Hello, World! This is a Test.")
        assert " " not in slug
        assert slug == slug.lower()
        assert all(c.isalnum() or c == "-" for c in slug)


# ── MemoryOpsSkill ─────────────────────────────────────────────────────────────

class TestMemoryOpsSkill:
    def setup_method(self):
        from skills.memory_ops import MemoryOpsSkill
        from memory.semantic import SemanticMemory

        class FakeAgent:
            semantic = SemanticMemory(persistent=False)
            episodic = None

        self.skill = MemoryOpsSkill(agent=FakeAgent())

    def test_store_and_retrieve(self):
        self.skill.execute({"action": "store", "text": "quantum entanglement research"})
        result = self.skill.execute({"action": "retrieve", "query": "quantum", "k": 1})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_retrieve_empty(self):
        result = self.skill.execute({"action": "retrieve", "query": "nothing here"})
        assert isinstance(result, str)

    def test_clear(self):
        self.skill.execute({"action": "store", "text": "some content"})
        result = self.skill.execute({"action": "clear"})
        assert "cleared" in result.lower()

    def test_store_empty_is_noop(self):
        result = self.skill.execute({"action": "store", "text": ""})
        assert "Nothing" in result

    def test_unknown_action(self):
        result = self.skill.execute({"action": "explode"})
        assert "Unknown" in result
