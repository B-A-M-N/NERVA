# nerva/memory/schemas.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid


class MemoryType(Enum):
    """Types of memory items stored in NERVA's knowledge base."""
    Q_AND_A = auto()
    TODO = auto()
    REPO_INSIGHT = auto()
    DAILY_OP = auto()
    SYSTEM = auto()


@dataclass
class MemoryItem:
    """A single item in NERVA's memory/knowledge base."""
    id: str
    type: MemoryType
    created_at: datetime
    text: str  # Human-readable content
    meta: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None  # Embedding for semantic search
    tags: List[str] = field(default_factory=list)

    @staticmethod
    def new(
        mem_type: MemoryType,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> "MemoryItem":
        """Create a new memory item with auto-generated ID."""
        return MemoryItem(
            id=str(uuid.uuid4()),
            type=mem_type,
            created_at=datetime.utcnow(),
            text=text,
            meta=meta or {},
            tags=tags or [],
            vector=None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage/logging."""
        return {
            "id": self.id,
            "type": self.type.name,
            "created_at": self.created_at.isoformat(),
            "text": self.text,
            "meta": self.meta,
            "tags": self.tags,
            "has_vector": self.vector is not None,
        }
