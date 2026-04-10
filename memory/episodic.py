"""
memory/episodic.py — Chronological log of agent actions (episodic memory).

Stores structured records of what the agent did, when, and with what outcome.
Supports querying by chapter, action type, or recency.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
import json
import os


@dataclass
class Episode:
    timestamp: str
    iteration: int
    chapter: str
    action_type: str
    payload: str
    result: str
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_display(self) -> str:
        status = "✓" if self.success else "✗"
        return (f"[{self.timestamp}] {status} {self.action_type} | "
                f"Chapter: {self.chapter} | Iter: {self.iteration}\n"
                f"  Payload: {self.payload[:80]}\n"
                f"  Result:  {self.result[:100]}")


class EpisodicMemory:
    """
    Append-only log of agent episodes.

    Episodes are stored in memory during a session. Optionally persisted
    to a JSONL file for cross-session replay and debugging.
    """

    def __init__(self, persist_path: Optional[str] = None, max_entries: int = 500):
        self._episodes: List[Episode] = []
        self._persist_path = persist_path
        self._max_entries = max_entries

        if persist_path:
            os.makedirs(os.path.dirname(persist_path), exist_ok=True)

    def log(
        self,
        action_type: str,
        payload: str,
        result: str,
        chapter: str = "",
        iteration: int = 0,
        success: Optional[bool] = None,
        metadata: Optional[dict] = None,
    ) -> Episode:
        if success is None:
            success = len(result) > 50 and "error" not in result.lower()

        ep = Episode(
            timestamp=datetime.utcnow().isoformat(),
            iteration=iteration,
            chapter=chapter,
            action_type=action_type,
            payload=payload[:300],
            result=result[:500],
            success=success,
            metadata=metadata or {},
        )

        self._episodes.append(ep)
        if len(self._episodes) > self._max_entries:
            self._episodes = self._episodes[-self._max_entries:]

        if self._persist_path:
            self._append_to_disk(ep)

        return ep

    def recent(self, n: int = 10) -> List[Episode]:
        return self._episodes[-n:]

    def by_chapter(self, chapter: str) -> List[Episode]:
        return [e for e in self._episodes if chapter.lower() in e.chapter.lower()]

    def by_action_type(self, action_type: str) -> List[Episode]:
        return [e for e in self._episodes if e.action_type == action_type]

    def success_rate(self) -> float:
        if not self._episodes:
            return 0.0
        return sum(1 for e in self._episodes if e.success) / len(self._episodes)

    def summary(self) -> str:
        total = len(self._episodes)
        if total == 0:
            return "No episodes recorded."
        rate = self.success_rate()
        types = {}
        for e in self._episodes:
            types[e.action_type] = types.get(e.action_type, 0) + 1
        breakdown = ", ".join(f"{k}:{v}" for k, v in types.items())
        return f"Episodes: {total} | Success: {rate:.0%} | Actions: [{breakdown}]"

    def clear_session(self) -> None:
        self._episodes.clear()

    def _append_to_disk(self, ep: Episode) -> None:
        try:
            with open(self._persist_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(ep.to_dict()) + "\n")
        except Exception:
            pass

    def __len__(self) -> int:
        return len(self._episodes)
