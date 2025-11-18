# nerva/types.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional, List
from datetime import datetime
import uuid


class EventType(Enum):
    """All event types in the NERVA system."""
    VOICE_COMMAND = auto()
    SCREEN_CAPTURE = auto()
    SCREEN_ANALYSIS = auto()
    REPO_QUERY = auto()
    REPO_ANSWER = auto()
    DAILY_OPS_TICK = auto()
    DAILY_SUMMARY_READY = auto()
    MEMORY_WRITE = auto()
    MEMORY_QUERY = auto()
    SYSTEM_LOG = auto()


@dataclass
class Event:
    """Core event structure for pub/sub communication."""
    id: str
    type: EventType
    payload: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def new(event_type: EventType, payload: Dict[str, Any]) -> "Event":
        """Create a new event with auto-generated ID."""
        return Event(id=str(uuid.uuid4()), type=event_type, payload=payload)


@dataclass
class NervaContext:
    """
    Global context NERVA can use to reason about 'where' it is.
    This gets injected into prompts and updated by agents.
    """
    active_repo: Optional[str] = None
    active_window_title: Optional[str] = None
    active_mode: Optional[str] = None  # "screen", "voice", "ops", "repo"
    node_status: Dict[str, Any] = field(default_factory=dict)
    last_screen_analysis: Optional[Dict[str, Any]] = None
    recent_commands: List[str] = field(default_factory=list)

    # SOLLOL/Hydra state can be injected here
    sollol_nodes: Dict[str, Any] = field(default_factory=dict)
    hydra_context: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context for LLM prompts."""
        return {
            "active_repo": self.active_repo,
            "active_window": self.active_window_title,
            "mode": self.active_mode,
            "nodes": self.node_status,
            "recent_commands": self.recent_commands[-5:],  # last 5 only
        }
