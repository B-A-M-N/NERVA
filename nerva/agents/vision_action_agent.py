"""VisionActionAgent: Vision → Reasoning → Action loop for browser automation."""
from __future__ import annotations
import asyncio
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from nerva.vision.qwen_vision import QwenVision
from nerva.tools.browser_automation import BrowserAutomation
from nerva.automation.playbooks import Playbook, PlaybookRunner
from nerva.automation.playbooks_lookup import build_lookup_playbook
from nerva.automation.ui_planner import UIPlanner, UIPlannerError

logger = logging.getLogger(__name__)
PHONE_REGEX = re.compile(r"(?:\+?1[-.\s]*)?(?:\(\d{3}\)|\d{3})[-.\s]*\d{3}[-.\s]*\d{4}")


@dataclass
class BrowserAction:
    """Represents a browser action parsed from vision analysis."""
    action_type: str  # click, type, scroll, navigate, wait, complete
    target: str
    value: Optional[str] = None
    reason: str = ""
    confidence: str = "medium"

    @property
    def is_complete(self) -> bool:
        """Check if action indicates task completion."""
        return self.action_type == "complete"


class VisionActionAgent:
    """
    Autonomous agent that combines vision and browser automation.

    Loop:
    1. Screenshot current browser state
    2. Vision model analyzes screenshot and determines next action
    3. Parse action from vision response
    4. Execute action via browser automation
    5. Verify result (optional)
    6. Repeat until task complete
    """

    def __init__(
        self,
        vision: Optional[QwenVision] = None,
        browser: Optional[BrowserAutomation] = None,
        max_steps: int = 20,
        verify_actions: bool = False,
        answer_task: bool = True,
    ):
        """
        Initialize VisionActionAgent.

        Args:
            vision: QwenVision instance (created if not provided)
            browser: BrowserAutomation instance (created if not provided)
            max_steps: Maximum steps before aborting
            verify_actions: Whether to verify each action result
        """
        self.vision = vision or QwenVision()  # Uses config defaults (SOLLOL routing)
        self.browser = browser or BrowserAutomation(headless=False)
        self.max_steps = max_steps
        self.verify_actions = verify_actions
        self.answer_task = answer_task
        self._screenshot_dir = Path("/tmp/nerva_screenshots")
        self._screenshot_dir.mkdir(exist_ok=True)
        logger.info("[VisionActionAgent] Initialized")
        self._playbook_runner = PlaybookRunner(browser=self.browser)
        self._planner = UIPlanner(browser=self.browser, executor=self._perform_action)

    async def execute_task(
        self,
        task: str,
        starting_url: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Execute a task using vision-guided browser automation.

        Args:
            task: Task description (e.g., "Search for Python tutorials on Google")
            starting_url: Optional URL to start from

        Returns:
            Task execution result with history
        """
        logger.info(f"[VisionActionAgent] Starting task: {task}")
        print(f"\n🌐 Starting browser for task: {task}")

        # Start browser
        await self.browser.start()

        try:
            # Navigate to starting URL if provided
            if starting_url:
                print(f"   → Navigating to: {starting_url}")
                await self.browser.navigate(starting_url)
                await asyncio.sleep(1)  # Let page load
            else:
                # Start with Google search if no URL provided
                print(f"   → No starting URL, opening Google...")
                await self.browser.navigate("https://www.google.com")
                await asyncio.sleep(1)

            # Execute task loop
            history = []
            step = 0

            while step < self.max_steps:
                step += 1
                logger.info(f"[VisionActionAgent] Step {step}/{self.max_steps}")

                # 1. Capture screenshot
                screenshot_path = self._screenshot_dir / f"step_{step:02d}.png"
                await self._take_screenshot(screenshot_path)

                # 2. Analyze with vision model
                vision_response = await self.vision.extract_browser_action(
                    screenshot_path,
                    task=task,
                )

                logger.debug(f"[VisionActionAgent] Vision response:\n{vision_response}")

                # 3. Parse action
                action = self._parse_action(vision_response)

                # Log action
                history.append({
                    "step": step,
                    "screenshot": str(screenshot_path),
                    "vision_response": vision_response,
                    "action": action,
                })

                logger.info(
                    f"[VisionActionAgent] Action: {action.action_type} | "
                    f"Target: {action.target} | Confidence: {action.confidence}"
                )

                # Show user what action is being taken
                print(f"   Step {step}: {action.action_type.upper()} - {action.target} ({action.confidence})")

                # 4. Check if task is complete
                if action.is_complete:
                    logger.info(f"[VisionActionAgent] Task complete: {action.reason}")
                    info = None
                    if self.answer_task:
                        info = await self._answer_task(task)
                    return {
                        "status": "success",
                        "reason": action.reason,
                        "steps": step,
                        "history": history,
                        "answer": info,
                    }

                # 5. Execute action
                try:
                    planner_info = await self._planner.run(action)
                    history[-1]["planner"] = planner_info
                except UIPlannerError as planner_exc:
                    logger.error("[VisionActionAgent] Planner failed: %s", planner_exc)
                    history[-1]["planner"] = planner_exc.summary
                    history[-1]["error"] = str(planner_exc)
                    if step >= self.max_steps - 1:
                        break
                    continue
                except Exception as e:
                    logger.error(f"[VisionActionAgent] Action failed: {e}")
                    history[-1]["error"] = str(e)

                    if step >= self.max_steps - 1:
                        break

                # 6. Wait for page to update
                await asyncio.sleep(1)

            # Max steps reached
            logger.warning(f"[VisionActionAgent] Max steps ({self.max_steps}) reached")
            info = None
            if self.answer_task:
                info = await self._answer_task(task)
            return {
                "status": "incomplete",
                "reason": f"Max steps ({self.max_steps}) reached",
                "steps": step,
                "history": history,
                "answer": info,
            }

        finally:
            # Clean up browser
            await self.browser.stop()

    async def run_playbook(self, playbook: Playbook) -> List[Dict[str, Any]]:
        """
        Execute a predefined UI playbook using the shared browser.
        Useful for stateful multi-step flows (logins, approvals, etc.).
        """
        return await self._playbook_runner.run(playbook)

    async def research_topic(self, query: str, result_count: int = 3) -> Dict[str, Any]:
        from nerva.automation.playbooks_research import build_research_playbook

        playbook = build_research_playbook(query, result_count=result_count)
        steps = await self.run_playbook(playbook)
        answer = None
        if self.answer_task:
            answer = await self._answer_task("Summarize the key findings from the captured search results.")
        return {
            "status": "success",
            "reason": f"Research run for {query}",
            "playbook": steps,
            "answer": answer,
        }

    async def lookup_phone_number(self, query: str) -> Dict[str, Any]:
        """
        Use a deterministic playbook to load Google results and open the first hit,
        then extract phone numbers directly from the page with a regex.
        """
        playbook = build_lookup_playbook(query)
        results = await self.run_playbook(playbook)
        phone = await self._extract_phone_number(query)
        answer = None
        if phone:
            answer = f"The phone number for {query} is {phone}."
        elif self.answer_task:
            answer = await self._answer_task(f"What is the phone number for {query}?")
        return {
            "status": "success",
            "reason": f"Lookup completed for {query}",
            "playbook": results,
            "answer": answer,
            "phone": phone,
        }

    async def _take_screenshot(self, path: Path) -> None:
        """Take screenshot of current browser state."""
        if not self.browser.page:
            raise RuntimeError("Browser page not initialized")

        await self.browser.page.screenshot(path=str(path))
        logger.debug(f"[VisionActionAgent] Screenshot saved: {path}")

    def _parse_action(self, vision_response: str) -> BrowserAction:
        """
        Parse action from vision model response.

        Expected format:
        ACTION: click
        TARGET: search button in header
        VALUE: N/A
        REASON: need to click search to enter query
        CONFIDENCE: high
        """
        # Extract fields using regex
        action_type = self._extract_field(vision_response, "ACTION", default="wait")
        target = self._extract_field(vision_response, "TARGET", default="")
        value = self._extract_field(vision_response, "VALUE", default=None)
        reason = self._extract_field(vision_response, "REASON", default="")
        confidence = self._extract_field(vision_response, "CONFIDENCE", default="medium")

        # Clean up
        action_type = action_type.lower().strip()
        if value and value.upper() == "N/A":
            value = None

        return BrowserAction(
            action_type=action_type,
            target=target,
            value=value,
            reason=reason,
            confidence=confidence,
        )

    async def _extract_phone_number(self, query: str) -> Optional[str]:
        """Inspect the active page body and pull the best matching phone number."""
        if not self.browser.page:
            return None

        try:
            content = await self.browser.page.inner_text("body")
        except Exception as exc:  # pragma: no cover - playwright runtime failure
            logger.warning("[VisionActionAgent] Failed to read body text: %s", exc)
            return None

        matches = list(PHONE_REGEX.finditer(content))
        if not matches:
            return None

        lowered = content.lower()
        query_tokens = [token for token in re.split(r"\W+", query.lower()) if token]
        best_score = -1
        best_phone: Optional[str] = None

        for match in matches:
            raw = match.group(0).strip()
            digits = re.sub(r"\D", "", raw)
            score = 1
            if len(digits) >= 10:
                score += 1
            start, end = match.span()
            snippet = lowered[max(0, start - 80) : min(len(lowered), end + 80)]
            if any(token in snippet for token in query_tokens):
                score += 2
            if score > best_score:
                best_score = score
                best_phone = self._format_phone(digits)

        if best_phone:
            logger.info("[VisionActionAgent] Extracted phone %s for query '%s'", best_phone, query)
        return best_phone

    def _format_phone(self, digits: str) -> str:
        """Normalize phone number digits into (XXX) XXX-XXXX when possible."""
        digits = digits[-10:]
        if len(digits) != 10:
            return digits
        area, prefix, line = digits[:3], digits[3:6], digits[6:]
        return f"({area}) {prefix}-{line}"

    async def _answer_task(self, task: str) -> Optional[str]:
        """Run a final screenshot through the vision QA prompt."""
        if not self.browser.page:
            return None
        screenshot_path = self._screenshot_dir / "final_answer.png"
        await self.browser.page.screenshot(path=str(screenshot_path), full_page=True)
        try:
            response = await self.vision.answer_question(screenshot_path, task)
            return response
        except Exception as exc:  # pragma: no cover - vision failures
            logger.warning("[VisionActionAgent] Answer extraction failed: %s", exc)
            return None

    def _extract_field(self, text: str, field_name: str, default: str = "") -> str:
        """Extract field value from structured text."""
        # Match "FIELD: value" or "FIELD: [value]"
        pattern = rf"{field_name}:\s*\[?([^\]\n]+)\]?"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match.group(1).strip()

        return default

    async def _perform_action(self, action: BrowserAction) -> None:
        """
        Execute browser action.

        Args:
            action: Parsed browser action
        """
        if not self.browser.page:
            raise RuntimeError("Browser page not initialized")

        page = self.browser.page

        if action.action_type == "click":
            # Try to click element by description
            await self._click_by_description(action.target)

        elif action.action_type == "type":
            # Type text into focused element
            if action.value:
                await page.keyboard.type(action.value)
            else:
                logger.warning("[VisionActionAgent] Type action has no value")

        elif action.action_type == "scroll":
            # Scroll page
            direction = action.target.lower()
            if "down" in direction:
                await page.keyboard.press("PageDown")
            elif "up" in direction:
                await page.keyboard.press("PageUp")
            else:
                await page.mouse.wheel(0, 300)  # Default scroll

        elif action.action_type == "navigate":
            # Navigate to URL
            url = action.target
            if not url.startswith("http"):
                url = f"https://{url}"
            await page.goto(url)

        elif action.action_type == "wait":
            # Wait for specified duration or page load
            duration = 2  # Default wait
            if action.value and action.value.isdigit():
                duration = int(action.value)
            await asyncio.sleep(duration)

        else:
            logger.warning(f"[VisionActionAgent] Unknown action type: {action.action_type}")

    async def _click_by_description(self, description: str) -> None:
        """
        Click element by description using heuristics.

        Args:
            description: Natural language description of element
        """
        if not self.browser.page:
            raise RuntimeError("Browser page not initialized")

        page = self.browser.page

        # Extract keywords from description
        desc_lower = description.lower()

        # Try common patterns
        selectors = []

        # Check for specific element types
        if "button" in desc_lower:
            # Look for buttons containing keywords
            keywords = self._extract_keywords(description)
            for kw in keywords:
                selectors.extend([
                    f"button:has-text('{kw}')",
                    f"input[type='button']:has-text('{kw}')",
                    f"input[type='submit']:has-text('{kw}')",
                    f"a:has-text('{kw}')",
                ])

        elif "link" in desc_lower:
            keywords = self._extract_keywords(description)
            for kw in keywords:
                selectors.append(f"a:has-text('{kw}')")

        elif "input" in desc_lower or "field" in desc_lower or "search" in desc_lower:
            # Look for input fields
            if "search" in desc_lower:
                selectors.extend([
                    "input[type='search']",
                    "input[placeholder*='search' i]",
                    "input[name*='search' i]",
                ])
            else:
                keywords = self._extract_keywords(description)
                for kw in keywords:
                    selectors.extend([
                        f"input[placeholder*='{kw}' i]",
                        f"input[name*='{kw}' i]",
                    ])

        else:
            # Generic text search
            keywords = self._extract_keywords(description)
            for kw in keywords:
                selectors.extend([
                    f"text={kw}",
                    f"*:has-text('{kw}')",
                ])

        # Try each selector
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    logger.debug(f"[VisionActionAgent] Clicking with selector: {selector}")
                    await element.click(timeout=2000)
                    return
            except Exception as e:
                logger.debug(f"[VisionActionAgent] Selector failed: {selector} ({e})")
                continue

        # Fallback: click by text content (case-insensitive)
        try:
            await page.get_by_text(description, exact=False).first.click(timeout=2000)
            logger.debug(f"[VisionActionAgent] Clicked by text: {description}")
        except Exception as e:
            logger.warning(f"[VisionActionAgent] Could not find element: {description} ({e})")
            raise ValueError(f"Could not find element: {description}")

    def _extract_keywords(self, description: str) -> List[str]:
        """Extract meaningful keywords from description."""
        # Remove common words
        stop_words = {
            "the", "a", "an", "in", "on", "at", "to", "for", "of", "with",
            "button", "link", "input", "field", "box", "element",
        }

        # Split and filter
        words = description.lower().split()
        keywords = [w.strip(".,!?\"'") for w in words if w not in stop_words]

        return keywords[:3]  # Return top 3 keywords
