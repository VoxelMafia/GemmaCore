"""
tests/test_planner.py — Unit tests for the Planner and PersonalityEngine.
Run with: python -m pytest tests/
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ── PersonalityEngine ──────────────────────────────────────────────────────────

class TestPersonalityEngine:
    def setup_method(self):
        from core.personality import PersonalityEngine
        self.pe = PersonalityEngine()

    def test_default_traits_in_range(self):
        for trait, val in self.pe.traits.items():
            assert 0.0 <= val <= 1.0, f"Trait {trait} out of range: {val}"

    def test_score_returns_float(self):
        score = self.pe.score("explore_vs_exploit")
        assert isinstance(score, float)
        assert -1.0 <= score <= 1.0

    def test_score_unknown_key_returns_zero(self):
        assert self.pe.score("nonexistent_decision") == 0.0

    def test_should_boolean(self):
        result = self.pe.should("explore_vs_exploit")
        assert isinstance(result, bool)

    def test_update_reinforces_trait(self):
        self.pe.traits["curiosity"] = 0.5
        self.pe.update_from_outcome("curiosity", success=True)
        assert self.pe.traits["curiosity"] > 0.5

    def test_update_reduces_on_failure(self):
        self.pe.traits["curiosity"] = 0.5
        self.pe.update_from_outcome("curiosity", success=False)
        assert self.pe.traits["curiosity"] < 0.5

    def test_trait_stays_in_bounds_after_many_updates(self):
        for _ in range(100):
            self.pe.update_from_outcome("curiosity", success=True)
        assert 0.0 <= self.pe.traits["curiosity"] <= 1.0

    def test_decay_moves_toward_default(self):
        from core.personality import PersonalityEngine
        pe = PersonalityEngine({"curiosity": 0.99})
        pe.decay_toward_defaults()
        assert pe.traits["curiosity"] < 0.99

    def test_reasoning_prefix_is_string(self):
        prefix = self.pe.reasoning_prefix()
        assert isinstance(prefix, str)
        assert len(prefix) > 0

    def test_snapshot_is_copy(self):
        snap = self.pe.snapshot()
        snap["curiosity"] = 0.0
        assert self.pe.traits["curiosity"] != 0.0

    def test_custom_traits_clamped(self):
        from core.personality import PersonalityEngine
        pe = PersonalityEngine({"curiosity": 5.0, "skepticism": -2.0})
        assert pe.traits["curiosity"] == 1.0
        assert pe.traits["skepticism"] == 0.0


# ── Planner ────────────────────────────────────────────────────────────────────

class TestPlanner:
    def _make_planner(self, traits=None):
        from core.state import AgentState
        from core.personality import PersonalityEngine
        from core.planner import Planner
        state = AgentState()
        state.current_sub_goal = "Test sub-goal"
        state.current_chapter_title = "Introduction"
        pe = PersonalityEngine(traits or {})
        return Planner(state, pe)

    def test_interpret_search_command(self):
        planner = self._make_planner()
        raw = """
RIGOR GAP: Missing empirical data on transformer efficiency.
SUB_GOAL: Find papers on transformer benchmarks.
COMMAND: SEARCH: transformer benchmark efficiency 2023
"""
        option = planner.interpret(raw)
        assert option.action_type == "SEARCH"
        assert "transformer" in option.payload.lower()
        assert 0.0 < option.confidence <= 1.0

    def test_interpret_navigate_command(self):
        planner = self._make_planner()
        raw = """
RIGOR GAP: Need full-text methodology.
SUB_GOAL: Read specific paper.
COMMAND: NAVIGATE: https://arxiv.org/pdf/2301.00001
"""
        option = planner.interpret(raw)
        assert option.action_type == "NAVIGATE"
        assert "arxiv.org" in option.payload

    def test_navigate_already_visited_gets_low_confidence(self):
        from core.state import AgentState
        from core.personality import PersonalityEngine
        from core.planner import Planner
        state = AgentState()
        url = "https://arxiv.org/pdf/1234"
        state.attempted_urls = [url]
        pe = PersonalityEngine()
        planner = Planner(state, pe)
        raw = f"NAVIGATE: {url}"
        option = planner.interpret(raw)
        # Already visited — confidence should be low
        assert option.confidence < 0.3

    def test_fallback_when_no_command(self):
        planner = self._make_planner()
        raw = "I think we should look at more data. The evidence is interesting."
        option = planner.interpret(raw)
        # Should still return something (REFLECT or SEARCH fallback)
        assert option.action_type in ("REFLECT", "SEARCH")
        assert option.confidence > 0.0

    def test_extract_sub_goal(self):
        planner = self._make_planner()
        raw = "SUB_GOAL: Find causal inference benchmarks in NLP\nCOMMAND: SEARCH: causal NLP"
        sg = planner.extract_sub_goal(raw)
        assert sg is not None
        assert "causal" in sg.lower()

    def test_extract_sub_goal_missing_returns_none(self):
        planner = self._make_planner()
        raw = "No sub-goal here."
        assert planner.extract_sub_goal(raw) is None

    def test_personality_affects_confidence(self):
        """High curiosity should boost NAVIGATE confidence."""
        from core.state import AgentState
        from core.personality import PersonalityEngine
        from core.planner import Planner

        url = "https://nature.com/articles/12345"
        raw = f"NAVIGATE: {url}"

        state_low = AgentState()
        state_high = AgentState()

        planner_low = Planner(state_low, PersonalityEngine({"curiosity": 0.1, "risk_tolerance": 0.1}))
        planner_high = Planner(state_high, PersonalityEngine({"curiosity": 0.95, "risk_tolerance": 0.9}))

        opt_low = planner_low.interpret(raw)
        opt_high = planner_high.interpret(raw)

        # High curiosity should yield higher or equal confidence for NAVIGATE
        assert opt_high.confidence >= opt_low.confidence - 0.01  # allow tiny float error
