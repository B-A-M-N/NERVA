"""
Browser Automation Module for NERVA

Provides programmatic browser control for:
- Web navigation and interaction
- Authenticated sessions (via persistent context)
- Form filling and data extraction
- Screenshot capture
- Complex multi-step workflows

Uses Playwright for cross-browser automation.
"""
from __future__ import annotations
from typing import Optional, Dict, List, Any
from pathlib import Path
import logging
import asyncio

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    Browser = None
    BrowserContext = None
    Page = None


logger = logging.getLogger(__name__)


class BrowserAutomation:
    """
    Browser automation client for NERVA.

    Features:
    - Persistent context: Use existing logged-in sessions from Chrome/Firefox
    - Headless/headed modes: Run with or without visible browser
    - Navigation: Go to URLs, click elements, fill forms
    - Extraction: Get page content, take screenshots
    - Workflows: Execute multi-step browser tasks
    """

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        user_data_dir: Optional[str] = None,
    ):
        """
        Initialize browser automation.

        Args:
            headless: Run browser in headless mode (no UI)
            browser_type: Browser to use ("chromium", "firefox", "webkit")
            user_data_dir: Path to existing browser profile for persistent context
                          (e.g., ~/.config/google-chrome/Default for Chrome)
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright not installed. Install with: pip install playwright && playwright install chromium"
            )

        self.headless = headless
        self.browser_type = browser_type
        self.user_data_dir = user_data_dir

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._is_persistent = user_data_dir is not None

    async def start(self):
        """Start the browser and create a page."""
        self.playwright = await async_playwright().start()

        if self.browser_type == "chromium":
            browser_factory = self.playwright.chromium
        elif self.browser_type == "firefox":
            browser_factory = self.playwright.firefox
        elif self.browser_type == "webkit":
            browser_factory = self.playwright.webkit
        else:
            raise ValueError(f"Unknown browser type: {self.browser_type}")

        if self._is_persistent:
            # Use persistent context to leverage existing logged-in sessions
            logger.info(f"🌐 Launching persistent context from {self.user_data_dir}")
            self.context = await browser_factory.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ]
            )
            # Get the first page or create new one
            pages = self.context.pages
            self.page = pages[0] if pages else await self.context.new_page()
        else:
            # Regular browser launch
            logger.info(f"🌐 Launching {self.browser_type} browser (headless={self.headless})")
            self.browser = await browser_factory.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                ]
            )
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()

        logger.info("✅ Browser ready")

    async def stop(self):
        """Stop the browser."""
        if self.page:
            await self.page.close()
        if self.context and not self._is_persistent:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logger.info("🛑 Browser stopped")

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> Dict[str, Any]:
        """
        Navigate to a URL.

        Args:
            url: URL to navigate to
            wait_until: When to consider navigation complete
                       ("load", "domcontentloaded", "networkidle")

        Returns:
            Response info
        """
        if not self.page:
            await self.start()

        logger.info(f"📍 Navigating to {url}")
        response = await self.page.goto(url, wait_until=wait_until)

        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "status": response.status if response else None,
        }

    async def click(self, selector: str, timeout: float = 30000) -> bool:
        """
        Click an element.

        Args:
            selector: CSS selector or text selector
            timeout: Maximum wait time in milliseconds

        Returns:
            True if successful
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        logger.info(f"🖱️  Clicking: {selector}")
        try:
            await self.page.click(selector, timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    async def fill(self, selector: str, text: str, timeout: float = 30000) -> bool:
        """
        Fill a form field.

        Args:
            selector: CSS selector for the input field
            text: Text to fill
            timeout: Maximum wait time in milliseconds

        Returns:
            True if successful
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        logger.info(f"✏️  Filling '{selector}' with '{text}'")
        try:
            await self.page.fill(selector, text, timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"Fill failed: {e}")
            return False

    async def get_text(self, selector: str, timeout: float = 30000) -> Optional[str]:
        """
        Get text content of an element.

        Args:
            selector: CSS selector
            timeout: Maximum wait time in milliseconds

        Returns:
            Text content or None if not found
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                return await element.text_content()
        except Exception as e:
            logger.error(f"Get text failed: {e}")
        return None

    async def screenshot(
        self,
        path: Optional[str] = None,
        full_page: bool = False
    ) -> Optional[bytes]:
        """
        Take a screenshot.

        Args:
            path: Save path (optional, returns bytes if not provided)
            full_page: Capture full scrollable page

        Returns:
            Screenshot bytes (if path not provided)
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        logger.info(f"📸 Taking screenshot{f' -> {path}' if path else ''}")
        screenshot = await self.page.screenshot(path=path, full_page=full_page)
        return screenshot if not path else None

    async def get_page_content(self) -> str:
        """Get the HTML content of the current page."""
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        return await self.page.content()

    async def evaluate(self, script: str) -> Any:
        """
        Execute JavaScript on the page.

        Args:
            script: JavaScript code to execute

        Returns:
            Result of the script
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        return await self.page.evaluate(script)

    async def upload(self, selector: str, file_path: str) -> bool:
        """Upload a file using an <input type="file"> selector."""
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        await self.page.set_input_files(selector, file_path)
        return True

    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 30000,
        state: str = "visible"
    ) -> bool:
        """
        Wait for an element to appear.

        Args:
            selector: CSS selector
            timeout: Maximum wait time in milliseconds
            state: Element state to wait for ("attached", "detached", "visible", "hidden")

        Returns:
            True if element found
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            await self.page.wait_for_selector(selector, timeout=timeout, state=state)
            return True
        except Exception as e:
            logger.error(f"Wait failed: {e}")
            return False

    async def execute_workflow(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute a multi-step workflow.

        Args:
            steps: List of workflow steps, each with:
                   {"action": "navigate|click|fill|wait|screenshot", "params": {...}}

        Returns:
            List of results for each step

        Example:
            steps = [
                {"action": "navigate", "params": {"url": "https://google.com"}},
                {"action": "fill", "params": {"selector": "input[name='q']", "text": "playwright"}},
                {"action": "click", "params": {"selector": "input[type='submit']"}},
                {"action": "screenshot", "params": {"path": "result.png"}},
            ]
        """
        results = []

        for i, step in enumerate(steps, 1):
            action = step.get("action")
            params = step.get("params", {})

            logger.info(f"📋 Step {i}/{len(steps)}: {action}")

            try:
                if action == "navigate":
                    result = await self.navigate(**params)
                elif action == "click":
                    result = await self.click(**params)
                elif action == "fill":
                    result = await self.fill(**params)
                elif action == "wait":
                    result = await self.wait_for_selector(**params)
                elif action == "screenshot":
                    result = await self.screenshot(**params)
                elif action == "get_text":
                    result = await self.get_text(**params)
                elif action == "evaluate":
                    result = await self.evaluate(**params)
                else:
                    result = {"error": f"Unknown action: {action}"}

                results.append({
                    "step": i,
                    "action": action,
                    "success": True,
                    "result": result
                })

            except Exception as e:
                logger.error(f"Step {i} failed: {e}")
                results.append({
                    "step": i,
                    "action": action,
                    "success": False,
                    "error": str(e)
                })
                # Continue or break based on error handling strategy
                # For now, we continue

        return results

    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.stop()
