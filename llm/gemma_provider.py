"""
llm/gemma_provider.py — Ollama-backed provider for Gemma (and any Ollama model).

Implements LLMInterface with retry logic and streaming support.
"""
from __future__ import annotations
import time
from typing import Iterator, Optional

try:
    import ollama
    _OLLAMA_AVAILABLE = True
except ImportError:
    _OLLAMA_AVAILABLE = False

from llm.interface import LLMInterface
from config.settings import settings
from observability.logger import get_logger

logger = get_logger(__name__)


class GemmaProvider(LLMInterface):
    """
    Ollama-backed LLM provider.

    Retries on connection failure (Ollama may restart between calls).
    Supports both blocking and streaming completions.
    """

    def __init__(self, model: Optional[str] = None):
        self._model = model or settings.model.name
        self._temperature = settings.model.temperature
        self._num_ctx = settings.model.num_ctx
        self._max_retries = settings.model.max_retries
        self._retry_delay = settings.model.retry_delay

        if not _OLLAMA_AVAILABLE:
            logger.warning("[LLM] ollama package not installed. LLM calls will fail.")

    # ── LLMInterface ──────────────────────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return self._model

    def is_available(self) -> bool:
        if not _OLLAMA_AVAILABLE:
            return False
        try:
            import httpx
            resp = httpx.get(f"{settings.model.base_url}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """
        Blocking chat completion with automatic retry on connection errors.
        """
        if not _OLLAMA_AVAILABLE:
            raise RuntimeError("ollama package is not installed. Run: pip install ollama")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        options = {"num_ctx": self._num_ctx, "temperature": self._temperature}

        for attempt in range(1, self._max_retries + 1):
            try:
                response = ollama.chat(
                    model=self._model,
                    messages=messages,
                    options=options,
                )
                content = response["message"]["content"]
                logger.debug(f"[LLM] complete() OK — {len(content)} chars")
                return content

            except Exception as exc:
                logger.warning(f"[LLM] Attempt {attempt}/{self._max_retries} failed: {exc}")
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay)

        raise ConnectionError(
            f"Ollama server unreachable after {self._max_retries} attempts. "
            "Ensure `ollama serve` is running."
        )

    def stream(self, prompt: str, system: Optional[str] = None) -> Iterator[str]:
        """
        Streaming completion. Yields text chunks as they arrive.
        """
        if not _OLLAMA_AVAILABLE:
            raise RuntimeError("ollama package is not installed.")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            for chunk in ollama.chat(
                model=self._model,
                messages=messages,
                options={"num_ctx": self._num_ctx, "temperature": self._temperature},
                stream=True,
            ):
                text = chunk.get("message", {}).get("content", "")
                if text:
                    yield text
        except Exception as exc:
            logger.error(f"[LLM] Stream error: {exc}")
            raise
