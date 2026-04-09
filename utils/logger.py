from config import LOG_PATH
import os
import time
import threading

# Ensure log directory exists
log_dir = os.path.dirname(LOG_PATH) or "data/logs"
os.makedirs(log_dir, exist_ok=True)

# Optional UI callback (set by the UI app to mirror logs to the textbox)
_ui_callback = None
_lock = threading.Lock()

def set_ui_callback(fn):
    """Register a callback that accepts a single already-formatted log string.
    The UI should pass a function that inserts the provided string into the
    on-screen console without adding another timestamp."""
    global _ui_callback
    _ui_callback = fn

def _format(level, msg, component=None):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    comp = f"[{component}]" if component else ""
    return f"[{ts}] [{level}]{comp} {msg}"

def log(msg, level="INFO", component=None):
    """Write a structured log to disk and forward it to the UI (if set).

    - `msg` may be a string (brief) or an exception/trace string.
    - `level` is one of INFO/WARN/ERROR/DEBUG.
    - `component` is an optional source label (e.g., 'API', 'Browser').
    Returns the formatted message."""
    formatted = _format(level, msg, component)
    try:
        with _lock:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
    except Exception:
        # If disk write fails, silently ignore to avoid crashing the UI
        pass

    # Forward to UI if available
    try:
        if _ui_callback:
            _ui_callback(formatted)
    except Exception:
        pass

    return formatted
