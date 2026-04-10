"""
memory/semantic.py — Embedding-based retrieval (semantic memory).

Wraps ChromaDB with a clean interface for storing and querying
research findings by semantic similarity.
"""
from __future__ import annotations
import uuid
from typing import List, Optional


class SemanticMemory:
    """
    Vector store backed by ChromaDB (ephemeral by default).

    Provides:
      store(text)                → add a document
      retrieve(query, k)        → top-k semantically similar docs
      clear_session()           → wipe the collection
    """

    def __init__(self, persistent: bool = False, path: Optional[str] = None):
        try:
            import chromadb
            if persistent and path:
                self._client = chromadb.PersistentClient(path=path)
            else:
                self._client = chromadb.EphemeralClient()
            self._collection = self._client.get_or_create_collection("semantic_memory")
            self._available = True
        except ImportError:
            self._available = False
            self._fallback: List[str] = []

    def store(self, text: str) -> None:
        """Add a document to semantic memory."""
        if not text or not text.strip():
            return
        if not self._available:
            self._fallback.append(text)
            if len(self._fallback) > 500:
                self._fallback = self._fallback[-500:]
            return
        try:
            self._collection.add(
                documents=[text.strip()],
                ids=[str(uuid.uuid4())]
            )
        except Exception:
            pass

    def retrieve(self, query: str, k: int = 5) -> str:
        """
        Retrieve top-k semantically similar documents.
        Returns a newline-joined string (suitable for LLM prompts).
        """
        if not query or not query.strip():
            return "No query provided."

        if not self._available:
            # Fallback: simple substring relevance
            scored = [(text, sum(1 for w in query.lower().split() if w in text.lower()))
                      for text in self._fallback]
            scored.sort(key=lambda x: x[1], reverse=True)
            results = [t for t, _ in scored[:k] if t]
            return "\n---\n".join(results) if results else "No relevant memory found."

        try:
            count = self._collection.count()
            if count == 0:
                return "No research yet."
            safe_k = min(k, count)
            results = self._collection.query(query_texts=[query], n_results=safe_k)
            docs = results.get("documents", [[]])[0]
            return "\n---\n".join(docs) if docs else "No relevant memory found."
        except Exception:
            return "Memory retrieval error."

    def score_relevance(self, query: str, text: str) -> float:
        """
        Naive relevance score (0–1) based on keyword overlap.
        Used when ChromaDB is unavailable or for quick pre-filtering.
        """
        q_words = set(query.lower().split())
        t_words = set(text.lower().split())
        if not q_words:
            return 0.0
        overlap = len(q_words & t_words)
        return min(overlap / len(q_words), 1.0)

    def clear_session(self) -> None:
        if not self._available:
            self._fallback.clear()
            return
        try:
            import chromadb
            self._client.delete_collection("semantic_memory")
            self._collection = self._client.get_or_create_collection("semantic_memory")
        except Exception:
            pass

    def count(self) -> int:
        if not self._available:
            return len(self._fallback)
        try:
            return self._collection.count()
        except Exception:
            return 0
