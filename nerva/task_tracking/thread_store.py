"""Threaded task/project memory for NERVA."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def _now() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class TaskEntry:
    """Single update inside a task thread."""

    entry_id: str
    timestamp: str
    author: str
    text: str
    metadata: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_text(
        cls,
        text: str,
        author: str = "nerva",
        metadata: Optional[Dict[str, str]] = None,
    ) -> "TaskEntry":
        return cls(
            entry_id=str(uuid.uuid4()),
            timestamp=_now(),
            author=author,
            text=text,
            metadata=metadata or {},
        )


@dataclass
class TaskThread:
    """Represents a project or task thread with running history."""

    thread_id: str
    project: str
    title: str
    status: str = "open"
    owner: Optional[str] = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    tags: List[str] = field(default_factory=list)
    entries: List[TaskEntry] = field(default_factory=list)

    def add_entry(self, text: str, author: str = "nerva", metadata: Optional[Dict[str, str]] = None) -> TaskEntry:
        entry = TaskEntry.from_text(text=text, author=author, metadata=metadata)
        self.entries.append(entry)
        self.updated_at = _now()
        return entry

    def to_dict(self) -> Dict:
        return {
            "thread_id": self.thread_id,
            "project": self.project,
            "title": self.title,
            "status": self.status,
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "entries": [entry.__dict__ for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TaskThread":
        thread = cls(
            thread_id=data["thread_id"],
            project=data["project"],
            title=data["title"],
            status=data.get("status", "open"),
            owner=data.get("owner"),
            created_at=data.get("created_at", _now()),
            updated_at=data.get("updated_at", _now()),
            tags=data.get("tags", []),
        )
        thread.entries = [
            TaskEntry(
                entry_id=entry["entry_id"],
                timestamp=entry["timestamp"],
                author=entry.get("author", "unknown"),
                text=entry["text"],
                metadata=entry.get("metadata", {}),
            )
            for entry in data.get("entries", [])
        ]
        return thread


class ThreadStore:
    """Simple JSON-backed persistence layer for task threads."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path or Path.home() / ".nerva" / "threads.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._threads: Dict[str, TaskThread] = {}
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            raw = json.loads(self.storage_path.read_text() or "{}")
            for thread_id, thread_obj in raw.items():
                self._threads[thread_id] = TaskThread.from_dict(thread_obj)
        except json.JSONDecodeError:
            self._threads = {}

    def _save(self) -> None:
        data = {thread_id: thread.to_dict() for thread_id, thread in self._threads.items()}
        self.storage_path.write_text(json.dumps(data, indent=2))

    def list_threads(self, project: Optional[str] = None, status: Optional[str] = None) -> List[TaskThread]:
        threads = list(self._threads.values())
        if project:
            threads = [t for t in threads if t.project == project]
        if status:
            threads = [t for t in threads if t.status == status]
        return sorted(threads, key=lambda t: t.updated_at, reverse=True)

    def get(self, thread_id: str) -> Optional[TaskThread]:
        return self._threads.get(thread_id)

    def create(
        self,
        project: str,
        title: str,
        owner: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> TaskThread:
        thread = TaskThread(
            thread_id=str(uuid.uuid4()),
            project=project,
            title=title,
            owner=owner,
            tags=tags or [],
        )
        self._threads[thread.thread_id] = thread
        self._save()
        return thread

    def add_entry(
        self,
        thread_id: str,
        text: str,
        author: str = "nerva",
        metadata: Optional[Dict[str, str]] = None,
    ) -> TaskEntry:
        thread = self._threads[thread_id]
        entry = thread.add_entry(text=text, author=author, metadata=metadata)
        self._save()
        return entry

    def update_status(self, thread_id: str, status: str) -> None:
        if thread_id in self._threads:
            self._threads[thread_id].status = status
            self._threads[thread_id].updated_at = _now()
            self._save()
