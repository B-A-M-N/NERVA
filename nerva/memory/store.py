# nerva/memory/store.py
from __future__ import annotations
from typing import List, Iterable, Tuple, Optional
import threading
import logging
import math

from .schemas import MemoryItem, MemoryType


logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Minimal in-memory knowledge store.

    TODO: Replace with SQLite + FAISS/Chroma for persistence and vector search.
    """

    def __init__(self) -> None:
        self._items: List[MemoryItem] = []
        self._lock = threading.Lock()
        logger.info("[MemoryStore] Initialized (in-memory)")

    def add(self, item: MemoryItem) -> None:
        """Add a single memory item."""
        with self._lock:
            self._items.append(item)
        logger.debug(f"[MemoryStore] Added item: {item.id} ({item.type.name})")

    def bulk_add(self, items: Iterable[MemoryItem]) -> None:
        """Add multiple memory items at once."""
        items_list = list(items)
        with self._lock:
            self._items.extend(items_list)
        logger.info(f"[MemoryStore] Bulk added {len(items_list)} items")

    def all(self) -> List[MemoryItem]:
        """Retrieve all memory items."""
        with self._lock:
            return list(self._items)

    def filter_by_type(self, mem_type: MemoryType, limit: int = 100) -> List[MemoryItem]:
        """Get all items of a specific type."""
        with self._lock:
            results = [i for i in self._items if i.type == mem_type]
        return results[:limit]

    def search_text_contains(self, needle: str, limit: int = 20) -> List[MemoryItem]:
        """Simple text search (case-insensitive substring match)."""
        needle_lower = needle.lower()
        with self._lock:
            results = [i for i in self._items if needle_lower in i.text.lower()]
        return results[:limit]

    def search_by_tags(self, tags: List[str], limit: int = 20) -> List[MemoryItem]:
        """Search for items with any of the given tags."""
        tag_set = set(tags)
        with self._lock:
            results = [i for i in self._items if tag_set & set(i.tags)]
        return results[:limit]

    def search_by_vector(
        self,
        vector: List[float],
        limit: int = 10,
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Vector similarity search (cosine similarity).

        Args:
            vector: Query embedding
            limit: Number of results to return

        Returns:
            List of (MemoryItem, similarity) tuples sorted by score.
        """
        if not vector:
            return []

        with self._lock:
            candidates = [item for item in self._items if item.vector]

        if not candidates:
            return []

        scores: List[Tuple[MemoryItem, float]] = []
        for item in candidates:
            similarity = _cosine_similarity(vector, item.vector or [])
            if similarity > 0:
                scores.append((item, similarity))

        scores.sort(key=lambda pair: pair[1], reverse=True)
        return scores[:limit]

    def clear(self) -> None:
        """Clear all memory items (use with caution)."""
        with self._lock:
            count = len(self._items)
            self._items.clear()
        logger.warning(f"[MemoryStore] Cleared {count} items")


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b:
        return 0.0

    if len(a) != len(b):
        length = min(len(a), len(b))
        a = a[:length]
        b = b[:length]

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)
