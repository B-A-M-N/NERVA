"""Declarative multi-step UI automation playbooks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from nerva.tools.browser_automation import BrowserAutomation


@dataclass
class PlaybookStep:
    """Single UI step with guard/check/selectors."""

    name: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    wait_for: Optional[str] = None  # selector to confirm before continuing
    wait_timeout: Optional[int] = None
    description: Optional[str] = None


@dataclass
class Playbook:
    """Collection of steps representing a workflow."""

    name: str
    steps: List[PlaybookStep]
    metadata: Dict[str, Any] = field(default_factory=dict)


class PlaybookRunner:
    """Executes Playbook steps through BrowserAutomation."""

    def __init__(self, browser: Optional[BrowserAutomation] = None) -> None:
        self.browser = browser or BrowserAutomation(headless=False)
        self._own_browser = browser is None

    async def run(self, playbook: Playbook) -> List[Dict[str, Any]]:
        if not self.browser.page:
            await self.browser.start()
        results: List[Dict[str, Any]] = []
        for step in playbook.steps:
            outcome = {"step": step.name, "action": step.action, "status": "pending"}
            try:
                if step.wait_for:
                    await self.browser.wait_for_selector(
                        step.wait_for, timeout=step.wait_timeout or 45000
                    )
                method = getattr(self.browser, step.action)
                result = await method(**step.params)
                outcome["result"] = result
                outcome["status"] = "ok"
            except Exception as exc:  # pragma: no cover - runtime failures
                outcome["status"] = "error"
                outcome["error"] = str(exc)
            results.append(outcome)
        if self._own_browser:
            await self.browser.stop()
        return results
