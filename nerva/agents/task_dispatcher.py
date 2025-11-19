"""Task dispatcher, voice control, and safety/ambient layers for Phase III+IV."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from nerva.llm.client_base import BaseLLMClient
from nerva.memory.store import MemoryStore
from nerva.memory.schemas import MemoryItem, MemoryType
from nerva.task_tracking.thread_store import ThreadStore
from nerva.knowledge.graph import KnowledgeGraph

from .vision_action_agent import VisionActionAgent
from .google_skills import (
    CalendarEvent,
    EmailDraft,
    GoogleCalendarSkill,
    GoogleDriveSkill,
    GmailSkill,
)
# Playbook imports removed - use proper playbook infrastructure from playbooks_google.py, playbooks_research.py, etc.

try:  # Optional voice deps
    from nerva.voice.whisper_asr import WhisperASR
    from nerva.voice.kokoro_tts import KokoroTTS
except Exception:  # pragma: no cover - optional
    WhisperASR = None
    KokoroTTS = None


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #


@dataclass
class TaskResult:
    """Summary payload returned by TaskDispatcher."""

    command: str
    route: str
    status: str
    summary: str
    payload: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskContext:
    """Metadata about task origin."""

    source: str = "manual"  # voice, hotkey, ambient, cli, etc.
    thread_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Task Dispatcher
# --------------------------------------------------------------------------- #


class TaskDispatcher:
    """Routes natural commands to the right agent/skill."""

    def __init__(
        self,
        *,
        llm: BaseLLMClient,
        memory: Optional[MemoryStore],
        vision_agent: VisionActionAgent,
        calendar_skill: Optional[GoogleCalendarSkill] = None,
        gmail_skill: Optional[GmailSkill] = None,
        drive_skill: Optional[GoogleDriveSkill] = None,
        safety_manager: Optional["SafetyManager"] = None,
        clarifier: Optional[Callable[[str], Awaitable[str]]] = None,
        thread_store: Optional[ThreadStore] = None,
        knowledge_graph: Optional[KnowledgeGraph] = None,
    ) -> None:
        self.llm = llm
        self.memory = memory or MemoryStore()
        self.vision_agent = vision_agent
        self.calendar_skill = calendar_skill
        self.gmail_skill = gmail_skill
        self.drive_skill = drive_skill
        self.safety = safety_manager or SafetyManager()
        self.clarifier = clarifier
        self.thread_store = thread_store
        self.knowledge_graph = knowledge_graph or KnowledgeGraph()

    async def dispatch(
        self,
        command: str,
        context: Optional[TaskContext] = None,
    ) -> TaskResult:
        """Classify and execute a task."""
        ctx = context or TaskContext()
        if self.thread_store and not ctx.thread_id:
            project = ctx.meta.get("project") or "general"
            thread = self.thread_store.create(project=project, title=command[:80])
            ctx.thread_id = thread.thread_id
            self.thread_store.add_entry(thread.thread_id, f"Task created: {command}")
            if self.knowledge_graph:
                self.knowledge_graph.ingest_thread(
                    thread.thread_id,
                    thread.title,
                    [entry.__dict__ for entry in thread.entries],
                )
        command = await self._clarify_command(command, ctx)
        route = await self._classify(command)
        handler = getattr(self, f"_handle_{route}", self._handle_unknown)
        logger.info("[TaskDispatcher] route=%s via=%s", route, ctx.source)
        result = await handler(command, ctx)
        self._record_memory(command, result, ctx)
        return result

    async def _classify(self, command: str) -> str:
        """Heuristic classifier with LLM fallback."""
        text = command.lower()
        if any(word in text for word in ("calendar", "schedule", "meeting", "event")):
            return "calendar"
        if any(word in text for word in ("email", "gmail", "inbox", "message")):
            return "gmail"
        if any(word in text for word in ("drive", "document", "file", "folder")):
            return "drive"
        if any(word in text for word in ("screen", "browser", "click", "scroll", "tab", "search")):
            return "vision"
        if any(
            phrase in text
            for phrase in (
                "phone number",
                "call",
                "dial",
                "directions",
                "address",
                "where is",
                "location",
                "map",
                "drive to",
                "lookup",
                "search for",
            )
        ):
            return "lookup"

        # Ask LLM to choose route
        prompt = """You are a router for NERVA. Valid skills:
1. calendar - schedule, meetings
2. gmail - emails
3. drive - google drive / files
4. vision - generic browser automation

