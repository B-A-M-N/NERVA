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
from nerva.github import GitHubManager, GitTroubleshooter
from nerva.filesystem import FileSystemNavigator, RepoManager, RepoInfo
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
        github_manager: Optional[GitHubManager] = None,
        repo_manager: Optional[RepoManager] = None,
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
        self.github_manager = github_manager or GitHubManager()
        self.repo_manager = repo_manager or RepoManager()
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
        calendar_keywords = (
            "calendar",
            "schedule",
            "meeting",
            "event",
            "reminder",
            "remind",
            "appointment",
            "activity",
            "pick up",
            "drop off",
            "to-do",
            "todo",
            "tasks for",
        )
        if any(keyword in text for keyword in calendar_keywords):
            return "calendar"
        if any(word in text for word in ("email", "gmail", "inbox", "message")):
            return "gmail"
        if any(word in text for word in ("drive", "document", "file", "folder")):
            return "drive"
        github_keywords = (
            "github",
            "access to github",
            "do you have github",
            "can you access github",
            "connected to github",
            "pull request",
            "pull requests",
            "merge request",
            "merge requests",
            "mr ",
            "mrs",
            "pr ",
            "prs",
            "issue",
            "notification",
            "git status",
            "git push",
            "git pull",
            "code review",
            "review queue",
            "review backlog",
            "create branch",
            "troubleshoot git",
            "merge",
            "merges",
            "merger",
            "discover repos",
            "find repos",
            "list repos",
            "my repos",
            "switch to",
            "go to repo",
            "dirty repos",
            "uncommitted changes",
            "unpushed",
            "repos ahead",
            "repos behind",
            "need pull",
            "fix issues",
            "fix problems",
            "fix all",
            "fix it",
            "diagnose",
        )
        if any(kw in text for kw in github_keywords):
            return "github"
        if any(word in text for word in ("screen", "browser", "click", "scroll", "tab", "search")):
            return "vision"
        # Phone number lookups only - directions/maps go to vision
        if any(
            phrase in text
            for phrase in (
                "phone number",
                "call",
                "dial",
                "contact info",
                "contact for",
            )
        ):
            return "lookup"

        # Directions/maps queries use vision agent with screenshots
        if any(
            phrase in text
            for phrase in (
                "directions",
                "map",
                "drive to",
                "navigate to",
                "where is",
                "location of",
                "how do i get to",
            )
        ):
            return "vision"

        # Ask LLM to choose route
        prompt = """You are a router for NERVA. Valid skills:
1. calendar - schedule, meetings
2. gmail - emails
3. drive - google drive / files
4. github - git operations, PRs, issues, notifications
5. vision - generic browser automation

Reply with JSON: {"route":"calendar|gmail|drive|github|vision","reason":"..."}."""
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": command},
        ]
        try:
            response = await self.llm.chat(messages)
            match = re.search(r'"route"\s*:\s*"([^"]+)"', response)
            if match:
                route = match.group(1).strip().lower()
                if route in {"calendar", "gmail", "drive", "github", "vision"}:
                    return route
        except Exception as exc:  # pragma: no cover - llm errors
            logger.warning("Router LLM failed: %s", exc)

        return "vision"

    async def _handle_calendar(self, command: str, ctx: TaskContext) -> TaskResult:
        if not self.calendar_skill:
            raise RuntimeError("Calendar skill not configured")

        lower = command.lower()
        create_triggers = ("create", "schedule", "add", "set", "make", "remind", "reminder")
        event_markers = (
            "event",
            "reminder",
            "activity",
            "appointment",
            "meeting",
            "pick up",
            "drop off",
            "call",
            "task",
            "todo",
            "to-do",
        )
        wants_event = any(trigger in lower for trigger in create_triggers) and any(
            marker in lower for marker in event_markers
        )
        if "remind me" in lower or "reminder" in lower:
            wants_event = True
        if wants_event:
            event = await self._interpret_event(command)
            try:
                payload = await self.calendar_skill.create_event(event)
                summary = f"Created calendar reminder '{event.title}'"
                status = payload.get("status", "submitted")
            except Exception as exc:
                logger.error("Calendar event creation failed: %s", exc)
                summary = f"Failed to create reminder: {exc}"
                payload = {"error": str(exc)}
                status = "error"
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
        if self._is_send_email_command(lower):
            draft = await self._interpret_email(command)
            if not draft.to:
                summary = "Failed to parse recipient from the request."
                payload = {"error": "missing_recipient", "draft": draft.__dict__}
                status = "error"
            else:
                payload = await self.gmail_skill.send_email(draft)
                summary = f"Sent email to {', '.join(draft.to)}"
                status = payload.get("status", "sent")
        else:
            payload = await self.gmail_skill.summarize_inbox()
            count = len(payload.get("messages") or [])
            summary = f"Summarized {count} inbox messages"
            status = "ok"
        return TaskResult(command, "gmail", status, summary, payload, ctx.meta)

    def _is_send_email_command(self, lower: str) -> bool:
        keywords = ("send", "email", "compose", "write", "reply")
        return any(word in lower for word in keywords)

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

    async def _handle_github(self, command: str, ctx: TaskContext) -> TaskResult:
        """Handle GitHub operations: status, PRs, issues, notifications, push/pull, troubleshooting, repo management."""
        cmd_lower = command.lower()

        try:
            # Check for access/availability questions - trigger repo discovery
            if any(phrase in cmd_lower for phrase in ["access", "do you have", "can you", "connected"]) and "github" in cmd_lower:
                print("   [DEBUG] Matched access question pattern")
                print("   Discovering repositories... (this may take a moment)")
                raw_local = self.repo_manager.discover_repos(max_depth=4) if self.repo_manager else []
                local_repos: List[RepoInfo] = []
                seen_paths = set()
                for repo in raw_local:
                    key = str(repo.path.resolve())
                    if key in seen_paths:
                        continue
                    seen_paths.add(key)
                    local_repos.append(repo)
                remote_repos: List[Dict[str, Any]] = []
                remote_error: Optional[str] = None
                if self.github_manager:
                    try:
                        remote_repos = self.github_manager.list_repositories(limit=50)
                    except Exception as exc:  # pragma: no cover - gh issues
                        remote_error = str(exc)

                summary_lines: List[str] = []
                if local_repos:
                    summary_lines.append(f"Local repositories ({len(local_repos)} found):")
                    for repo in local_repos[:15]:
                        summary_lines.append(f"  • {repo}")
                    stats = self.repo_manager.get_repo_summary() if self.repo_manager else {"dirty": 0, "ahead": 0, "behind": 0}
                    hints = []
                    if stats.get("dirty"):
                        hints.append(f"{stats['dirty']} dirty")
                    if stats.get("ahead"):
                        hints.append(f"{stats['ahead']} ahead")
                    if stats.get("behind"):
                        hints.append(f"{stats['behind']} behind")
                    if hints:
                        summary_lines.append("    (" + ", ".join(hints) + ")")
                else:
                    summary_lines.append("No local git repositories found under the configured roots.")

                if remote_repos:
                    summary_lines.append("")
                    summary_lines.append(f"GitHub account repositories ({len(remote_repos)} from gh auth):")
                    for repo in remote_repos[:15]:
                        owner = repo.get("nameWithOwner") or repo.get("name", "unknown")
                        visibility = (repo.get("visibility") or "unknown").lower()
                        summary_lines.append(f"  • {owner} [{visibility}]")
                elif remote_error:
                    summary_lines.append("")
                    summary_lines.append(f"GitHub CLI access unavailable: {remote_error}")
                else:
                    summary_lines.append("")
                    summary_lines.append("GitHub CLI returned no repositories (check `gh auth login`).")

                payload = {
                    "local_repos": [str(repo.path) for repo in local_repos],
                    "remote_repos": remote_repos,
                }
                return TaskResult(command, "github", "ok", "\n".join(summary_lines), payload, ctx.meta)

            # Repository discovery and management
            if "discover repos" in cmd_lower or "find all repos" in cmd_lower or "scan repos" in cmd_lower:
                print("   Discovering repositories... (this may take a moment)")
                repos = self.repo_manager.discover_repos(max_depth=4)

                if not repos:
                    summary = "No git repositories found"
                else:
                    summary = f"Discovered {len(repos)} repositories:\n"
                    for repo in repos[:10]:  # Show first 10
                        summary += f"\n  • {repo}"

                    stats = self.repo_manager.get_repo_summary()
                    if stats["dirty"] > 0:
                        summary += f"\n\n{stats['dirty']} repo(s) have uncommitted changes"
                    if stats["ahead"] > 0:
                        summary += f"\n{stats['ahead']} repo(s) have unpushed commits"
                    if stats["behind"] > 0:
                        summary += f"\n{stats['behind']} repo(s) need pulling"

                return TaskResult(command, "github", "ok", summary, {"repos": [str(r) for r in repos]}, ctx.meta)

            # Outstanding merges / PR overview
            elif any(
                kw in cmd_lower
                for kw in (
                    "outstanding merge",
                    "outstanding merges",
                    "pending merge",
                    "pending merges",
                    "mergers outstanding",
                    "outstanding mergers",
                    "awaiting merge",
                    "awaiting merges",
                    "merge request",
                    "merge requests",
                    "mr ",
                    "mrs",
                    "pull request",
                    "pull requests",
                    "open pr",
                    "open prs",
                    "pr backlog",
                    "review queue",
                    "review backlog",
                    "code review",
                )
            ):
                if not self.github_manager.gh_available:
                    return TaskResult(
                        command,
                        "github",
                        "error",
                        "GitHub CLI (gh) not installed. Install with: brew install gh",
                        {},
                        ctx.meta,
                    )

                prs = self.github_manager.list_pull_requests(limit=20)
                if not prs:
                    summary = "No open pull requests or outstanding merges detected."
                else:
                    summary = f"{len(prs)} open pull request{'s' if len(prs) != 1 else ''} awaiting merge:\n"
                    for pr in prs[:8]:
                        state = "draft" if pr.get("isDraft") else pr.get("state", "").lower()
                        summary += f"\n  #{pr['number']}: {pr['title'][:60]} ({pr.get('headRefName')} · {state})"

                return TaskResult(command, "github", "ok", summary, {"prs": prs}, ctx.meta)

            # Quick repo issue overview across all repos
            elif (
                ("issues" in cmd_lower or "repo issues" in cmd_lower or "repo problem" in cmd_lower or "repo problems" in cmd_lower or "git issues" in cmd_lower)
                and "list" not in cmd_lower
                and "fix" not in cmd_lower
                and not any(
                    token in cmd_lower
                    for token in ("pull request", "pull requests", "pr ", "prs", "merge", "merger", "merge request", "merge requests")
                )
            ):
                if not self.repo_manager._repo_cache:
                    self.repo_manager.discover_repos(max_depth=4)

                dirty = self.repo_manager.find_dirty_repos()
                ahead = self.repo_manager.find_repos_ahead()
                behind = self.repo_manager.find_repos_behind()

                if not dirty and not ahead and not behind:
                    summary = "All repositories look clean—no uncommitted, unpushed, or out-of-date branches detected."
                else:
                    lines: List[str] = []
                    if dirty:
                        lines.append(f"{len(dirty)} repo(s) have uncommitted changes:")
                        for repo in dirty[:10]:
                            lines.append(f"  • {repo.name} ({repo.branch})")
                    if ahead:
                        if lines:
                            lines.append("")
                        lines.append(f"{len(ahead)} repo(s) have unpushed commits:")
                        for repo in ahead[:10]:
                            lines.append(f"  • {repo.name} (+{repo.ahead})")
                    if behind:
                        if lines:
                            lines.append("")
                        lines.append(f"{len(behind)} repo(s) need pulling:")
                        for repo in behind[:10]:
                            lines.append(f"  • {repo.name} (-{repo.behind})")
                    summary = "\n".join(lines)

                payload = {
                    "dirty": [repo.name for repo in dirty],
                    "ahead": [repo.name for repo in ahead],
                    "behind": [repo.name for repo in behind],
                }
                return TaskResult(command, "github", "ok", summary, payload, ctx.meta)

            # List repositories
            elif "list repos" in cmd_lower or "show repos" in cmd_lower or "my repos" in cmd_lower:
                if not self.repo_manager._repo_cache:
                    self.repo_manager.discover_repos(max_depth=4)

                repos = list(self.repo_manager._repo_cache.values())
                if not repos:
                    summary = "No repositories in cache. Try 'discover repos' first."
                else:
                    summary = f"Found {len(repos)} repositories:\n"
                    for repo in repos[:15]:  # Show first 15
                        summary += f"\n  • {repo}"

                return TaskResult(command, "github", "ok", summary, {"repos": [str(r) for r in repos]}, ctx.meta)

            # Switch repository
            elif "switch to" in cmd_lower or "go to repo" in cmd_lower or "change repo" in cmd_lower:
                # Extract repo name from command
                match = re.search(r"(?:switch to|go to repo|change repo)\s+(.+)", cmd_lower)
                if not match:
                    return TaskResult(
                        command,
                        "github",
                        "error",
                        "Could not parse repository name from command",
                        {},
                        ctx.meta,
                    )

                repo_name = match.group(1).strip()
                repo = self.repo_manager.switch_repo(repo_name)

                if not repo:
                    summary = f"Repository '{repo_name}' not found. Try 'discover repos' first."
                    return TaskResult(command, "github", "error", summary, {}, ctx.meta)

                # Update github_manager to point to new repo
                self.github_manager = GitHubManager(repo_path=repo.path)

                summary = f"Switched to repository: {repo}"
                return TaskResult(command, "github", "ok", summary, {"repo": str(repo)}, ctx.meta)

            # Find dirty/uncommitted repos
            elif "dirty repos" in cmd_lower or "uncommitted changes" in cmd_lower:
                if not self.repo_manager._repo_cache:
                    self.repo_manager.discover_repos(max_depth=4)

                dirty = self.repo_manager.find_dirty_repos()
                if not dirty:
                    summary = "All repositories are clean"
                else:
                    summary = f"Found {len(dirty)} repositories with uncommitted changes:\n"
                    for repo in dirty:
                        summary += f"\n  • {repo.name} ({repo.branch})"

                return TaskResult(command, "github", "ok", summary, {"repos": [str(r) for r in dirty]}, ctx.meta)

            # Find repos that need pushing
            elif "unpushed" in cmd_lower or "need push" in cmd_lower or "repos ahead" in cmd_lower:
                if not self.repo_manager._repo_cache:
                    self.repo_manager.discover_repos(max_depth=4)

                ahead = self.repo_manager.find_repos_ahead()
                if not ahead:
                    summary = "No repositories have unpushed commits"
                else:
                    summary = f"Found {len(ahead)} repositories with unpushed commits:\n"
                    for repo in ahead:
                        summary += f"\n  • {repo.name}: +{repo.ahead} commit(s)"

                return TaskResult(command, "github", "ok", summary, {"repos": [str(r) for r in ahead]}, ctx.meta)

            # Find repos that need pulling
            elif "need pull" in cmd_lower or "repos behind" in cmd_lower or "update needed" in cmd_lower:
                if not self.repo_manager._repo_cache:
                    self.repo_manager.discover_repos(max_depth=4)

                behind = self.repo_manager.find_repos_behind()
                if not behind:
                    summary = "All repositories are up to date"
                else:
                    summary = f"Found {len(behind)} repositories that need pulling:\n"
                    for repo in behind:
                        summary += f"\n  • {repo.name}: -{repo.behind} commit(s)"

                return TaskResult(command, "github", "ok", summary, {"repos": [str(r) for r in behind]}, ctx.meta)

            # Status check (existing code)
            elif "status" in cmd_lower or "git status" in cmd_lower:
                status_info = self.github_manager.status()
                ahead_behind = self.github_manager.ahead_behind()
                branch = status_info["branch"]
                changes = len(status_info["changes"])
                ahead = ahead_behind["ahead"]
                behind = ahead_behind["behind"]

                summary = f"Branch: {branch}"
                if ahead > 0:
                    summary += f"\n  Ahead by {ahead} commit{'s' if ahead != 1 else ''}"
                if behind > 0:
                    summary += f"\n  Behind by {behind} commit{'s' if behind != 1 else ''}"
                if changes > 0:
                    summary += f"\n  {changes} uncommitted change{'s' if changes != 1 else ''}"
                else:
                    summary += "\n  Working tree clean"

                # Proactive troubleshooting warnings
                troubleshooter = GitTroubleshooter(self.github_manager.repo_path)
                tips = troubleshooter.run_checks()

                warnings = []
                for tip in tips:
                    if "conflict" in tip.title.lower():
                        warnings.append(f"⚠️ {tip.title}")
                    elif "behind" in tip.title.lower():
                        warnings.append(f"💡 {tip.title} - consider pulling")
                    elif "ahead" in tip.title.lower() and ahead > 5:
                        warnings.append(f"💡 {tip.title} - consider pushing soon")

                if warnings:
                    summary += "\n\n" + "\n".join(warnings)

                return TaskResult(command, "github", "ok", summary, status_info, ctx.meta)

            # Pull
            elif "pull" in cmd_lower:
                result = self.github_manager.pull()
                output = result["stdout"].strip() or result["stderr"].strip()

                # Auto-troubleshoot if pull failed
                if "error" in output.lower() or "fatal" in output.lower() or result.get("stderr"):
                    troubleshooter = GitTroubleshooter(self.github_manager.repo_path)
                    tips = troubleshooter.run_checks()

                    summary = f"Git pull failed: {output[:200]}"
                    if tips:
                        summary += f"\n\n⚠️ Detected {len(tips)} issue(s):"
                        for tip in tips[:3]:  # Show top 3
                            summary += f"\n  • {tip.title}: {tip.fix[:100]}"
                    return TaskResult(command, "github", "error", summary, result, ctx.meta)

                summary = f"Git pull complete: {output[:200]}"
                return TaskResult(command, "github", "ok", summary, result, ctx.meta)

            # Push
            elif "push" in cmd_lower:
                result = self.github_manager.push()
                output = result["stdout"].strip() or result["stderr"].strip()

                # Auto-troubleshoot if push failed
                if "error" in output.lower() or "fatal" in output.lower() or "rejected" in output.lower():
                    troubleshooter = GitTroubleshooter(self.github_manager.repo_path)
                    tips = troubleshooter.run_checks()

                    summary = f"Git push failed: {output[:200]}"
                    if tips:
                        summary += f"\n\n⚠️ Detected {len(tips)} issue(s):"
                        for tip in tips[:3]:  # Show top 3
                            summary += f"\n  • {tip.title}: {tip.fix[:100]}"
                    else:
                        # Common push failures
                        if "rejected" in output.lower():
                            summary += "\n\n💡 Tip: Remote has changes you don't have. Try 'git pull' first."
                        elif "no upstream" in output.lower():
                            summary += "\n\n💡 Tip: Set upstream with 'git push -u origin <branch>'"
                    return TaskResult(command, "github", "error", summary, result, ctx.meta)

                summary = f"Git push complete: {output[:200]}"
                return TaskResult(command, "github", "ok", summary, result, ctx.meta)

            # Troubleshooting
            elif "troubleshoot" in cmd_lower or "diagnose" in cmd_lower:
                troubleshooter = GitTroubleshooter(self.github_manager.repo_path)
                tips = troubleshooter.run_checks()

                if not tips:
                    summary = "No git issues detected. Everything looks good!"
                else:
                    summary = f"Found {len(tips)} issue{'s' if len(tips) != 1 else ''}:\n"
                    for tip in tips:
                        has_fix = "🔧" if tip.auto_fix else "💡"
                        summary += f"\n  {has_fix} {tip.title}: {tip.details[:100]}"

                    # Count auto-fixable issues
                    auto_fixable = sum(1 for t in tips if t.auto_fix)
                    if auto_fixable > 0:
                        summary += f"\n\n{auto_fixable} issue(s) can be auto-fixed. Say 'fix all issues' to apply fixes."

                payload = {"tips": [{"title": t.title, "details": t.details, "fix": t.fix, "has_auto_fix": t.auto_fix is not None} for t in tips]}
                return TaskResult(command, "github", "ok", summary, payload, ctx.meta)

            # Auto-fix issues
            elif "fix" in cmd_lower and any(phrase in cmd_lower for phrase in ["issues", "problems", "all", "it"]):
                troubleshooter = GitTroubleshooter(self.github_manager.repo_path)
                tips = troubleshooter.run_checks()

                auto_fixable = [t for t in tips if t.auto_fix]

                if not auto_fixable:
                    summary = "No auto-fixable issues detected. Manual fixes may be required."
                    return TaskResult(command, "github", "ok", summary, {}, ctx.meta)

                # Ask for confirmation using clarifier if available
                if self.clarifier:
                    confirm_msg = f"Found {len(auto_fixable)} fixable issue(s):\n"
                    for tip in auto_fixable:
                        confirm_msg += f"\n  • {tip.title}"
                    confirm_msg += "\n\nDo you want me to fix these? (yes/no)"

                    response = await self.clarifier(confirm_msg)
                    if not response or "no" in response.lower() or "cancel" in response.lower():
                        summary = "Auto-fix cancelled by user"
                        return TaskResult(command, "github", "ok", summary, {}, ctx.meta)

                # Execute auto-fixes
                results = []
                for tip in auto_fixable:
                    try:
                        result = tip.auto_fix()
                        success = result.returncode == 0
                        results.append({
                            "title": tip.title,
                            "success": success,
                            "output": result.stdout.strip() or result.stderr.strip(),
                        })
                    except Exception as e:
                        results.append({
                            "title": tip.title,
                            "success": False,
                            "output": str(e),
                        })

                success_count = sum(1 for r in results if r["success"])
                summary = f"Applied {success_count}/{len(results)} fixes:\n"
                for r in results:
                    status = "[OK]" if r["success"] else "[FAIL]"
                    summary += f"\n  {status} {r['title']}"
                    if not r["success"]:
                        summary += f": {r['output'][:100]}"

                return TaskResult(command, "github", "ok" if success_count > 0 else "error", summary, {"results": results}, ctx.meta)

            # List issues via GitHub CLI
            elif any(
                kw in cmd_lower
                for kw in (
                    "list issues",
                    "show issues",
                    "open issues",
                    "what issues",
                    "github issues",
                    "issue backlog",
                )
            ):
                if not self.github_manager.gh_available:
                    return TaskResult(
                        command,
                        "github",
                        "error",
                        "GitHub CLI (gh) not installed. Install with: brew install gh",
                        {},
                        ctx.meta,
                    )

                issues = self.github_manager.list_issues(limit=10)

                if not issues:
                    summary = "No open issues found"
                else:
                    summary = f"Found {len(issues)} open issue{'s' if len(issues) != 1 else ''}:\n"
                    for issue in issues[:5]:
                        summary += f"\n  #{issue['number']}: {issue['title'][:60]} ({issue['state']})"

                return TaskResult(command, "github", "ok", summary, {"issues": issues}, ctx.meta)

            # List notifications
            elif "notification" in cmd_lower:
                if not self.github_manager.gh_available:
                    return TaskResult(
                        command,
                        "github",
                        "error",
                        "GitHub CLI (gh) not installed. Install with: brew install gh",
                        {},
                        ctx.meta,
                    )

                notifications = self.github_manager.list_notifications(limit=20)

                if not notifications:
                    summary = "No GitHub notifications"
                else:
                    summary = f"You have {len(notifications)} notification{'s' if len(notifications) != 1 else ''}:\n"
                    for notif in notifications[:5]:
                        summary += f"\n  • {notif.get('subject', 'Unknown')[:60]}"

                return TaskResult(command, "github", "ok", summary, {"notifications": notifications}, ctx.meta)

            # Create branch
            elif "create branch" in cmd_lower or "new branch" in cmd_lower:
                match = re.search(r"(?:create|new)\s+branch\s+(?:called\s+)?['\"]?([a-zA-Z0-9_/-]+)['\"]?", cmd_lower)
                if not match:
                    return TaskResult(
                        command,
                        "github",
                        "error",
                        "Could not parse branch name from command",
                        {},
                        ctx.meta,
                    )

                branch_name = match.group(1)
                self.github_manager.create_branch(branch_name)
                summary = f"Created and checked out branch: {branch_name}"
                return TaskResult(command, "github", "ok", summary, {"branch": branch_name}, ctx.meta)

            # Default: show status
            else:
                status_info = self.github_manager.status()
                summary = f"Git status: {status_info['summary']}"
                return TaskResult(command, "github", "ok", summary, status_info, ctx.meta)

        except Exception as e:
            logger.error(f"[TaskDispatcher] GitHub handler error: {e}")
            return TaskResult(
                command,
                "github",
                "error",
                f"GitHub operation failed: {str(e)}",
                {"error": str(e)},
                ctx.meta,
            )

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
        to_clean = [r.strip() for r in recipients if isinstance(r, str) and r.strip()]
        subject = data.get("subject")
        body = data.get("body")
        if not subject:
            subject = "Untitled email"
        if not body:
            body = ""
        return EmailDraft(
            to=to_clean,
            subject=subject,
            body=body,
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
