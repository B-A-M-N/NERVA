"""Intermediate UI planning layer between vision intent and concrete actions."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

from nerva.tools.browser_automation import BrowserAutomation

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from nerva.agents.vision_action_agent import BrowserAction


logger = logging.getLogger(__name__)


@dataclass
class UIStateExpectation:
    """Guard/validation requirement for a selector."""

    label: str
    selector: str
    state: str = "visible"
    timeout: int = 6000
    description: Optional[str] = None


@dataclass
class UIPlan:
    """Plan describing guards, action, and validations."""

    action_type: str
    target: str
    preconditions: List[UIStateExpectation] = field(default_factory=list)
    postconditions: List[UIStateExpectation] = field(default_factory=list)
    max_retries: int = 2


class UIPlannerError(RuntimeError):
    """Raised when planner retries are exhausted."""

    def __init__(self, summary: Dict[str, Any], message: str) -> None:
        super().__init__(message)
        self.summary = summary


class UIPlanner:
    """
    Predicts the immediate UI transitions required for an action and validates them.

    Responsibilities:
      * Check that the described target is reachable before the action
      * Execute the action via a provided executor callback
      * Verify expected postconditions (results list, inbox grid, etc.)
      * Attempt structured recovery (scroll, wait, reload) before failing
    """

    _RESULT_PATTERNS: Tuple[Tuple[Tuple[str, ...], str, int, str], ...] = (
        (("search", "lookup", "phone", "google"), "#search", 60000, "Google results loaded"),
        (("gmail", "inbox", "email"), "div[role='main']", 45000, "Gmail inbox ready"),
        (("calendar", "meeting"), "div[role='grid']", 45000, "Calendar grid visible"),
        (("drive", "file"), "div[data-target='doclist']", 45000, "Drive file list ready"),
    )

    _STAGE_STRATEGIES: Dict[str, Sequence[str]] = {
        "guard": ("scroll", "wait_short", "reload"),
        "post": ("wait_long", "scroll", "reload"),
    }

    def __init__(
        self,
        browser: BrowserAutomation,
        executor: Optional[Callable[["BrowserAction"], Awaitable[None]]] = None,
        *,
        max_retries: int = 2,
    ) -> None:
        self.browser = browser
        self.executor = executor
        self.max_retries = max_retries

    async def run(self, action: "BrowserAction") -> Dict[str, Any]:
        """Execute the action with guard/validation/recovery phases."""
        if not self.executor:
            raise RuntimeError("UIPlanner requires an executor callback")

        plan = self._build_plan(action)
        summary: Dict[str, Any] = {
            "action": action.action_type,
            "target": action.target,
            "attempts": [],
            "preconditions": [exp.__dict__ for exp in plan.preconditions],
            "postconditions": [exp.__dict__ for exp in plan.postconditions],
        }

        attempt = 0
        while attempt <= plan.max_retries:
            attempt += 1
            attempt_log: Dict[str, Any] = {"attempt": attempt}

            guards_ok, failing_guard = await self._verify_expectations(
                plan.preconditions, attempt_log, "preconditions"
            )
            if not guards_ok:
                attempt_log["status"] = "guard_failed"
                recovered = await self._attempt_recovery("guard", failing_guard, attempt_log)
                summary["attempts"].append(attempt_log)
                if recovered:
                    continue
                reason = f"Target not reachable ({failing_guard.selector if failing_guard else 'unknown'})"
                summary.update({"status": "failed", "reason": reason})
                raise UIPlannerError(summary, reason)

            try:
                await self.executor(action)
            except Exception:
                attempt_log["status"] = "action_failed"
                summary["attempts"].append(attempt_log)
                summary.update({"status": "failed", "reason": "executor raised"})
                raise

            validations_ok, failing_validation = await self._verify_expectations(
                plan.postconditions, attempt_log, "postconditions"
            )
            if validations_ok:
                attempt_log["status"] = "ok"
                summary["attempts"].append(attempt_log)
                summary["status"] = "ok"
                summary["attempt"] = attempt
                return summary

            attempt_log["status"] = "postcondition_failed"
            recovered = await self._attempt_recovery("post", failing_validation, attempt_log)
            summary["attempts"].append(attempt_log)
            if recovered:
                continue

            reason = (
                f"Postcondition not met ({failing_validation.selector if failing_validation else 'unknown'})"
            )
            summary.update({"status": "failed", "reason": reason})
            raise UIPlannerError(summary, reason)

        reason = "Planner retries exhausted"
        summary.update({"status": "failed", "reason": reason})
        raise UIPlannerError(summary, reason)

    def _build_plan(self, action: "BrowserAction") -> UIPlan:
        """Synthesize plan heuristics from action metadata."""
        plan = UIPlan(action_type=action.action_type, target=action.target, max_retries=self.max_retries)

        target_selector = self._selector_candidates(action.target)
        if target_selector:
            plan.preconditions.append(
                UIStateExpectation(
                    label="target_visible",
                    selector=target_selector[0],
                    timeout=15000,
                    description=f"Ensure target '{action.target}' is visible",
                )
            )

        plan.postconditions.extend(self._predict_postconditions(action))
        if not plan.postconditions:
            plan.postconditions.append(
                UIStateExpectation(
                    label="page_stable",
                    selector="body",
                    timeout=8000,
                    description="Ensure page finished updating",
                )
            )
        return plan

    async def _verify_expectations(
        self,
        expectations: Sequence[UIStateExpectation],
        attempt_log: Dict[str, Any],
        key: str,
    ) -> Tuple[bool, Optional[UIStateExpectation]]:
        """Check guards or validations."""
        results: List[Dict[str, Any]] = []
        for exp in expectations:
            ok = await self.browser.wait_for_selector(exp.selector, timeout=exp.timeout, state=exp.state)
            results.append(
                {
                    "label": exp.label,
                    "selector": exp.selector,
                    "state": exp.state,
                    "timeout": exp.timeout,
                    "status": "ok" if ok else "missing",
                }
            )
            if not ok:
                attempt_log[key] = results
                return False, exp

        attempt_log[key] = results
        return True, None

    async def _attempt_recovery(
        self,
        stage: str,
        failing: Optional[UIStateExpectation],
        attempt_log: Dict[str, Any],
    ) -> bool:
        """Run recovery strategies for the given stage."""
        strategies = self._STAGE_STRATEGIES.get(stage, ())
        if not strategies or not self.browser.page:
            return False

        recoveries: List[Dict[str, Any]] = []
        for strategy in strategies:
            success = await self._execute_recovery_strategy(strategy)
            record: Dict[str, Any] = {"strategy": strategy, "status": "ok" if success else "skipped"}
            if success and failing:
                ok = await self.browser.wait_for_selector(
                    failing.selector,
                    timeout=min(failing.timeout, 8000),
                    state=failing.state,
                )
                record["recheck"] = ok
                if ok:
                    recoveries.append(record)
                    attempt_log["recovery"] = recoveries
                    return True
            recoveries.append(record)

        attempt_log["recovery"] = recoveries
        return False

    async def _execute_recovery_strategy(self, strategy: str) -> bool:
        """Perform a single recovery routine."""
        page = self.browser.page
        if not page:
            return False

        if strategy == "scroll":
            await page.mouse.wheel(0, 500)
            return True
        if strategy == "wait_short":
            await asyncio.sleep(1.0)
            return True
        if strategy == "wait_long":
            await asyncio.sleep(2.5)
            return True
        if strategy == "reload":
            await page.reload()
            return True

        logger.debug("Unknown recovery strategy: %s", strategy)
        return False

    def _selector_candidates(self, description: str) -> List[str]:
        """Heuristically derive selectors from a natural language description."""
        if not description:
            return []

        desc_lower = description.lower()
        selectors: List[str] = []

        if "button" in desc_lower:
            for kw in self._extract_keywords(description):
                selectors.extend(
                    [
                        f"button:has-text('{kw}')",
                        f"a:has-text('{kw}')",
                        f"input[type='submit']:has-text('{kw}')",
                    ]
                )
        elif "link" in desc_lower:
            for kw in self._extract_keywords(description):
                selectors.append(f"a:has-text('{kw}')")
        elif any(word in desc_lower for word in ("field", "input", "search")):
            selectors.extend(
                [
                    "input[type='search']",
                    "textarea[name='q']",
                ]
            )

        if not selectors:
            for kw in self._extract_keywords(description):
                selectors.extend(
                    [
                        f"text={kw}",
                        f"*:has-text('{kw}')",
                    ]
                )

        return selectors

    def _extract_keywords(self, description: str) -> List[str]:
        stop_words = {
            "the",
            "a",
            "an",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "button",
            "link",
            "input",
            "field",
            "box",
            "element",
        }
        words = description.lower().split()
        return [w.strip(".,!?\"'") for w in words if w and w not in stop_words][:3]

    def _predict_postconditions(self, action: "BrowserAction") -> List[UIStateExpectation]:
        """Guess which selectors should appear after the action."""
        haystack = f"{action.target} {action.value or ''}".lower()
        expectations: List[UIStateExpectation] = []
        for keywords, selector, timeout, description in self._RESULT_PATTERNS:
            if any(keyword in haystack for keyword in keywords):
                expectations.append(
                    UIStateExpectation(
                        label=selector,
                        selector=selector,
                        timeout=timeout,
                        description=description,
                    )
                )
        return expectations
