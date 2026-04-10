"""
skills/memory_ops.py — Memory read/write skill.

Provides the agent with explicit, controlled access to its memory layers.
Permission level 0: memory operations are free (no approval required).
"""
from __future__ import annotations
from typing import Any, Dict, List

from skills.base_skill import BaseSkill


class MemoryOpsSkill(BaseSkill):

    @property
    def name(self) -> str:
        return "memory"

    @property
    def description(self) -> str:
        return "Read from and write to the agent's semantic and episodic memory layers."

    @property
    def input_schema(self) -> Dict[str, str]:
        return {
            "action": "One of: store | retrieve | episodic_summary | clear",
            "text": "(store) Text to store in semantic memory.",
            "query": "(retrieve) Query string for semantic retrieval.",
            "k": "(retrieve) Number of results to return (default: 5).",
        }

    @property
    def output_schema(self) -> Dict[str, str]:
        return {
            "output": "Retrieved text (retrieve) or confirmation string (store/clear).",
        }

    @property
    def side_effects(self) -> List[str]:
        return ["Modifies semantic memory store"]

    @property
    def permission_level(self) -> int:
        return 0  # free

    def __init__(self, agent=None):
        self._agent = agent

    # ── BaseSkill ──────────────────────────────────────────────────────────────

    def _run(self, inputs: Dict[str, Any]) -> Any:
        action = inputs.get("action", "retrieve")

        if action == "store":
            return self._store(inputs.get("text", ""))
        elif action == "retrieve":
            return self._retrieve(inputs.get("query", ""), int(inputs.get("k", 5)))
        elif action == "episodic_summary":
            return self._episodic_summary()
        elif action == "clear":
            return self._clear()
        else:
            return f"Unknown memory action: {action}"

    # ── Private ────────────────────────────────────────────────────────────────

    def _store(self, text: str) -> str:
        if not text.strip():
            return "Nothing to store."
        if self._agent and hasattr(self._agent, "semantic"):
            self._agent.semantic.store(text)
        return f"Stored {len(text)} chars to semantic memory."

    def _retrieve(self, query: str, k: int = 5) -> str:
        if not query.strip():
            return "No query provided."
        if self._agent and hasattr(self._agent, "semantic"):
            return self._agent.semantic.retrieve(query, k=k)
        return "Semantic memory not available."

    def _episodic_summary(self) -> str:
        if self._agent and hasattr(self._agent, "episodic"):
            return self._agent.episodic.summary()
        return "Episodic memory not available."

    def _clear(self) -> str:
        if self._agent and hasattr(self._agent, "semantic"):
            self._agent.semantic.clear_session()
        return "Semantic memory cleared."
