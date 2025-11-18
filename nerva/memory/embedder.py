# nerva/memory/embedder.py
from __future__ import annotations
from typing import List
import logging
import hashlib
import os
import requests


logger = logging.getLogger(__name__)


class LocalEmbedder:
    """
    Local text embedder for semantic search.

    Uses Ollama's `/api/embeddings` endpoint so we stay aligned with the local
    stack. If Ollama or the embedding model is unavailable, falls back to a
    deterministic hashing scheme so vector search still returns consistent
    results.
    """

    def __init__(
        self,
        model_name: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.embedding_dim = 1536  # reasonable default; overwritten once we embed
        logger.info("[Embedder] Using Ollama embeddings model=%s base=%s", model_name, self.base_url)

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            List of floats representing the embedding vector
        """
        vector = self._embed_via_ollama(text)
        if vector is not None:
            self.embedding_dim = len(vector)
            return vector

        return _hash_embedding(text, dim=self.embedding_dim)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        vectors: List[List[float]] = []
        for text in texts:
            vector = self._embed_via_ollama(text)
            if vector is None:
                vector = _hash_embedding(text, dim=self.embedding_dim)
            else:
                self.embedding_dim = len(vector)
            vectors.append(vector)
        return vectors

    def _embed_via_ollama(self, text: str) -> List[float] | None:
        """Call Ollama embedding endpoint, handling connectivity issues gracefully."""
        payload = {"model": self.model_name, "prompt": text}
        try:
            resp = requests.post(f"{self.base_url}/api/embeddings", json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            vector = data.get("embedding")
            if isinstance(vector, list):
                return [float(v) for v in vector]
        except requests.exceptions.RequestException as exc:
            logger.debug("[Embedder] Ollama embedding error: %s", exc)
        except Exception as exc:  # pragma: no cover
            logger.debug("[Embedder] Unexpected embedding error: %s", exc)
        return None


def _hash_embedding(text: str, dim: int = 256) -> List[float]:
    """
    Deterministic fallback embedding using SHA256 hashing.

    Produces pseudo-random numbers in (-0.5, 0.5) so cosine similarity remains
    meaningful for ranking even though the vectors have no semantic grounding.
    """
    if not text:
        text = " "

    seed = text.encode("utf-8")
    values: List[float] = []
    counter = 0

    while len(values) < dim:
        counter_bytes = counter.to_bytes(4, byteorder="big", signed=False)
        digest = hashlib.sha256(seed + counter_bytes).digest()
        # Convert each byte to a float in range -0.5..0.5
        values.extend(((b / 255.0) - 0.5) for b in digest)
        counter += 1

    return values[:dim]
