"""
tests/test_memory.py — Unit tests for the memory layer.
Run with: python -m pytest tests/
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Short-Term Memory ──────────────────────────────────────────────────────────

class TestShortTermMemory:
    def setup_method(self):
        from memory.short_term import ShortTermMemory
        self.stm = ShortTermMemory(capacity=5)

    def test_push_and_recent(self):
        self.stm.push("A")
        self.stm.push("B")
        self.stm.push("C")
        recent = self.stm.recent(2)
        assert recent == ["B", "C"]

    def test_capacity_eviction(self):
        for i in range(10):
            self.stm.push(f"item_{i}")
        assert len(self.stm) == 5
        assert "item_9" in self.stm.recent()

    def test_peek(self):
        self.stm.push("last")
        assert self.stm.peek() == "last"

    def test_clear(self):
        self.stm.push("X")
        self.stm.clear()
        assert len(self.stm) == 0
        assert self.stm.peek() == ""

    def test_empty_strings_ignored(self):
        self.stm.push("")
        self.stm.push("   ")
        assert len(self.stm) == 0

    def test_as_context(self):
        self.stm.push("one")
        self.stm.push("two")
        ctx = self.stm.as_context(n=2)
        assert "one" in ctx
        assert "two" in ctx


# ── Episodic Memory ────────────────────────────────────────────────────────────

class TestEpisodicMemory:
    def setup_method(self):
        from memory.episodic import EpisodicMemory
        self.ep = EpisodicMemory(max_entries=100)

    def test_log_and_recent(self):
        self.ep.log("SEARCH", "AI climate", "found 3 papers", chapter="Introduction", iteration=0)
        self.ep.log("NAVIGATE", "https://example.com", "page content", chapter="Introduction", iteration=1)
        recent = self.ep.recent(2)
        assert len(recent) == 2
        assert recent[-1].action_type == "NAVIGATE"

    def test_by_chapter(self):
        self.ep.log("SEARCH", "q1", "r1", chapter="Introduction")
        self.ep.log("SEARCH", "q2", "r2", chapter="Methodology")
        intro = self.ep.by_chapter("Introduction")
        assert len(intro) == 1
        assert intro[0].chapter == "Introduction"

    def test_by_action_type(self):
        self.ep.log("SEARCH", "q", "r")
        self.ep.log("NAVIGATE", "url", "content")
        searches = self.ep.by_action_type("SEARCH")
        assert all(e.action_type == "SEARCH" for e in searches)

    def test_success_rate(self):
        self.ep.log("SEARCH", "q", "good long result " * 10, success=True)
        self.ep.log("SEARCH", "q", "err", success=False)
        rate = self.ep.success_rate()
        assert rate == 0.5

    def test_clear_session(self):
        self.ep.log("SEARCH", "q", "r")
        self.ep.clear_session()
        assert len(self.ep) == 0

    def test_summary_format(self):
        self.ep.log("SEARCH", "q", "r")
        summary = self.ep.summary()
        assert "Episodes" in summary
        assert "SEARCH" in summary


# ── Semantic Memory ────────────────────────────────────────────────────────────

class TestSemanticMemory:
    def setup_method(self):
        from memory.semantic import SemanticMemory
        self.sem = SemanticMemory(persistent=False)

    def test_store_and_retrieve(self):
        self.sem.store("machine learning transformer attention mechanism")
        result = self.sem.retrieve("transformer attention", k=1)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_retrieve(self):
        result = self.sem.retrieve("anything", k=1)
        assert "No" in result or isinstance(result, str)

    def test_score_relevance_basic(self):
        score = self.sem.score_relevance("machine learning", "machine learning is great")
        assert score > 0.5

    def test_score_relevance_no_overlap(self):
        score = self.sem.score_relevance("astronomy stars", "cooking pasta recipes")
        assert score == 0.0

    def test_clear_session(self):
        self.sem.store("test document")
        self.sem.clear_session()
        assert self.sem.count() == 0

    def test_count(self):
        self.sem.store("doc one")
        self.sem.store("doc two")
        assert self.sem.count() == 2


# ── Long-Term Memory ───────────────────────────────────────────────────────────

class TestLongTermMemory:
    def setup_method(self, tmp_path=None):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        from memory.long_term import LongTermMemory
        self.ltm = LongTermMemory(path=self._tmpdir, enabled=True)

    def test_store_and_get(self):
        self.ltm.store("chapter_1", "Introduction content here")
        val = self.ltm.get("chapter_1")
        assert val == "Introduction content here"

    def test_get_missing_returns_default(self):
        val = self.ltm.get("nonexistent", default="fallback")
        assert val == "fallback"

    def test_search(self):
        self.ltm.store("ch1", "climate change AI analysis")
        self.ltm.store("ch2", "quantum computing methods")
        results = self.ltm.search("climate")
        assert len(results) >= 1
        assert any("climate" in r["value"] for r in results)

    def test_delete(self):
        self.ltm.store("temp_key", "value")
        deleted = self.ltm.delete("temp_key")
        assert deleted is True
        assert self.ltm.get("temp_key") is None

    def test_disabled_is_noop(self):
        from memory.long_term import LongTermMemory
        ltm = LongTermMemory(enabled=False)
        ltm.store("k", "v")         # should not raise
        assert ltm.get("k") is None
        assert ltm.keys() == []
