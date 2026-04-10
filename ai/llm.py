"""
ai/llm.py — Thin shim for backwards compatibility.

Old code imported `from ai.llm import ask_llm`.
This shim delegates to the new GemmaProvider.
"""
from __future__ import annotations
from typing import Optional

_provider = None


def _get_provider():
    global _provider
    if _provider is None:
        from llm.gemma_provider import GemmaProvider
        _provider = GemmaProvider()
    return _provider


def ask_llm(prompt: str, system: Optional[str] = None) -> str:
    """Legacy entry point. Use GemmaProvider directly in new code."""
    return _get_provider().complete(prompt, system=system)
