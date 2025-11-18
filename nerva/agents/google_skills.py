"""Google Workspace skill layer built on BrowserAutomation + Qwen Vision."""
from __future__ import annotations

import asyncio
import json
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from nerva.tools.browser_automation import BrowserAutomation
from nerva.vision.qwen_vision import QwenVision


@dataclass
class CalendarEvent:
    """Simple representation of a Google Calendar event."""

    title: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    date: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


@dataclass
class EmailDraft:
    """Email payload for GmailSkill."""

    to: List[str]
    subject: str
    body: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None


DEFAULT_VISION_MODEL = "qwen3-vl:4b"


class GoogleSkillBase:
    """Shared helpers for Google Workspace skills."""

    def __init__(
        self,
        *,
        browser: Optional[BrowserAutomation] = None,
        vision: Optional[QwenVision] = None,
        headless: bool = False,
        user_data_dir: Optional[str] = None,
        screenshot_dir: Optional[Path] = None,
    ) -> None:
        self.browser = browser or BrowserAutomation(
            headless=headless,
            user_data_dir=user_data_dir,
        )
        self._own_browser = browser is None
        self.vision = vision or QwenVision(model=DEFAULT_VISION_MODEL)
        self._screenshot_dir = screenshot_dir or Path(
            tempfile.mkdtemp(prefix="nerva_google_skill_")
        )
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        """Close the browser if this skill owns it."""
        if self._own_browser and self.browser:
            await self.browser.stop()

    async def __aenter__(self) -> "GoogleSkillBase":
        await self._ensure_browser()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def _ensure_browser(self) -> None:
        if not self.browser.page:
            await self.browser.start()

    async def _navigate(self, url: str, wait_selector: Optional[str] = None) -> None:
        """Nav helper that waits for a key selector if provided."""
        await self._ensure_browser()
        await self.browser.navigate(url)
        if wait_selector:
            await self.browser.wait_for_selector(wait_selector, timeout=20000)

    async def _capture_view(self, label: str) -> Path:
        """Capture current browser view for vision analysis."""
        await self._ensure_browser()
        timestamp = int(time.time() * 1000)
        path = self._screenshot_dir / f"{label}_{timestamp}.png"
        await self.browser.screenshot(str(path), full_page=True)
        return path

    async def _vision_json(self, screenshot: Path, prompt: str) -> Dict[str, Any]:
        """Describe screenshot with Qwen and attempt to parse JSON payload."""
        response = await self.vision.analyze_screenshot(screenshot, prompt)
        parsed = self._extract_json(response)
        return {
            "raw": response.strip(),
            "parsed": parsed,
            "screenshot": str(screenshot),
        }

    @staticmethod
    def _extract_json(text: str) -> Optional[Any]:
        """Extract first JSON block from LLM text."""
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            # Attempt to salvage by trimming trailing commas
            candidate = re.sub(r",\s*([\]}])", r"\1", match.group(1))
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return None


class GoogleCalendarSkill(GoogleSkillBase):
    """Vision + browser helpers for Google Calendar."""

    async def summarize_day(self, day: str = "today", limit: int = 6) -> Dict[str, Any]:
        """Capture agenda view and summarize events."""
        await self._navigate(
            "https://calendar.google.com/calendar/u/0/r/day",
            wait_selector="div[role='main']",
        )
        screenshot = await self._capture_view("calendar_day")
        prompt = f"""You are looking at Google Calendar. Summarize the schedule for {day}.
Return JSON with this schema:
{{
  "day": "{day}",
  "events": [
    {{"time": "9:00 AM - 10:00 AM", "title": "Event title", "location": "..."}}
  ]
}}
Limit to {limit} events. If no events, use an empty array."""
        result = await self._vision_json(screenshot, prompt)
        events = []
        if isinstance(result["parsed"], dict):
            events = result["parsed"].get("events") or []
        elif isinstance(result["parsed"], list):
            events = result["parsed"]
        return {
            "events": events,
            "vision": result["raw"],
            "screenshot": result["screenshot"],
        }

    async def create_event(self, event: CalendarEvent) -> Dict[str, Any]:
        """Create a calendar event via the event edit page."""
        await self._navigate(
            "https://calendar.google.com/calendar/u/0/r/eventedit",
            wait_selector="input[aria-label='Add title']",
        )
        page = self.browser.page
        assert page is not None
        await page.fill("input[aria-label='Add title']", event.title)
        if event.date:
            await page.fill("input[aria-label='From date']", event.date)
            await page.fill("input[aria-label='To date']", event.date)
        if event.start_time:
            await page.fill("input[aria-label='From time']", event.start_time)
        if event.end_time:
            await page.fill("input[aria-label='To time']", event.end_time)
        if event.location:
            await page.fill("input[aria-label='Add location']", event.location)
        if event.description:
            await page.fill("div[aria-label='Description']", event.description)

        # Save event
        save_locator = page.locator("div[role='button']:has-text('Save')")
        if await save_locator.count() > 0:
            await save_locator.first.click()
        else:
            await page.keyboard.press("Control+Enter")

        # Simple confirmation wait
        await asyncio.sleep(2)
        return {
            "status": "submitted",
            "title": event.title,
            "start": event.start_time,
            "end": event.end_time,
        }


