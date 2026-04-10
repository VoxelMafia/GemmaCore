"""
core/planner.py — Decision engine: interprets agent intent, selects next action,
ranks options by confidence, and produces an explainable plan.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Any, Dict

from core.state import AgentState
from core.personality import PersonalityEngine
from observability.logger import get_logger
from observability.trace import Tracer

logger = get_logger(__name__)


@dataclass
class PlanOption:
    action_type: str          # "SEARCH" | "NAVIGATE" | "WRITE" | "REFLECT"
    skill_name: str           # maps to registry key
    payload: Any              # FIXED: Any (was str) to support dicts for skills
    confidence: float         # 0.0 – 1.0
    rationale: str            # why this was chosen
    requires_approval: bool = True


class Planner:
    """
    Interprets the raw LLM plan text and translates it into a ranked
    list of PlanOptions. The highest-confidence option is chosen.
    """

    def __init__(self, state: AgentState, personality: PersonalityEngine, tracer: Optional[Tracer] = None):
        self.state = state
        self.personality = personality
        self.tracer = tracer

    # ── Public API ─────────────────────────────────────────────────────────────

    def interpret(self, raw_plan: str) -> PlanOption:
        """Parse raw LLM plan text → return the best PlanOption."""
        options = self._extract_options(raw_plan)
        ranked = self._rank(options)

        if self.tracer:
            self.tracer.record("PLAN", {
                "raw": raw_plan[:400],
                "options": [
                    {"type": o.action_type, "confidence": round(o.confidence, 3)}
                    for o in ranked
                ],
                "selected": ranked[0].action_type if ranked else "FALLBACK",
            })

        logger.info(f"[PLAN] {len(ranked)} option(s) evaluated. Selected: {ranked[0].action_type if ranked else 'NONE'}")
        return ranked[0] if ranked else self._fallback_option()

    def extract_sub_goal(self, raw_plan: str) -> Optional[str]:
        match = re.search(r"SUB_GOAL:\s*(.*)", raw_plan, re.I)
        return match.group(1).strip() if match else None

    # ── Private ────────────────────────────────────────────────────────────────

    def _extract_options(self, text: str) -> List[PlanOption]:
        options: List[PlanOption] = []

        # 1. NAVIGATE command logic
        if re.search(r"NAVIGATE:", text, re.I):
            url_match = re.search(r"https?://[^\s`<>\"'\)\]\}]+", text)
            if url_match:
                url = url_match.group(0).strip("`'\"().,[]{} ")
                already_visited = url in self.state.attempted_urls
                confidence = 0.55 if not already_visited else 0.10
                
                # Personality influence: Curiosity boosts NAVIGATE
                confidence += self.personality.score("explore_vs_exploit") * 0.15
                
                options.append(PlanOption(
                    action_type="NAVIGATE",
                    skill_name="browser",
                    payload={"url": url}, # FIXED: dictionary for skill
                    confidence=min(confidence, 1.0),
                    rationale="LLM explicitly requested URL navigation.",
                    requires_approval=True,
                ))

        # 2. SEARCH command logic
        search_match = re.search(r"SEARCH:\s*[:\s]*['\"\[]?(.*?)['\"\]]?(\n|$)", text, re.I)
        if search_match:
            query = search_match.group(1).strip("[]' ")
            # Clean technical noise
            query = re.sub(r"[\(\)]", "", query)
            query = re.sub(r"\b(AND|OR)\b", "", query, flags=re.I).strip()
            
            confidence = 0.70
            # Personality influence: Skepticism boosts SEARCH validation
            confidence += self.personality.score("accept_low_quality_source") * -0.10
            
            options.append(PlanOption(
                action_type="SEARCH",
                skill_name="academic",
                payload={"query": query, "limit": 5}, # FIXED: dictionary for skill
                confidence=min(confidence, 1.0),
                rationale="LLM requested academic search for this query.",
                requires_approval=False,
            ))

        # 3. WRITE command logic (The "Mission Complete" condition)
        if "✍️" in text or "COMMAND: WRITE" in text.upper() or "Synthesizing" in text:
            confidence = 0.85
            # Ensure we have enough data before writing
            if len(self.state.short_term_memory) < 3:
                confidence -= 0.40 # Penalize writing with low data

            options.append(PlanOption(
                action_type="WRITE",
                skill_name="file_ops",
                payload={
                    "path": f"Chapter_{self.state.current_chapter_title or 'Draft'}.md",
                    "content": text 
                },
                confidence=max(0.1, confidence),
                rationale="Agent attempting to synthesize and save research results.",
                requires_approval=True,
            ))

        # 4. FALLBACK / REFLECT logic
        if not options:
            rigor_gap_match = re.search(r"RIGOR.GAP:\s*(.*)", text, re.I)
            payload_str = rigor_gap_match.group(1).strip() if rigor_gap_match else "Needs more ground truth."
            options.append(PlanOption(
                action_type="REFLECT",
                skill_name="memory",
                payload={"query": payload_str}, # Memory reflection payload
                confidence=0.40,
                rationale="No explicit action found; defaulting to internal reflection.",
                requires_approval=False,
            ))

        return options

    def _rank(self, options: List[PlanOption]) -> List[PlanOption]:
        """Sort by confidence descending and apply trait weights."""
        ranked = sorted([o for o in options if o.confidence > 0.05],
                        key=lambda o: o.confidence, reverse=True)
        return ranked

    def _fallback_option(self) -> PlanOption:
        """The emergency break-out action for loops."""
        fallback_query = self.state.current_sub_goal or self.state.active_goal_str() or "AI Research"
        return PlanOption(
            action_type="SEARCH",
            skill_name="academic",
            payload={"query": fallback_query, "limit": 5},
            confidence=0.30,
            rationale="Fallback: no parseable command. Forcing new search to break loop.",
            requires_approval=False,
        )