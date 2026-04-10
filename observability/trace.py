"""
observability/trace.py — Structured per-session execution trace.

Records every phase of the agent loop as a JSONL entry:
  {"session": "...", "step": 3, "phase": "ACTION", "ts": "...", "data": {...}}

This trace is the ground truth for debugging, replay, and auditing.
"""
from __future__ import annotations
import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional


class Tracer:
    """
    Records structured trace events to an in-memory buffer and optionally
    to a JSONL file. One Tracer instance per agent session.

    Usage:
        tracer = Tracer(path="./data/logs/trace.jsonl")
        tracer.record("PERCEPTION", {"summary": "..."})
        tracer.record("ACTION", {"type": "SEARCH", "payload": "..."})
    """

    VALID_PHASES = {
        "PERCEPTION", "THOUGHT", "PLAN", "ACTION",
        "RESULT", "REFLECTION", "SYSTEM", "ERROR",
    }

    def __init__(self, path: Optional[str] = None, session_id: Optional[str] = None):
        self._session_id = session_id or str(uuid.uuid4())[:8]
        self._path = path
        self._step = 0
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        if path:
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

    # ── Public ─────────────────────────────────────────────────────────────────

    def record(self, phase: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record a phase event.

        Args:
            phase:  One of VALID_PHASES (e.g., "ACTION", "REFLECTION").
            data:   Arbitrary dict payload — keep values short for readability.

        Returns:
            The trace entry dict.
        """
        entry = {
            "session": self._session_id,
            "step": self._step,
            "phase": phase.upper(),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "data": data,
        }

        with self._lock:
            self._buffer.append(entry)
            self._step += 1
            if self._path:
                self._append(entry)

        return entry

    def render(self, last_n: int = 20) -> str:
        """
        Return a human-readable trace of the last N events.
        Suitable for displaying in the CLI reasoning trace.
        """
        with self._lock:
            events = self._buffer[-last_n:]

        lines = [f"{'─'*60}", f" Session {self._session_id} — last {len(events)} events", f"{'─'*60}"]
        for e in events:
            phase = e["phase"]
            step = e["step"]
            ts = e["ts"][11:]  # HH:MM:SS
            data = e["data"]

            # Pretty-print the most important data key
            summary = _summarize_data(data)
            lines.append(f"  [{ts}] step={step:>3}  [{phase:<12}] {summary}")

        lines.append(f"{'─'*60}")
        return "\n".join(lines)

    def to_jsonl(self) -> str:
        """Return all trace entries as a JSONL string."""
        with self._lock:
            return "\n".join(json.dumps(e, ensure_ascii=False) for e in self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._step = 0

    def __len__(self) -> int:
        return len(self._buffer)

    # ── Private ────────────────────────────────────────────────────────────────

    def _append(self, entry: Dict[str, Any]) -> None:
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass


def _summarize_data(data: Dict[str, Any]) -> str:
    """Pick the most meaningful field from a data dict for display."""
    priority_keys = ["summary", "plan_excerpt", "type", "result_excerpt",
                     "reflection_excerpt", "stored", "selected", "error"]
    for k in priority_keys:
        if k in data:
            val = str(data[k])
            return f"{k}={val[:80]}" if len(val) > 80 else f"{k}={val}"
    # Fallback: first key
    if data:
        k = next(iter(data))
        val = str(data[k])[:80]
        return f"{k}={val}"
    return ""