Reply with JSON: {"route":"calendar|gmail|drive|vision","reason":"..."}."""
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": command},
        ]
        try:
            response = await self.llm.chat(messages)
            match = re.search(r'"route"\s*:\s*"([^"]+)"', response)
            if match:
                route = match.group(1).strip().lower()
                if route in {"calendar", "gmail", "drive", "vision"}:
                    return route
        except Exception as exc:  # pragma: no cover - llm errors
            logger.warning("Router LLM failed: %s", exc)

        return "vision"

    async def _handle_calendar(self, command: str, ctx: TaskContext) -> TaskResult:
        if not self.calendar_skill:
            raise RuntimeError("Calendar skill not configured")

        lower = command.lower()
        if any(word in lower for word in ("create", "schedule", "add")) and "event" in lower:
            event = await self._interpret_event(command)
            payload = await self.calendar_skill.create_event(event)
            summary = f"Created event '{event.title}'"
            status = payload.get("status", "submitted")
        else:
            payload = await self.calendar_skill.summarize_day()
            count = len(payload.get("events") or [])
            summary = f"Found {count} events"
            status = "ok"
        return TaskResult(command, "calendar", status, summary, payload, ctx.meta)

    async def _handle_gmail(self, command: str, ctx: TaskContext) -> TaskResult:
        if not self.gmail_skill:
            raise RuntimeError("Gmail skill not configured")

        lower = command.lower()
        if any(word in lower for word in ("send", "email", "compose")) and any(
            word in lower for word in ("to", "recipient", "email")
        ):
            draft = await self._interpret_email(command)
            payload = await self.gmail_skill.send_email(draft)
            summary = f"Sent email to {', '.join(draft.to)}"
            status = payload.get("status", "sent")
        else:
            payload = await self.gmail_skill.summarize_inbox()
            count = len(payload.get("messages") or [])
            summary = f"Summarized {count} inbox messages"
            status = "ok"
        return TaskResult(command, "gmail", status, summary, payload, ctx.meta)

    async def _handle_drive(self, command: str, ctx: TaskContext) -> TaskResult:
        if not self.drive_skill:
            raise RuntimeError("Drive skill not configured")

        if "search" in command.lower():
            match = re.search(r"search (.+)", command, re.IGNORECASE)
            query = match.group(1) if match else command
            payload = await self.drive_skill.search(query.strip("'\" "))
            summary = f"Searched Drive for '{query.strip()}'"
        else:
            payload = await self.drive_skill.list_recent_files()
            count = len(payload.get("files") or [])
            summary = f"Listed {count} recent Drive items"
        return TaskResult(command, "drive", "ok", summary, payload, ctx.meta)

    async def _handle_lookup(self, command: str, ctx: TaskContext) -> TaskResult:
        """Handle business lookup / phone-number queries via deterministic playbook."""
        query = await self._interpret_lookup(command)
        if not query:
            # Fallback: strip common prefixes with regex
            cmd_lower = command.lower()
            for pattern in [
                r"(?:phone number|number|contact info|call)\s+(?:for|to)\s+(.+)",
                r"(?:find|get|give me|tell me)\s+(?:the\s+)?(?:phone number|number|contact info)\s+(?:for|to|of)\s+(.+)",
                r"(?:what\'s|what is)\s+(?:the\s+)?(?:phone number|number)\s+(?:for|to|of)\s+(.+)",
            ]:
                match = re.search(pattern, cmd_lower, re.IGNORECASE)
                if match:
                    query = match.group(1).strip()
                    break
        if not query:
            query = command
        payload = await self.vision_agent.lookup_phone_number(query)
        answer = payload.get("answer")
        summary = payload.get("reason", f"Lookup completed for {query}")
        if isinstance(answer, str) and answer.strip():
            summary = f"{summary}\n{answer.strip()}"
        return TaskResult(command, "lookup", payload.get("status", "success"), summary, payload, ctx.meta)

    async def _handle_vision(self, command: str, ctx: TaskContext) -> TaskResult:
        """Fallback to the autonomous vision/browser agent."""
        cmd_lower = command.lower()

        # Check if this is a lookup/phone number query - use deterministic playbook
        is_lookup = any(kw in cmd_lower for kw in ["phone number", "phone for", "number for", "contact info"])

        if is_lookup:
            # Extract the business/location from the query
            # e.g., "phone number for Target in Tinley Park" -> "Target Tinley Park"
            query = command
            for prefix in ["phone number for", "phone for", "number for", "contact info for", "find"]:
                if prefix in cmd_lower:
                    query = command[command.lower().find(prefix) + len(prefix):].strip()
                    break

            # Use deterministic lookup playbook
            result = await self.vision_agent.lookup_phone_number(query)
            summary = result.get("answer", result.get("reason", "Lookup complete"))
            return TaskResult(command, "lookup", result.get("status", "ok"), summary, result, ctx.meta)

        # Otherwise use full vision agent loop
        starting_url = ctx.meta.get("url") or self._extract_url(command)
        result = await self.vision_agent.execute_task(
            task=command,
            starting_url=starting_url,
        )
        summary = result.get("reason", "vision agent run complete")
        return TaskResult(command, "vision", result.get("status", "unknown"), summary, result, ctx.meta)

    async def _handle_unknown(self, command: str, ctx: TaskContext) -> TaskResult:
        """Graceful fallback when route not supported."""
        summary = "No handler available for this command."
        return TaskResult(command, "unknown", "skipped", summary, {}, ctx.meta)

    # ------------------------------------------------------------------ #
    # Interpretation helpers
    # ------------------------------------------------------------------ #

    async def _interpret_event(self, command: str) -> CalendarEvent:
        prompt = """Extract a Google Calendar event from the request.
