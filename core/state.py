"""
core/state.py — Canonical AgentState: the single source of truth for the running agent.

All modules read from and write to this object. Nothing lives outside it.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum


class AgentStatus(str, Enum):
    IDLE = "IDLE"
    PERCEIVING = "PERCEIVING"
    REASONING = "REASONING"
    PLANNING = "PLANNING"
    ACTING = "ACTING"
    REFLECTING = "REFLECTING"
    UPDATING_MEMORY = "UPDATING_MEMORY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass
class Goal:
    description: str
    primary_domain: str = ""
    intersection_domain: str = ""
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ActionRecord:
    """Immutable record of a completed action."""
    step: int
    action_type: str          # "SEARCH" | "NAVIGATE" | "WRITE" | "REFLECT" | ...
    input_summary: str
    output_summary: str
    skill_used: str
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """
    The single source of truth for agent execution state.
    Created fresh at startup; persisted across loop iterations.
    """
    # ── Identity ──────────────────────────────────────────────────────────────
    session_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # ── Goals ─────────────────────────────────────────────────────────────────
    goals: List[Goal] = field(default_factory=list)
    current_goal: Optional[Goal] = None
    plan: Optional[str] = None         
    # ── Execution context ─────────────────────────────────────────────────────
    current_context: str = ""          # What the agent is focused on right now
    current_action: Optional[Any] = None  # The action currently being executed; None if idle or between actions
    current_sub_goal: str = ""
    current_chapter_index: int = 0
    current_chapter_title: str = ""
    thesis_outline: List[str] = field(default_factory=list)
    iteration: int = 0

    # ── Memory references ─────────────────────────────────────────────────────
    short_term_memory: List[str] = field(default_factory=list)   # recent raw content
    long_term_memory_refs: List[str] = field(default_factory=list)  # keys into LTM
    episodic_refs: List[str] = field(default_factory=list)       # keys into episodic

    # ── Personality ───────────────────────────────────────────────────────────
    personality: Dict[str, float] = field(default_factory=lambda: {
        "curiosity": 0.75,
        "risk_tolerance": 0.40,
        "persistence": 0.80,
        "verbosity": 0.60,
        "skepticism": 0.65,
    })

    # ── Action history ────────────────────────────────────────────────────────
    recent_actions: List[ActionRecord] = field(default_factory=list)
    attempted_urls: List[str] = field(default_factory=list)
    source_map: Dict[str, Any] = field(default_factory=dict)
    consecutive_failures: int = 0

    # ── System status ─────────────────────────────────────────────────────────
    status: AgentStatus = AgentStatus.IDLE
    last_error: Optional[str] = None
    running: bool = False

    # ── Last outputs per phase ────────────────────────────────────────────────
    last_perception: str = ""
    last_plan: str = ""
    last_action_result: str = ""
    last_reflection: str = ""

    # ── Helpers ───────────────────────────────────────────────────────────────
    def set_status(self, status: AgentStatus) -> None:
        self.status = status

    def add_action(self, record: ActionRecord) -> None:
        self.recent_actions.append(record)
        # Keep only last 50 actions in state to avoid bloat
        if len(self.recent_actions) > 50:
            self.recent_actions = self.recent_actions[-50:]

    def push_short_term(self, text: str) -> None:
        from config.settings import settings
        self.short_term_memory.append(text)
        cap = settings.memory.short_term_capacity
        if len(self.short_term_memory) > cap:
            self.short_term_memory = self.short_term_memory[-cap:]

    def active_goal_str(self) -> str:
        if self.current_goal:
            return self.current_goal.description
        return ""

    def to_summary(self) -> Dict[str, Any]:
        """Lightweight dict for logging/display — no large blobs."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "goal": self.active_goal_str(),
            "sub_goal": self.current_sub_goal,
            "chapter": self.current_chapter_title,
            "iteration": self.iteration,
            "actions_taken": len(self.recent_actions),
            "consecutive_failures": self.consecutive_failures,
            "personality": self.personality,
        }
