"""
core/agent.py — OperatorAgent: thin adapter between the UI and AgentCore.

Exposes the same public API as the original agent.py so the UI needs
minimal changes. All real logic lives in AgentCore.
"""
from __future__ import annotations
from typing import Any, Optional

from core.agent_core import AgentCore
from core.approval import ApprovalSystem
from observability.logger import get_logger

logger = get_logger("agent")


class OperatorAgent:
    """
    Thin façade over AgentCore.

    The UI calls:  agent.start(metadata)  /  agent.stop()
    The UI reads:  agent.approval  (for approval button wiring)
    """

    def __init__(self, ui=None):
        self.ui = ui
        self.core = AgentCore(ui=ui)
        self.approval = ApprovalSystem(ui)

        # Wire approval into core so the loop can gate on user input
        self.core.approval = self.approval

        # Legacy attribute aliases expected by the UI
        self.memory = self.core.semantic        # SemanticMemory
        self.running = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self, metadata: Any = None, start_auto_approve: bool = True) -> None:
        """Start the agent with a goal string, dict, or 'Autonomous'."""
        self.running = True
        self.core.state.running = True

        if start_auto_approve:
            self.approval.set_auto_approve(True)

        goal_input = self._normalize_metadata(metadata)
        self.core.start(goal_input, auto_approve=start_auto_approve)
        logger.info(f"OperatorAgent started: {goal_input}")

    def stop(self) -> None:
        self.running = False
        self.core.stop()
        try:
            self.approval.set_auto_approve(False)
        except Exception:
            pass
        logger.info("OperatorAgent stopped.")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _normalize_metadata(self, metadata: Any) -> Any:
            """Accept dict, string, or None; normalize to something AgentCore understands."""
            # 1. Handle Empty/Autonomous
            if metadata is None or str(metadata).strip().lower() in ("", "autonomous"):
                return "Autonomous"
            
            # 2. Handle Structured Dicts
            if isinstance(metadata, dict):
                return metadata
                
            # 3. Handle Plain Strings (Legacy & Direct)
            return str(metadata).strip()