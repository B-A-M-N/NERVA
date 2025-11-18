# nerva/run_context.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from datetime import datetime


@dataclass
class RunContext:
    """
    Shared state passed through DAG nodes.

    Each workflow run gets its own RunContext instance.
    Nodes read inputs, perform operations, and write outputs to this context.
    """
    mode: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Raw inputs
    voice_text: Optional[str] = None
    screenshot_bytes: Optional[bytes] = None
    repo_question: Optional[str] = None
    repo_root: Optional[str] = None

    # Intermediate artifacts
    asr_transcript: Optional[str] = None
    intent: Optional[str] = None
    llm_raw_response: Optional[str] = None

    # Screen understanding
    screen_analysis: Dict[str, Any] = field(default_factory=dict)

    # Daily ops
    daily_inputs: Dict[str, Any] = field(default_factory=dict)
    daily_summary: Optional[str] = None
    daily_tasks: List[Dict[str, Any]] = field(default_factory=list)

    # Repo assistant
    repo_context: Dict[str, Any] = field(default_factory=dict)
    repo_answer: Optional[str] = None

    # Memory
    memory_items: List[Dict[str, Any]] = field(default_factory=list)

    # Misc / extensibility
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context for logging or debugging."""
        return {
            "mode": self.mode,
            "created_at": self.created_at.isoformat(),
            "intent": self.intent,
            "screen_analysis": self.screen_analysis,
            "daily_summary": self.daily_summary,
            "repo_answer": self.repo_answer,
            "memory_items": len(self.memory_items),
        }
