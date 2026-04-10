"""
core/personality.py — Mathematical personality model.

Traits are float values in [0.0, 1.0]. They evolve over time based on
action outcomes and influence the agent's reasoning and decision-making.
"""
from __future__ import annotations
import math
from typing import Dict, Optional
from config.settings import settings


# ── Trait definitions ──────────────────────────────────────────────────────────

TRAIT_DESCRIPTIONS: Dict[str, str] = {
    "curiosity":       "Drives exploration of new information vs. exploiting known sources.",
    "risk_tolerance":  "Willingness to attempt uncertain actions (e.g., unverified URLs).",
    "persistence":     "Tendency to retry after failure rather than move on.",
    "verbosity":       "Depth of reasoning output and explanation length.",
    "skepticism":      "Critical evaluation of sources; resistance to low-quality evidence.",
}

# How strongly each trait influences specific decisions (weight matrix)
DECISION_WEIGHTS: Dict[str, Dict[str, float]] = {
    "explore_vs_exploit": {
        "curiosity": +0.6,
        "risk_tolerance": +0.3,
        "skepticism": -0.2,
    },
    "retry_on_failure": {
        "persistence": +0.7,
        "risk_tolerance": +0.2,
        "skepticism": -0.1,
    },
    "accept_low_quality_source": {
        "risk_tolerance": +0.5,
        "skepticism": -0.6,
        "curiosity": +0.2,
    },
    "depth_of_analysis": {
        "curiosity": +0.4,
        "verbosity": +0.5,
        "skepticism": +0.2,
    },
}

# Learning rate for trait evolution
_ALPHA = 0.05
_DECAY = 0.01   # Slow regression toward defaults over time


class PersonalityEngine:
    """
    Manages personality traits and exposes influence scores for decisions.

    Usage:
        pe = PersonalityEngine(state.personality)
        score = pe.score("explore_vs_exploit")   # float [-1, 1]
        pe.update_from_outcome("curiosity", success=True)
    """

    def __init__(self, traits: Optional[Dict[str, float]] = None) -> None:
        defaults = {
            "curiosity":       settings.personality.curiosity,
            "risk_tolerance":  settings.personality.risk_tolerance,
            "persistence":     settings.personality.persistence,
            "verbosity":       settings.personality.verbosity,
            "skepticism":      settings.personality.skepticism,
        }
        self.traits: Dict[str, float] = defaults.copy()
        if traits:
            for k, v in traits.items():
                if k in self.traits:
                    self.traits[k] = float(max(0.0, min(1.0, v)))

        self._defaults = defaults.copy()

    # ── Read ──────────────────────────────────────────────────────────────────

    def score(self, decision_key: str) -> float:
        weights = DECISION_WEIGHTS.get(decision_key, {})
        if not weights:
            return 0.0
        
        # Calculate weighted influence
        raw = sum(self.traits.get(t, 0.5) * w for t, w in weights.items())
        
        # Optional: Normalize by the total potential weight to keep raw value in a predictable range
        weight_sum = sum(abs(w) for w in weights.values())
        normalized_raw = raw / weight_sum if weight_sum > 0 else raw
        
        return math.tanh(normalized_raw) # Squash to [-1, 1] for stability

    def should(self, decision_key: str, threshold: float = 0.0) -> bool:
        """Boolean decision helper: True when score exceeds threshold."""
        return self.score(decision_key) > threshold

    def reasoning_prefix(self) -> str:
        """
        Returns a short natural-language description of the current personality
        that can be prepended to LLM prompts to bias reasoning style.
        """
        parts = []
        if self.traits["curiosity"] > 0.7:
            parts.append("Prioritize unexplored angles and novel sources.")
        if self.traits["skepticism"] > 0.6:
            parts.append("Critically evaluate all evidence; flag weak citations.")
        if self.traits["persistence"] > 0.7:
            parts.append("Retry failed approaches before abandoning a line of inquiry.")
        if self.traits["verbosity"] > 0.7:
            parts.append("Provide thorough, detailed reasoning at each step.")
        elif self.traits["verbosity"] < 0.3:
            parts.append("Be concise; avoid unnecessary elaboration.")
        if self.traits["risk_tolerance"] < 0.3:
            parts.append("Prefer conservative, well-verified sources over speculative ones.")
        return " ".join(parts) if parts else "Use balanced reasoning."

    # ── Write ─────────────────────────────────────────────────────────────────

    def update_from_outcome(self, trait: str, success: bool, magnitude: float = 1.0) -> None:
        """
        Adjust a trait based on whether an outcome was successful.

        Success → reinforce the trait in the direction it contributed.
        Failure → slightly reduce it.
        `magnitude` ∈ [0, 1] scales the learning signal.
        """
        if trait not in self.traits:
            return
        delta = _ALPHA * magnitude * (1.0 if success else -0.5)
        self.traits[trait] = float(max(0.0, min(1.0, self.traits[trait] + delta)))

    def decay_toward_defaults(self) -> None:
        """Gradually regress all traits back toward their baseline values."""
        for t in self.traits:
            diff = self._defaults[t] - self.traits[t]
            self.traits[t] += _DECAY * diff

    def apply_to_state(self, state) -> None:
        """Write current trait values back into the canonical AgentState."""
        state.personality = self.traits.copy()

    def snapshot(self) -> Dict[str, float]:
        return self.traits.copy()

    def __repr__(self) -> str:
        lines = [f"  {k:<16} {v:.3f}" for k, v in self.traits.items()]
        return "PersonalityEngine(\n" + "\n".join(lines) + "\n)"
