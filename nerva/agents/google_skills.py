"""Google Workspace skill layer built on BrowserAutomation + Qwen Vision."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from nerva.tools.browser_automation import BrowserAutomation
from nerva.vision.qwen_vision import QwenVision
from nerva.automation.playbooks import PlaybookRunner
from nerva.automation.playbooks_google import (
    build_calendar_day_playbook,
    build_calendar_event_playbook,
    build_calendar_week_playbook,
    build_calendar_reschedule_playbook,
    build_gmail_inbox_playbook,
    build_gmail_compose_playbook,
    build_gmail_archive_playbook,
    build_gmail_mark_read_playbook,
    build_gmail_label_playbook,
    build_gmail_reply_playbook,
    build_drive_main_playbook,
    build_drive_search_playbook,
    build_drive_upload_playbook,
    build_drive_share_playbook,
)


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
logger = logging.getLogger(__name__)


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
        self.playbook_runner = PlaybookRunner(browser=self.browser)

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
        await self.playbook_runner.run(build_calendar_day_playbook())
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
        await self.playbook_runner.run(build_calendar_event_playbook())
        page = self.browser.page
        assert page is not None
        async def fill_field(selectors: List[str], value: Optional[str]) -> bool:
            if not value:
                return False
            for selector in selectors:
                try:
                    locator = page.locator(selector).first
                    await locator.wait_for(state="visible", timeout=4000)
                    await locator.fill(value)
                    return True
                except Exception:
                    continue
            logger.warning("Unable to fill field for selectors %s", selectors)
            return False

        title_filled = await fill_field(
            [
                "input[aria-label='Add title']",
                "input[aria-label='Event title']",
                "input[aria-label*='title' i]",
                "textarea[aria-label*='title' i]",
                "div[aria-label*='title' i]",
                "input[aria-label='Add title and time']",
                "div[aria-label='Add title and time']",
                "[aria-label*='title and time' i]",
            ],
            event.title,
        )
        if event.title and not title_filled:
            try:
                filled = await page.evaluate(
                    """
                    (value) => {
                        const selectors = [
                            'input[aria-label*="title" i]',
                            'textarea[aria-label*="title" i]',
                            'div[aria-label*="title" i]',
                            'div[aria-label*="title and time" i]',
                            '[aria-label*="title and time" i]'
                        ];
                        for (const sel of selectors) {
                            const el = document.querySelector(sel);
                            if (!el) continue;
                            if (el.hasAttribute && el.hasAttribute('contenteditable')) {
                                el.textContent = value;
                            } else if ('value' in el) {
                                el.value = value;
                            } else {
                                continue;
                            }
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                            return true;
                        }
                        return false;
                    }
                    """,
                    event.title,
                )
                if not filled:
                    logger.warning("Script fallback could not set calendar title")
            except Exception as exc:
                logger.warning("Script fallback failed for title field: %s", exc)
        if event.date:
            await fill_field(
                [
                    "input[aria-label='From date']",
                    "input[aria-label='Date']",
                    "input[aria-label*='from date' i]",
                ],
                event.date,
            )
            await fill_field(
                [
                    "input[aria-label='To date']",
                    "input[aria-label*='to date' i]",
                ],
                event.date,
            )
        if event.start_time:
            await fill_field(
                [
                    "input[aria-label='From time']",
                    "input[aria-label='Start time']",
                    "input[aria-label*='from time' i]",
                ],
                event.start_time,
            )
        if event.end_time:
            await fill_field(
                [
                    "input[aria-label='To time']",
                    "input[aria-label='End time']",
                    "input[aria-label*='to time' i]",
                ],
                event.end_time,
            )
        if event.location:
            await fill_field(
                [
                    "input[aria-label='Add location']",
                    "input[aria-label*='location' i]",
                ],
                event.location,
            )
        if event.description:
            await fill_field(
                [
                    "div[aria-label='Description']",
                    "div[aria-label*='description' i]",
                    "textarea[aria-label*='description' i]",
                ],
                event.description,
            )

        # Save event
        saved = False
        for selector in (
            "div[role='button']:has-text('Save')",
            "button:has-text('Save')",
            "div[role='button']:has-text('Done')",
            "button:has-text('Done')",
        ):
            locator = page.locator(selector)
            if await locator.count() > 0:
                try:
                    await locator.first.click()
                    saved = True
                    break
                except Exception:
                    continue
        if not saved:
            logger.warning("Save button not found, using keyboard shortcut")
            await page.keyboard.press("Control+Enter")

        # Simple confirmation wait
        await asyncio.sleep(2)
        return {
            "status": "submitted",
            "title": event.title,
            "start": event.start_time,
            "end": event.end_time,
        }

    async def summarize_week(self, limit: int = 10) -> Dict[str, Any]:
        await self.playbook_runner.run(build_calendar_week_playbook())
        screenshot = await self._capture_view("calendar_week")
        prompt = "Summarize the key events in this week view as JSON."
        result = await self._vision_json(screenshot, prompt)
        data = result.get("parsed")
        events = data if isinstance(data, list) else []
        return {
            "events": events,
            "vision": result["raw"],
            "screenshot": result["screenshot"],
        }

    async def edit_first_event(self, updates: Dict[str, str]) -> Dict[str, Any]:
        await self.playbook_runner.run(build_calendar_reschedule_playbook())
        page = self.browser.page
        assert page is not None
        if title := updates.get("title"):
            await page.fill("input[aria-label='Add title']", title)
        if start := updates.get("start"):
            await page.fill("input[aria-label='From time']", start)
        if end := updates.get("end"):
            await page.fill("input[aria-label='To time']", end)
        if location := updates.get("location"):
            await page.fill("input[aria-label='Add location']", location)
        await page.click("div[role='button']:has-text('Save')")
        await asyncio.sleep(2)
        return {
            "status": "updated",
            "updates": updates,
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
        await self.playbook_runner.run(build_gmail_inbox_playbook())
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
        await self.playbook_runner.run(build_gmail_compose_playbook())
        page = self.browser.page
        assert page is not None

        # Wait for compose dialog to fully appear
        await page.wait_for_timeout(2000)

        # Type recipient directly (cursor is already in To field)
        recipient = ", ".join(draft.to)
        await page.keyboard.type(recipient)

        # If it's an email address, press Enter to commit it
        # If it's a name, wait for autocomplete then select
        if "@" in recipient:
            await page.wait_for_timeout(500)
            await page.keyboard.press("Enter")  # Commit the email address
        else:
            await page.wait_for_timeout(2000)  # Wait for autocomplete
            await page.keyboard.press("ArrowDown")
            await page.wait_for_timeout(300)
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(500)

        # Click subject field and type
        await page.click("input[name='subjectbox']")
        await page.keyboard.type(draft.subject)

        # Click body field and type
        await page.click("div[aria-label='Message Body']")
        await page.keyboard.type(draft.body)

        # Send with keyboard shortcut
        await page.wait_for_timeout(500)
        await page.keyboard.press("Control+Enter")

        await page.wait_for_timeout(1500)
        return {
            "status": "sent",
            "subject": draft.subject,
            "to": draft.to,
        }

    async def archive_first(self) -> Dict[str, Any]:
        await self.playbook_runner.run(build_gmail_archive_playbook())
        return {
            "status": "archived",
        }

    async def mark_first_read(self, read: bool = True) -> Dict[str, Any]:
        await self.playbook_runner.run(build_gmail_mark_read_playbook(read))
        return {
            "status": "updated",
            "read": read,
        }

    async def open_label(self, label: str) -> Dict[str, Any]:
        await self.playbook_runner.run(build_gmail_label_playbook(label))
        screenshot = await self._capture_view(f'label_{label}')
        return {
            "label": label,
            "screenshot": str(screenshot),
        }

    async def reply_first(self, body: str) -> Dict[str, Any]:
        await self.playbook_runner.run(build_gmail_reply_playbook())
        page = self.browser.page
        assert page is not None
        editor = page.locator("div[aria-label='Message Body']")
        await editor.fill(body)
        await page.locator("div[aria-label='Send ‪(Ctrl-Enter)‬']").click()
        await asyncio.sleep(1)
        return {
            "status": "sent",
            "body": body,
        }


class GoogleDriveSkill(GoogleSkillBase):
    """Drive listing + search helpers."""

    async def list_recent_files(self, limit: int = 8) -> Dict[str, Any]:
        """Capture Drive main view and summarize files."""
        await self.playbook_runner.run(build_drive_main_playbook())
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

    async def upload_file(self, file_path: str) -> Dict[str, Any]:
        await self.playbook_runner.run(build_drive_upload_playbook(file_path=file_path))
        return {
            "status": "uploaded",
            "file": file_path,
        }

    async def share_first_item(self) -> Dict[str, Any]:
        await self.playbook_runner.run(build_drive_share_playbook())
        return {
            "status": "share_dialog_opened",
        }

    async def search(self, query: str) -> Dict[str, Any]:
        """Use Drive search to locate files and summarize results."""
        await self.playbook_runner.run(build_drive_search_playbook(query))
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