Return JSON with keys: title, date, start_time, end_time, location, description."""
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": command},
        ]
        response = await self.llm.chat(messages)
        data = self._extract_structured(response)
        return CalendarEvent(
            title=data.get("title") or "Untitled Event",
            date=data.get("date"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            location=data.get("location"),
            description=data.get("description"),
        )

    async def _interpret_email(self, command: str) -> EmailDraft:
        prompt = """Extract email fields from this request.
Return JSON: {"to":["recipient@example.com"],"subject":"...","body":"..."}"""
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": command},
        ]
        response = await self.llm.chat(messages)
        data = self._extract_structured(response)
        recipients = data.get("to") or data.get("recipients") or []
        if isinstance(recipients, str):
            recipients = [recipients]
        return EmailDraft(
            to=[r.strip() for r in recipients if r.strip()],
            subject=data.get("subject") or "Untitled email",
            body=data.get("body") or "",
            cc=data.get("cc"),
            bcc=data.get("bcc"),
        )

    async def _interpret_lookup(self, command: str) -> Optional[str]:
        prompt = """Extract the business or place the user wants information about.
Return JSON: {"query": "..."}"""
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": command},
        ]
        try:
            response = await self.llm.chat(messages)
            data = self._extract_structured(response)
            query = data.get("query")
            if isinstance(query, str) and query.strip():
                return query.strip()
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_structured(text: str) -> Dict[str, Any]:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except Exception:
            return {}

    @staticmethod
    def _extract_url(command: str) -> Optional[str]:
        match = re.search(r"(https?://\S+)", command)
        return match.group(1) if match else None

    def _record_memory(self, command: str, result: TaskResult, ctx: TaskContext) -> None:
        """Persist dispatch results for later reference."""
        text = f"Task: {command}\nRoute: {result.route}\nSummary: {result.summary}"
        item = MemoryItem.new(
            mem_type=MemoryType.SYSTEM,
            text=text,
            meta={"route": result.route, "payload": result.payload, "status": result.status},
            tags=["dispatcher", result.route],
        )
        self.memory.add(item)
        if self.thread_store and ctx.thread_id:
            thread = self.thread_store.get(ctx.thread_id)
            if thread:
                entry_text = f"{result.route.upper()} → {result.summary}"
                self.thread_store.add_entry(
                    ctx.thread_id,
                    entry_text,
                    metadata={"route": result.route, "status": result.status},
                )
                if self.knowledge_graph:
                    self.knowledge_graph.ingest_thread(
                        thread.thread_id,
                        thread.title,
                        [entry.__dict__ for entry in thread.entries],
                    )

    async def _clarify_command(self, command: str, ctx: TaskContext) -> str:
        prompt = """You are a task clarifier. Determine if the user's request is ambiguous.
