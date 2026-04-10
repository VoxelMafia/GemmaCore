"""
observability/logger.py — Structured logger with phase-tagged output.

Emits human-readable logs in the format:
  [TIMESTAMP] [LEVEL] [COMPONENT] message

Phase tags ([PERCEPTION], [THOUGHT], [PLAN], [ACTION], [RESULT], [REFLECTION])
are emitted by the agent loop — this module handles formatting and routing.
"""
from __future__ import annotations
import logging
import os
import sys
import threading
import time
from typing import Callable, Optional

# ── Setup ──────────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_ui_callback: Optional[Callable[[str], None]] = None
_log_path: Optional[str] = None
_initialized = False


def _ensure_init() -> None:
    global _initialized, _log_path
    if _initialized:
        return
    try:
        from config.settings import settings
        _log_path = settings.agent.log_path
    except Exception:
        _log_path = "./data/logs/agent.log"
    os.makedirs(os.path.dirname(_log_path), exist_ok=True)
    _initialized = True


# ── Public API ─────────────────────────────────────────────────────────────────

def set_ui_callback(fn: Callable[[str], None]) -> None:
    """Register a callback that receives formatted log lines for the UI."""
    global _ui_callback
    _ui_callback = fn


def get_logger(name: str) -> "AgentLogger":
    """Return a named logger instance."""
    _ensure_init()
    return AgentLogger(name)


# ── Logger class ───────────────────────────────────────────────────────────────

class AgentLogger:
    """
    Lightweight logger that writes to disk and optionally forwards to a UI callback.
    Uses a consistent format:  [HH:MM:SS] [LEVEL] [name] message
    """

    LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "WARN": 30, "ERROR": 40, "CRITICAL": 50}

    def __init__(self, name: str, min_level: str = "DEBUG"):
        self._name = name
        self._min = self.LEVELS.get(min_level.upper(), 10)

    def debug(self, msg: str, **kw) -> None:
        self._emit("DEBUG", msg)

    def info(self, msg: str, **kw) -> None:
        self._emit("INFO", msg)

    def warning(self, msg: str, **kw) -> None:
        self._emit("WARN", msg)

    # alias
    warn = warning

    def error(self, msg: str, exc_info: bool = False, **kw) -> None:
        if exc_info:
            import traceback
            msg = msg + "\n" + traceback.format_exc()
        self._emit("ERROR", msg)

    def critical(self, msg: str, **kw) -> None:
        self._emit("CRITICAL", msg)

    def _emit(self, level: str, msg: str) -> None:
        if self.LEVELS.get(level, 0) < self._min:
            return
        _ensure_init()
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] [{level:<5}] [{self._name}] {msg}"
        _write(line)

    # Convenience: forward legacy log(msg, level=..., component=...) calls
    def log(self, msg: str, level: str = "INFO", component: Optional[str] = None) -> str:
        tag = f"[{component}] " if component else ""
        self._emit(level, tag + msg)
        return msg


def _write(line: str) -> None:
    """Write to disk + forward to UI callback."""
    global _ui_callback, _log_path
    with _lock:
        try:
            if _log_path:
                with open(_log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except OSError:
            pass
        try:
            if _ui_callback:
                _ui_callback(line)
        except Exception:
            pass


# ── Legacy shim ───────────────────────────────────────────────────────────────
# Keeps old `from utils.logger import log, set_ui_callback` calls working.

def log(msg: str, level: str = "INFO", component: Optional[str] = None) -> str:
    _ensure_init()
    tag = f"[{component}] " if component else ""
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] [{level:<5}] {tag}{msg}"
    _write(line)
    return line
