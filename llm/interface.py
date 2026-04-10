"""
llm/interface.py — Abstract LLM interface.

All provider implementations must subclass LLMInterface.
This decouples the agent from any specific model or library.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterator, List, Optional


class LLMInterface(ABC):
    """
    Abstract interface for language model providers.

    Implementors: GemmaProvider (Ollama), OpenAIProvider, etc.
    """

    @abstractmethod
    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """
        Blocking completion. Returns the full response as a string.

        Args:
            prompt:  The user-turn content.
            system:  Optional system prompt override.

        Returns:
            Model response text.

        Raises:
            ConnectionError: If the provider is unreachable after retries.
            RuntimeError:    On unexpected model errors.
        """
        ...

    @abstractmethod
    def stream(self, prompt: str, system: Optional[str] = None) -> Iterator[str]:
        """
        Streaming completion. Yields text chunks as they arrive.
        The caller is responsible for joining chunks.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider can accept requests right now."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the model being used."""
        ...