Respond with JSON like {"needs_clarification": true/false, "question": "Follow-up question"}.
Only request clarification if it is absolutely necessary."""
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": command},
        ]
        try:
            response = await self.llm.chat(messages)
            data = self._extract_structured(response)
        except Exception:
            data = {}

        if not data or not data.get("needs_clarification"):
            return command

        question = data.get("question") or "Can you clarify?"
        answer = await self._ask_clarification(question)
        if not answer:
            return command
        return f"{command}\nClarification: {answer.strip()}"

    async def _ask_clarification(self, question: str) -> Optional[str]:
        if self.clarifier:
            return await self.clarifier(question)
        loop = asyncio.get_running_loop()

        def _prompt() -> str:
            return input(f"[Clarify] {question} ").strip()

        return await loop.run_in_executor(None, _prompt)


# --------------------------------------------------------------------------- #
# Safety Layer
# --------------------------------------------------------------------------- #


class SafetyManager:
    """Simple risk detector + confirmation workflow."""

    risky_keywords = {"delete", "send", "purchase", "submit", "transfer", "publish", "remove"}

    def requires_confirmation(self, command: str) -> bool:
        lower = command.lower()
        return any(word in lower for word in self.risky_keywords)

    async def confirm(self, command: str) -> bool:
        """Prompt user for confirmation via stdin (works for CLI/voice)."""
        loop = asyncio.get_running_loop()

        def _ask() -> str:
            return input(f"[Safety] Confirm action '{command}'? (y/N): ").strip().lower()

        reply = await loop.run_in_executor(None, _ask)
        return reply in {"y", "yes"}


# --------------------------------------------------------------------------- #
# Hotkey + Ambient Monitoring
# --------------------------------------------------------------------------- #


class HotkeyManager:
    """Basic stdin-based hotkey watcher."""

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[[], Awaitable[None]]] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def register(self, key: str, handler: Callable[[], Awaitable[None]]) -> None:
        self._handlers[key.lower()] = handler

    async def start(self) -> None:
        if self._task:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            await self._task
            self._task = None

    async def _listen_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while self._running:
            cmd = await loop.run_in_executor(
                None, lambda: input("[Hotkey] Enter command (*, :calendar, :quit): ").strip()
            )
            if not cmd:
                continue
            key = cmd.lower()
            if key in (":quit", ":exit"):
                self._running = False
                break
            handler = self._handlers.get(key)
            if handler:
                await handler()
            else:
                print(f"[Hotkey] No handler for {cmd}")


class AmbientMonitor:
    """Schedules periodic tasks (e.g., summary checks)."""

    def __init__(
        self,
        dispatcher: TaskDispatcher,
        *,
        interval: int = 1800,
        task: str = "Check my calendar for upcoming meetings",
    ) -> None:
        self.dispatcher = dispatcher
        self.interval = interval
        self.task = task
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

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.interval)
            logger.info("[AmbientMonitor] Running scheduled task: %s", self.task)
            try:
                await self.dispatcher.dispatch(self.task, TaskContext(source="ambient"))
            except Exception as exc:
                logger.warning("Ambient task failed: %s", exc)


# --------------------------------------------------------------------------- #
# Voice Control Agent
# --------------------------------------------------------------------------- #


class VoiceControlAgent:
    """Hands-free voice loop that routes to the TaskDispatcher."""

    def __init__(
        self,
        dispatcher: TaskDispatcher,
        *,
        wake_word: str = "nerva",
        whisper_model: str = "tiny",
        safety_manager: Optional[SafetyManager] = None,
        enable_tts: bool = True,
    ) -> None:
        if WhisperASR is None or KokoroTTS is None:
            raise RuntimeError("Voice dependencies missing. Install Whisper + Kokoro.")

        self.dispatcher = dispatcher
        self.wake_word = wake_word.lower()
        self.asr = WhisperASR(model_path=whisper_model)
        self.tts = KokoroTTS() if enable_tts else None
        self.safety = safety_manager or dispatcher.safety
        self._running = False

    async def run(self) -> None:
        """Enter a wake-word driven loop."""
        print("\n[Voice] Say the wake word to issue a task (Ctrl+C to exit).")
        self._running = True
        loop = asyncio.get_running_loop()

        while self._running:
            try:
                text = await loop.run_in_executor(None, self.asr.transcribe_once)
            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.error("ASR error: %s", exc)
                continue

            if not text:
                continue

            lower = text.lower()
            if self.wake_word not in lower:
                continue

            command = lower.split(self.wake_word, 1)[-1].strip() or text
            print(f"\n[Voice] Command detected: {command}")

            if self.safety.requires_confirmation(command):
                confirmed = await self.safety.confirm(command)
                if not confirmed:
                    self._speak("Action cancelled.")
                    continue

            result = await self.dispatcher.dispatch(
                command,
                TaskContext(source="voice", meta={"transcript": text}),
            )
            response = f"Task routed to {result.route}. {result.summary}"
            self._speak(response)

    def stop(self) -> None:
        self._running = False

    def _speak(self, text: str) -> None:
        if self.tts:
            self.tts.speak(text, blocking=False)
        else:
            print(f"[Voice] {text}")


def create_default_hotkeys(dispatcher: TaskDispatcher) -> HotkeyManager:
    """
    Convenience helper that registers the '*' (numpad asterisk) macro hotkey.

    Pressing '*' kicks off three core summaries in sequence:
        1. Summarize today's calendar
        2. Summarize unread Gmail
        3. List recent Drive files
    """

    async def _star_macro() -> None:
        print("\n[Hotkey:*] Running quick status macro...")
        commands = [
            "Summarize today's calendar",
            "Show unread Gmail messages",
            "List my most recent Google Drive files",
        ]
        for command in commands:
            try:
                result = await dispatcher.dispatch(
                    command,
                    TaskContext(source="hotkey", meta={"macro": "*"}),
                )
                print(f"[Hotkey:*] {result.route}: {result.summary}")
            except Exception as exc:  # pragma: no cover - live usage
                print(f"[Hotkey:*] Error handling '{command}': {exc}")

    manager = HotkeyManager()
    manager.register("*", _star_macro)
    return manager
