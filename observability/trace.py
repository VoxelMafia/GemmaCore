"""
observability/trace.py — Structured per-session execution trace.
Writes to data/logs/trace.jsonl (absolute, anchored to project root).
"""
from __future__ import annotations
import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _resolve_path(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    if not os.path.isabs(raw):
        raw = os.path.join(_PROJECT_ROOT, raw)
    os.makedirs(os.path.dirname(raw), exist_ok=True)
    return raw


class Tracer:
    """
    Records structured trace events to an in-memory buffer + optional JSONL file.

    Usage:
        tracer = Tracer()                          # in-memory only
        tracer = Tracer(session_id="abc123")       # in-memory only, named session
        tracer.record("ACTION", {"type": "SEARCH"})
    """

    VALID_PHASES = {
        "PERCEPTION", "THOUGHT", "PLAN", "ACTION",
        "RESULT", "REFLECTION", "SYSTEM", "ERROR",
    }

    def __init__(self, session_id: Optional[str] = None, path: Optional[str] = None):
        # NOTE: session_id is first so Tracer(state.session_id) works correctly
        self._session_id = (session_id or str(uuid.uuid4()))[:8]
        self._path = _resolve_path(path)
        self._step = 0
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def record(self, phase: str, data: Dict[str, Any]) -> Dict[str, Any]:
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
        with self._lock:
            events = self._buffer[-last_n:]
        lines = [f"{'─'*60}", f" Session {self._session_id} — last {len(events)} events", f"{'─'*60}"]
        for e in events:
            ts = e["ts"][11:]
            summary = _summarize_data(e["data"])
            lines.append(f"  [{ts}] step={e['step']:>3}  [{e['phase']:<12}] {summary}")
        lines.append(f"{'─'*60}")
        return "\n".join(lines)

    def to_jsonl(self) -> str:
        with self._lock:
            return "\n".join(json.dumps(e, ensure_ascii=False) for e in self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._step = 0

    def __len__(self) -> int:
        return len(self._buffer)

    def _append(self, entry: Dict[str, Any]) -> None:
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass


def _summarize_data(data: Dict[str, Any]) -> str:
    for k in ["summary", "plan_excerpt", "type", "result_excerpt", "reflection_excerpt", "selected"]:
        if k in data:
            val = str(data[k])
            return f"{k}={val[:80]}"
    if data:
        k = next(iter(data))
        return f"{k}={str(data[k])[:80]}"
    return ""