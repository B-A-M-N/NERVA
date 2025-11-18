# nerva/console.py
"""
NERVA Console - Textual TUI interface for NERVA workflows.

A full-featured terminal UI that provides tabs for each NERVA mode:
- Screen Understanding
- Voice Commands
- Daily Ops
- Repo Assistant
- Memory Browser
- Node Status (SOLLOL integration)
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional
import logging

from textual.app import App, ComposeResult
from textual.widgets import (
    Header,
    Footer,
    RichLog,
    Input,
    Button,
    TabbedContent,
    TabPane,
    Static,
)
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive

from .config import NervaConfig
from .llm.factory import create_llm_client
from .memory.store import MemoryStore
from .workflows import (
    build_screen_dag,
    build_voice_dag,
    build_daily_ops_dag,
    build_repo_dag,
)
from .run_context import RunContext


logger = logging.getLogger(__name__)


class StatusBar(Static):
    """Status bar widget showing current operation status."""

    status: reactive[str] = reactive("Ready")

    def watch_status(self, value: str) -> None:
        """Update status display when status changes."""
        self.update(f"[b]Status:[/b] {value}")


class NervaConsole(App):
    """
    NERVA Console - Main TUI application.

    Provides tabbed interface for all NERVA workflows with live logging.
    """

    CSS = """
    #left-pane {
        width: 70%;
        border: solid green;
    }

    #right-pane {
        width: 30%;
        border: solid blue;
    }

    #main-log {
        height: 1fr;
        border: solid yellow;
    }

    #status-bar {
        height: 3;
        content-align: center middle;
        border: solid cyan;
    }

    RichLog {
        height: 1fr;
        border: solid white;
    }

    Input {
        margin: 1 0;
    }

    Button {
        margin: 1 0;
    }

    Static {
        margin: 1 0;
    }
    """

    BINDINGS = [
        ("f1", "tab_screen", "Screen"),
        ("f2", "tab_voice", "Voice"),
        ("f3", "tab_daily_ops", "Daily Ops"),
        ("f4", "tab_repo", "Repo"),
        ("f5", "tab_memory", "Memory"),
        ("f6", "tab_nodes", "Nodes"),
        ("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self, use_mock_llm: bool = False) -> None:
        super().__init__()
        self.cfg = NervaConfig()

        # Try to use real LLM, fall back to mock if connection fails
        try:
            self.llm = create_llm_client(self.cfg, use_mock=use_mock_llm)
            if use_mock_llm:
                logger.warning(
                    "Using mock LLM client - start Ollama/SOLLOL for real responses"
                )
        except Exception as e:  # pragma: no cover - init edge case
            logger.warning(f"Failed to initialize LLM client: {e}")
            from .llm.mock_client import MockLLMClient

            self.llm = MockLLMClient()

        self.memory = MemoryStore()

        # Widget handles
        self.event_log: Optional[RichLog] = None
        self.status_bar: Optional[StatusBar] = None

        # Per-tab widgets
        self.screen_output: Optional[RichLog] = None

        self.voice_input: Optional[Input] = None
        self.voice_output: Optional[RichLog] = None

        self.daily_output: Optional[RichLog] = None

        self.repo_question_input: Optional[Input] = None
        self.repo_root_input: Optional[Input] = None
        self.repo_output: Optional[RichLog] = None

        self.memory_output: Optional[RichLog] = None

        self.nodes_output: Optional[RichLog] = None

    # ========================================================================
    # Layout
    # ========================================================================

    def compose(self) -> ComposeResult:
        """Build the UI layout."""
        yield Header(show_clock=True)

        with Horizontal():
            # LEFT PANE: Tabbed workflows
            with Vertical(id="left-pane"):
                with TabbedContent():
                    # SCREEN TAB
                    with TabPane("Screen", id="tab-screen"):
                        yield Static(
                            "[bold]Screen Understanding Mode[/bold]\n\n"
                            "Analyzes screenshots using Qwen3-VL to understand what you're working on.\n"
                            "Extracts errors, intent, and suggests next actions.\n\n"
                            "[dim]Note: Screenshot capture needs to be implemented in vision/screenshot.py[/dim]",
                            id="screen-help",
                        )
                        yield Button("Run Screen DAG", id="btn-screen-run", variant="primary")
                        self.screen_output = RichLog(id="screen-output", highlight=True, markup=True)
                        yield self.screen_output

                    # VOICE TAB
                    with TabPane("Voice", id="tab-voice"):
                        yield Static(
                            "[bold]Voice Command Mode[/bold]\n\n"
                            "Type what you would say to NERVA (ASR integration coming soon).",
                            id="voice-help",
                        )
                        self.voice_input = Input(
                            placeholder="e.g. NERVA, what should I work on next?",
                            id="voice-input",
                        )
                        yield self.voice_input
                        yield Button("Send Command", id="btn-voice-run", variant="primary")
                        self.voice_output = RichLog(id="voice-output", highlight=True, markup=True)
                        yield self.voice_output

                    # DAILY OPS TAB
                    with TabPane("Daily Ops", id="tab-daily"):
                        yield Static(
                            "[bold]Daily Operations Mode[/bold]\n\n"
                            "Aggregates GitHub notifications, local TODOs, system events, and SOLLOL status\n"
                            "into a prioritized task list for your day.",
                            id="daily-help",
                        )
                        yield Button("Run Daily Ops DAG", id="btn-daily-run", variant="primary")
                        self.daily_output = RichLog(id="daily-output", highlight=True, markup=True)
                        yield self.daily_output

                    # REPO TAB
                    with TabPane("Repo", id="tab-repo"):
                        yield Static(
                            "[bold]Repo-Aware Assistant[/bold]\n\n"
                            "Ask questions about any codebase. Uses HydraContext for structured code understanding.",
                            id="repo-help",
                        )
                        self.repo_root_input = Input(
                            value=str(Path.cwd()),
                            placeholder="Repo root path",
                            id="repo-root-input",
                        )
                        yield self.repo_root_input
                        self.repo_question_input = Input(
                            placeholder="Ask a question about this repo...",
                            id="repo-question-input",
                        )
                        yield self.repo_question_input
                        yield Button("Ask Question", id="btn-repo-run", variant="primary")
                        self.repo_output = RichLog(id="repo-output", highlight=True, markup=True)
                        yield self.repo_output

                    # MEMORY TAB
                    with TabPane("Memory", id="tab-memory"):
                        yield Static(
                            "[bold]Memory Browser[/bold]\n\n"
                            "Browse NERVA's knowledge base - all Q&A, repo insights, and daily ops history.",
                            id="memory-help",
                        )
                        yield Button("Refresh Memory View", id="btn-memory-refresh", variant="success")
                        self.memory_output = RichLog(id="memory-output", highlight=True, markup=True)
                        yield self.memory_output

                    # NODES TAB
                    with TabPane("Nodes", id="tab-nodes"):
                        yield Static(
                            "[bold]Node Status[/bold]\n\n"
                            "SOLLOL node status, GPU telemetry, and system metrics.\n"
                            "[dim](Integration pending)[/dim]",
                            id="nodes-help",
                        )
                        yield Button("Refresh Node View", id="btn-nodes-refresh", variant="success")
                        self.nodes_output = RichLog(id="nodes-output", highlight=True, markup=True)
                        yield self.nodes_output

            # RIGHT PANE: Event log
            with Vertical(id="right-pane"):
                yield Static("[bold]Event Log[/bold]", id="log-label")
                self.event_log = RichLog(id="main-log", highlight=True, wrap=True, markup=True)
                yield self.event_log

                self.status_bar = StatusBar(id="status-bar")
                yield self.status_bar

        yield Footer()

    # ========================================================================
    # Actions for keybindings
    # ========================================================================

    def action_tab_screen(self) -> None:
        """Switch to Screen tab (F1)."""
        self.switch_tab("tab-screen")

    def action_tab_voice(self) -> None:
        """Switch to Voice tab (F2)."""
        self.switch_tab("tab-voice")

    def action_tab_daily_ops(self) -> None:
        """Switch to Daily Ops tab (F3)."""
        self.switch_tab("tab-daily")

    def action_tab_repo(self) -> None:
        """Switch to Repo tab (F4)."""
        self.switch_tab("tab-repo")

    def action_tab_memory(self) -> None:
        """Switch to Memory tab (F5)."""
        self.switch_tab("tab-memory")

    def action_tab_nodes(self) -> None:
        """Switch to Nodes tab (F6)."""
        self.switch_tab("tab-nodes")

    def switch_tab(self, tab_id: str) -> None:
        """Switch to a specific tab by ID."""
        tabbed = self.query_one(TabbedContent)
        tabbed.active = tab_id

    # ========================================================================
    # Helpers
    # ========================================================================

    def log_msg(self, msg: str) -> None:
        """Write a message to the event log."""
        if self.event_log is not None:
            self.event_log.write(msg)

    def set_status(self, msg: str) -> None:
        """Update the status bar."""
        if self.status_bar is not None:
            self.status_bar.status = msg

    # ========================================================================
    # Button event handlers
    # ========================================================================

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle all button presses."""
        button_id = event.button.id
        if button_id == "btn-screen-run":
            await self.run_screen_dag()
        elif button_id == "btn-voice-run":
            await self.run_voice_dag()
        elif button_id == "btn-daily-run":
            await self.run_daily_ops_dag()
        elif button_id == "btn-repo-run":
            await self.run_repo_dag()
        elif button_id == "btn-memory-refresh":
            await self.refresh_memory_view()
        elif button_id == "btn-nodes-refresh":
            await self.refresh_nodes_view()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input fields."""
        input_id = event.input.id
        if input_id == "voice-input":
            await self.run_voice_dag()
        elif input_id == "repo-question-input":
            await self.run_repo_dag()

    # ========================================================================
    # DAG Runners
    # ========================================================================

    async def run_screen_dag(self) -> None:
        """Run screen understanding workflow."""
        self.set_status("Running Screen DAG...")
        self.log_msg("[cyan][screen][/cyan] Starting Screen Understanding DAG")

        if self.screen_output is not None:
            self.screen_output.clear()
            self.screen_output.write(
                "[yellow]⚠[/yellow] Screen capture not yet implemented.\n"
                "To enable:\n"
                "1. Implement capture_screen() in vision/screenshot.py using mss\n"
                "2. Or manually inject screenshot_bytes into RunContext\n"
            )

        self.set_status("Screen DAG requires screenshot implementation")
        self.log_msg("[yellow][screen][/yellow] Screenshot capture not wired")

    async def run_voice_dag(self) -> None:
        """Run voice command workflow."""
        if self.voice_input is None:
            return

        text = self.voice_input.value.strip()
        if not text:
            self.set_status("Voice: No text provided")
            return

        self.set_status("Running Voice DAG...")
        self.log_msg(f"[cyan][voice][/cyan] Input: {text[:50]}...")

        if self.voice_output is not None:
            self.voice_output.clear()
            self.voice_output.write("[dim]Processing...[/dim]")

        ctx = RunContext(mode="voice", voice_text=text)
        dag = build_voice_dag(llm=self.llm, memory=self.memory)

        try:
            ctx = await dag.run(ctx)
        except Exception as e:
            self.log_msg(f"[red][voice][/red] ERROR: {e}")
            self.set_status("Voice DAG failed")
            if self.voice_output is not None:
                self.voice_output.clear()
                self.voice_output.write(f"[red]ERROR:[/red] {e}")
            logger.error(f"Voice DAG failed: {e}", exc_info=True)
            return

        if self.voice_output is not None:
            self.voice_output.clear()
            self.voice_output.write(f"[bold]Intent:[/bold] {ctx.intent}\n\n")
            self.voice_output.write("[bold]Response:[/bold]\n")
            self.voice_output.write(ctx.llm_raw_response or "[dim]No response[/dim]")

        self.set_status("Voice DAG completed")
        self.log_msg(f"[green][voice][/green] Completed (intent: {ctx.intent})")

        # Clear input for next command
        if self.voice_input is not None:
            self.voice_input.value = ""

    async def run_daily_ops_dag(self) -> None:
        """Run daily operations workflow."""
        self.set_status("Running Daily Ops DAG...")
        self.log_msg("[cyan][daily_ops][/cyan] Starting Daily Ops DAG")

        if self.daily_output is not None:
            self.daily_output.clear()
            self.daily_output.write("[dim]Collecting data and generating summary...[/dim]")

        ctx = RunContext(mode="daily_ops")
        dag = build_daily_ops_dag(llm=self.llm, memory=self.memory)

        try:
            ctx = await dag.run(ctx)
        except Exception as e:
            self.log_msg(f"[red][daily_ops][/red] ERROR: {e}")
            self.set_status("Daily Ops DAG failed")
            if self.daily_output is not None:
                self.daily_output.clear()
                self.daily_output.write(f"[red]ERROR:[/red] {e}")
            logger.error(f"Daily Ops DAG failed: {e}", exc_info=True)
            return

        if self.daily_output is not None:
            self.daily_output.clear()
            self.daily_output.write("[bold green]Daily Summary[/bold green]\n")
            self.daily_output.write(ctx.daily_summary or "[dim]No summary generated[/dim]")
            self.daily_output.write("\n\n[bold cyan]Tasks[/bold cyan]\n")

            for i, task in enumerate(ctx.daily_tasks, 1):
                priority = task.get("priority", "medium")
                title = task.get("title", "Untitled")
                reason = task.get("reason", "")

                # Color code by priority
                if priority == "high":
                    color = "red"
                elif priority == "medium":
                    color = "yellow"
                else:
                    color = "green"

                self.daily_output.write(f"{i}. [{color}]■[/{color}] {title}")
                if reason:
                    self.daily_output.write(f"   [dim]→ {reason}[/dim]")

        self.set_status("Daily Ops DAG completed")
        self.log_msg(f"[green][daily_ops][/green] Completed ({len(ctx.daily_tasks)} tasks)")

    async def run_repo_dag(self) -> None:
        """Run repo-aware assistant workflow."""
        if self.repo_root_input is None or self.repo_question_input is None:
            return

        repo_root = self.repo_root_input.value.strip() or str(Path.cwd())
        question = self.repo_question_input.value.strip()

        if not question:
            self.set_status("Repo: No question provided")
            return

        self.set_status("Running Repo DAG...")
        self.log_msg(f"[cyan][repo][/cyan] Root: {repo_root}")
        self.log_msg(f"[cyan][repo][/cyan] Question: {question[:50]}...")

        if self.repo_output is not None:
            self.repo_output.clear()
            self.repo_output.write("[dim]Indexing repository and generating answer...[/dim]")

        ctx = RunContext(mode="repo", repo_root=repo_root, repo_question=question)
        dag = build_repo_dag(llm=self.llm, memory=self.memory)

        try:
            ctx = await dag.run(ctx)
        except Exception as e:
            self.log_msg(f"[red][repo][/red] ERROR: {e}")
            self.set_status("Repo DAG failed")
            if self.repo_output is not None:
                self.repo_output.clear()
                self.repo_output.write(f"[red]ERROR:[/red] {e}")
            logger.error(f"Repo DAG failed: {e}", exc_info=True)
            return

        if self.repo_output is not None:
            self.repo_output.clear()
            self.repo_output.write(f"[bold]Repo:[/bold] {repo_root}\n")
            self.repo_output.write(f"[bold]Question:[/bold] {question}\n\n")
            self.repo_output.write("[bold green]Answer:[/bold green]\n")
            self.repo_output.write(ctx.repo_answer or "[dim]No answer generated[/dim]")

        self.set_status("Repo DAG completed")
        self.log_msg("[green][repo][/green] Completed")

        # Clear question for next one
        if self.repo_question_input is not None:
            self.repo_question_input.value = ""

    # ========================================================================
    # Memory & Nodes views
    # ========================================================================

    async def refresh_memory_view(self) -> None:
        """Refresh the memory browser view."""
        self.set_status("Refreshing Memory view...")
        self.log_msg("[cyan][memory][/cyan] Refreshing Memory view")

        items = self.memory.all()

        if self.memory_output is not None:
            self.memory_output.clear()
            if not items:
                self.memory_output.write("[dim]No memory items yet. Run some workflows to populate memory.[/dim]")
            else:
                self.memory_output.write(f"[bold]Total Items:[/bold] {len(items)}\n\n")

                # Show most recent 50
                for item in items[-50:]:
                    timestamp = item.created_at.strftime("%H:%M:%S")
                    mem_type = item.type.name
                    text_preview = item.text[:100].replace("\n", " ")

                    # Color code by type
                    if mem_type == "Q_AND_A":
                        color = "cyan"
                    elif mem_type == "DAILY_OP":
                        color = "green"
                    elif mem_type == "REPO_INSIGHT":
                        color = "yellow"
                    else:
                        color = "white"

                    self.memory_output.write(
                        f"[dim]{timestamp}[/dim] [{color}]{mem_type}[/{color}]: {text_preview}..."
                    )

        self.set_status("Memory view updated")
        self.log_msg(f"[green][memory][/green] Loaded {len(items)} items")

    async def refresh_nodes_view(self) -> None:
        """Refresh the nodes status view."""
        self.set_status("Refreshing Nodes view...")
        self.log_msg("[cyan][nodes][/cyan] Refreshing Nodes view")

        if self.nodes_output is not None:
            self.nodes_output.clear()
            self.nodes_output.write("[bold]SOLLOL Nodes[/bold]\n\n")
            self.nodes_output.write("[yellow]⚠[/yellow] SOLLOL integration not yet implemented.\n\n")
            self.nodes_output.write("To enable:\n")
            self.nodes_output.write("1. Install SOLLOL from your local repo\n")
            self.nodes_output.write("2. Implement collectors.collect_sollol_status()\n")
            self.nodes_output.write("3. Wire in real node metrics here\n")

        self.set_status("Nodes view (stub)")
        self.log_msg("[yellow][nodes][/yellow] Nodes view not implemented")


def run(use_mock_llm: bool = False) -> None:
    """
    Launch the NERVA Console TUI.

    Args:
        use_mock_llm: If True, use mock LLM client instead of Ollama/SOLLOL
    """
    app = NervaConsole(use_mock_llm=use_mock_llm)
    app.run()


if __name__ == "__main__":
    run()
