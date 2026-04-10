"""
memory/long_term.py — Persistent cross-session storage.

Stores key→value pairs to disk as JSON. Loaded at startup, flushed on write.
Intentionally simple: long-term memory should be deliberate, not automatic.
"""
from __future__ import annotations
import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


class LongTermMemory:
    """
    Persistent key-value store backed by a JSON file on disk.

    Enabled only when `enabled=True` is passed. When disabled, all
    operations are no-ops to keep the system predictable.
    """

    def __init__(self, path: str = "./data/memory_db", enabled: bool = False):
        self.enabled = enabled
        self._path = os.path.join(path, "long_term.json")
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()

        if self.enabled:
            os.makedirs(path, exist_ok=True)
            self._load()

    # ── Read ───────────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        if not self.enabled:
            return default
        with self._lock:
            entry = self._data.get(key)
            return entry["value"] if entry else default

    def search(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Return entries whose key or value contains `keyword`."""
        if not self.enabled:
            return []
        kw = keyword.lower()
        results = []
        with self._lock:
            for k, v in self._data.items():
                val_str = str(v.get("value", "")).lower()
                if kw in k.lower() or kw in val_str:
                    results.append({"key": k, "value": v["value"], "stored_at": v.get("stored_at")})
                    if len(results) >= limit:
                        break
        return results

    def keys(self) -> List[str]:
        if not self.enabled:
            return []
        with self._lock:
            return list(self._data.keys())

    # ── Write ──────────────────────────────────────────────────────────────────

    def store(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._data[key] = {
                "value": value,
                "stored_at": datetime.utcnow().isoformat(),
            }
            self._flush()

    def delete(self, key: str) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            existed = key in self._data
            self._data.pop(key, None)
            if existed:
                self._flush()
            return existed

    def clear(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._data.clear()
            self._flush()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _flush(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"LongTermMemory({status}, {len(self._data)} entries)"
