"""
memory/short_term.py — Active context buffer (working memory).

Holds the most recent N text fragments in a FIFO deque.
No persistence; cleared at session start.
"""
from __future__ import annotations
from collections import deque
from typing import List


class ShortTermMemory:
    """
    Fixed-capacity FIFO buffer of recent text fragments.
    Think of this as the agent's 'working memory' — what it is actively
    attending to right now.
    """

    def __init__(self, capacity: int = 20) -> None:
        self._capacity = capacity
        self._buffer: deque = deque(maxlen=capacity)

    def push(self, text: str) -> None:
        """Add a new fragment; oldest is evicted if at capacity."""
        if text and text.strip():
            self._buffer.append(text.strip())

    def recent(self, n: int = 5) -> List[str]:
        """Return the N most recent entries (newest last)."""
        items = list(self._buffer)
        return items[-n:] if n < len(items) else items

    def peek(self) -> str:
        """Return the single most recent entry, or empty string."""
        return self._buffer[-1] if self._buffer else ""

    def as_context(self, n: int = 5, separator: str = "\n---\n") -> str:
        """Convenience: join recent entries into a single string."""
        return separator.join(self.recent(n)) or "No short-term context."

    def clear(self) -> None:
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)

    def __repr__(self) -> str:
        return f"ShortTermMemory(capacity={self._capacity}, used={len(self._buffer)})"