class GmailSkill(GoogleSkillBase):
    """Inbox summary + compose helper."""

    async def summarize_inbox(
        self,
        *,
        unread_only: bool = True,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Use vision to describe the Gmail inbox."""
        await self._navigate(
            "https://mail.google.com/mail/u/0/#inbox",
            wait_selector="div[role='main']",
        )
        screenshot = await self._capture_view("gmail_inbox")
        status = "unread" if unread_only else "recent"
        prompt = f"""You are looking at Gmail. List the top {limit} {status} messages.
Respond with JSON:
[
  {{"sender": "Name", "subject": "Subject", "snippet": "Preview", "time": "10:04 AM", "unread": true}}
]
"""
        result = await self._vision_json(screenshot, prompt)
        messages = result["parsed"] if isinstance(result["parsed"], list) else []
        return {
            "messages": messages,
            "vision": result["raw"],
            "screenshot": result["screenshot"],
        }

    async def send_email(self, draft: EmailDraft) -> Dict[str, Any]:
        """Compose and send an email using Gmail UI."""
        await self._navigate(
            "https://mail.google.com/mail/u/0/#inbox",
            wait_selector="div[gh='cm']",
        )
        page = self.browser.page
        assert page is not None
        await page.click("div[gh='cm']")
        await page.wait_for_selector("textarea[name='to']", timeout=20000)

        await page.fill("textarea[name='to']", ", ".join(draft.to))
        if draft.cc:
            await page.click("span[aria-label='Add Cc recipients']")
            await page.fill("textarea[name='cc']", ", ".join(draft.cc))
        if draft.bcc:
            await page.click("span[aria-label='Add Bcc recipients']")
            await page.fill("textarea[name='bcc']", ", ".join(draft.bcc))

        await page.fill("input[name='subjectbox']", draft.subject)
        body_locator = page.locator("div[aria-label='Message Body']")
        await body_locator.click()
        await body_locator.fill(draft.body)

        send_locator = page.locator("div[role='button'][data-tooltip*='Send']")
        await send_locator.first.click()

        await page.wait_for_timeout(1500)
        return {
            "status": "sent",
            "subject": draft.subject,
            "to": draft.to,
        }


class GoogleDriveSkill(GoogleSkillBase):
    """Drive listing + search helpers."""

    async def list_recent_files(self, limit: int = 8) -> Dict[str, Any]:
        """Capture Drive main view and summarize files."""
        await self._navigate(
            "https://drive.google.com/drive/u/0/my-drive",
            wait_selector="div[role='main']",
        )
        screenshot = await self._capture_view("drive_recent")
        prompt = f"""You are looking at Google Drive. List the {limit} most visible files/folders.
Respond with JSON:
[
  {{"name": "Project Plan", "type": "Google Doc", "owner": "Me", "last_modified": "Yesterday"}}
]
"""
        result = await self._vision_json(screenshot, prompt)
        files = result["parsed"] if isinstance(result["parsed"], list) else []
        return {
            "files": files,
            "vision": result["raw"],
            "screenshot": result["screenshot"],
        }

    async def search(self, query: str) -> Dict[str, Any]:
        """Use Drive search to locate files and summarize results."""
        await self._navigate(
            "https://drive.google.com/drive/u/0/my-drive",
            wait_selector="input[aria-label='Search in Drive']",
        )
        page = self.browser.page
        assert page is not None
        await page.fill("input[aria-label='Search in Drive']", query)
        await page.keyboard.press("Enter")
        await page.wait_for_selector("div[role='main']", timeout=20000)
        await asyncio.sleep(1)
        screenshot = await self._capture_view("drive_search")
        prompt = f"""You are looking at Google Drive search results for '{query}'.
List the top results as JSON with fields name, type, owner, last_modified."""
        result = await self._vision_json(screenshot, prompt)
        items = result["parsed"] if isinstance(result["parsed"], list) else []
        return {
            "query": query,
            "results": items,
            "vision": result["raw"],
            "screenshot": result["screenshot"],
        }
