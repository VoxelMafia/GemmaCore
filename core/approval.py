"""
core/approval.py — Human-in-the-loop approval gate.

Blocks the agent loop until the user approves or rejects an action.
Supports auto-approve mode (for unattended runs).
"""
from __future__ import annotations
import re
import threading
from typing import Optional


class ApprovalSystem:

    def __init__(self, ui=None):
        self.ui = ui
        self._event = threading.Event()
        self._approved = False
        self.auto_approve = False
        self._pending_action: Optional[str] = None

    def request(self, action: str) -> bool:
        """
        Gate execution: returns True (approved) or False (rejected).
        Blocks the calling thread until a decision is made.
        """
        from config.settings import settings
        if not settings.agent.require_approval or self.auto_approve:
            return True

        clean = self._extract_readable_plan(action)
        self._pending_action = clean

        if self.ui and hasattr(self.ui, "set_pending_action"):
            self.ui.after(0, lambda: self.ui.set_pending_action(clean))

        self._event.clear()
        self._event.wait()          # block until approve() or reject() is called
        self._pending_action = None
        return self._approved

    def approve(self) -> None:
        self._approved = True
        self._event.set()

    def reject(self) -> None:
        self._approved = False
        self._event.set()

    def set_auto_approve(self, flag: bool) -> None:
        self.auto_approve = bool(flag)

    def has_pending(self) -> bool:
        return bool(self._pending_action)

    def get_pending(self) -> Optional[str]:
        return self._pending_action

    @staticmethod
    def _extract_readable_plan(raw: str) -> str:
        """Strip LLM internals; show only the readable PLAN/ACTION section."""
        match = re.search(r"(PLAN|ACTION|THOUGHTS?|SUB_GOAL):?\s*(.*)", raw, re.I | re.S)
        if match:
            return match.group(0).strip()[:500]
        return raw[:500] + ("…" if len(raw) > 500 else "")
