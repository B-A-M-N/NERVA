"""Automated daily ops cycles (Phase V)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from nerva.agents.task_dispatcher import TaskDispatcher, TaskContext
from nerva.ops.collectors import (
    collect_github_notifications,
    collect_local_todos,
    collect_system_events,
    collect_sollol_status,
)

logger = logging.getLogger(__name__)


class DailyCycleManager:
    """
    Runs repeatable "ops cycles" composed of dispatcher commands + local checks.
    """

    def __init__(
        self,
        dispatcher: TaskDispatcher,
        interval_minutes: int = 60,
        commands: Optional[List[str]] = None,
    ) -> None:
        self.dispatcher = dispatcher
        self.interval = interval_minutes * 60
        self.commands = commands or [
            "Summarize today's calendar",
            "Summarize unread Gmail",
            "List latest GitHub notifications",
        ]
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._task:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            await self._task
            self._task = None

    async def run_cycle(self) -> None:
        logger.info("[DailyCycle] Starting cycle @ %s", datetime.utcnow())
        await self._run_collectors()
        for command in self.commands:
            try:
                await self.dispatcher.dispatch(
                    command,
                    TaskContext(source="daily_cycle", meta={"project": "daily_ops"}),
                )
            except Exception as exc:  # pragma: no cover - runtime issues
                logger.warning("[DailyCycle] Command '%s' failed: %s", command, exc)

    async def _loop(self) -> None:
        while self._running:
            await self.run_cycle()
            await asyncio.sleep(self.interval)

    async def _run_collectors(self) -> None:
        """Capture baseline inputs before dispatcher commands."""
        github = collect_github_notifications()
        todos = collect_local_todos()
        system = collect_system_events()
        sollol = collect_sollol_status()
        logger.info("[DailyCycle] Stats -> GitHub:%d TODOs:%d Logs:%d SOLLOL: %s", len(github), len(todos), len(system), sollol.get("reachable"))
