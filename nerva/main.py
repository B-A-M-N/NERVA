#!/usr/bin/env python3
# nerva/main.py
"""
NERVA - Neural Embodied Reasoning & Vision Assistant

Main orchestrator and CLI entrypoint.
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from .config import NervaConfig
from .llm.factory import create_llm_client
from .memory.store import MemoryStore
from .run_context import RunContext
from .workflows import (
    build_screen_dag,
    build_voice_dag,
    build_daily_ops_dag,
    build_repo_dag,
)
from .vision.screenshot import capture_screen


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class NervaOrchestrator:
    """Main NERVA orchestrator - manages workflows and system state."""

    def __init__(self, config: Optional[NervaConfig] = None) -> None:
        self.config = config or NervaConfig()
        self.llm = create_llm_client(self.config)
        self.memory = MemoryStore()

        logger.info("NERVA Orchestrator initialized")
        if self.config.use_sollol:
            logger.info(
                "LLM: SOLLOL router (%s, model=%s)",
                self.config.sollol_base_url,
                self.config.sollol_model,
            )
        else:
            logger.info(
                "LLM: %s @ %s", self.config.qwen_model, self.config.ollama_base_url
            )

    async def run_screen_mode(self, screenshot_bytes: Optional[bytes] = None) -> RunContext:
        """
        Run screen understanding workflow.

        Args:
            screenshot_bytes: Optional screenshot bytes. If None, captures screen.

        Returns:
            RunContext with screen analysis results
        """
        if screenshot_bytes is None:
            screenshot_bytes = capture_screen()

        if screenshot_bytes is None:
            raise RuntimeError("No screenshot available - capture_screen() returned None")

        ctx = RunContext(mode="screen", screenshot_bytes=screenshot_bytes)
        dag = build_screen_dag(llm=self.llm, memory=self.memory)
        return await dag.run(ctx)

    async def run_voice_mode(self, text: str) -> RunContext:
        """
        Run voice command workflow.

        Args:
            text: Voice transcript or text command

        Returns:
            RunContext with LLM response
        """
        ctx = RunContext(mode="voice", voice_text=text)
        dag = build_voice_dag(llm=self.llm, memory=self.memory)
        return await dag.run(ctx)

    async def run_daily_ops(self) -> RunContext:
        """
        Run daily operations workflow.

        Returns:
            RunContext with daily summary and tasks
        """
        ctx = RunContext(mode="daily_ops")
        dag = build_daily_ops_dag(llm=self.llm, memory=self.memory)
        return await dag.run(ctx)

    async def run_repo_mode(self, question: str, repo_root: Optional[str] = None) -> RunContext:
        """
        Run repo-aware assistant workflow.

        Args:
            question: Question about the codebase
            repo_root: Path to repository root (defaults to current directory)

        Returns:
            RunContext with repo answer
        """
        if repo_root is None:
            repo_root = str(Path.cwd())

        ctx = RunContext(mode="repo", repo_question=question, repo_root=repo_root)
        dag = build_repo_dag(llm=self.llm, memory=self.memory)
        return await dag.run(ctx)


# ============================================================================
# CLI Interface
# ============================================================================


async def cmd_daily_ops(orchestrator: NervaOrchestrator) -> None:
    """Run daily ops and display results."""
    print("\n" + "=" * 60)
    print("DAILY OPS MODE")
    print("=" * 60 + "\n")

    ctx = await orchestrator.run_daily_ops()

    print(f"Summary:\n{ctx.daily_summary}\n")
    print(f"Tasks ({len(ctx.daily_tasks)}):")
    for i, task in enumerate(ctx.daily_tasks, 1):
        priority = task.get("priority", "medium")
        title = task.get("title", "Untitled")
        reason = task.get("reason", "")
        print(f"{i}. [{priority.upper()}] {title}")
        if reason:
            print(f"   → {reason}")
    print()


async def cmd_voice(orchestrator: NervaOrchestrator, text: str) -> None:
    """Run voice command and display results."""
    print("\n" + "=" * 60)
    print("VOICE COMMAND MODE")
    print("=" * 60 + "\n")
    print(f"You: {text}\n")

    ctx = await orchestrator.run_voice_mode(text)

    print(f"NERVA [{ctx.intent}]: {ctx.llm_raw_response}\n")


async def cmd_repo(orchestrator: NervaOrchestrator, question: str, repo_root: Optional[str] = None) -> None:
    """Run repo query and display results."""
    print("\n" + "=" * 60)
    print("REPO-AWARE ASSISTANT MODE")
    print("=" * 60 + "\n")
    print(f"Question: {question}")
    print(f"Repo: {repo_root or Path.cwd()}\n")

    ctx = await orchestrator.run_repo_mode(question, repo_root)

    print(f"Answer:\n{ctx.repo_answer}\n")


async def cmd_screen(orchestrator: NervaOrchestrator) -> None:
    """Run screen understanding and display results."""
    print("\n" + "=" * 60)
    print("SCREEN UNDERSTANDING MODE")
    print("=" * 60 + "\n")

    ctx = await orchestrator.run_screen_mode()

    print("Analysis:")
    for key, value in ctx.screen_analysis.items():
        print(f"  {key}: {value}")
    print()


async def interactive_mode(orchestrator: NervaOrchestrator) -> None:
    """Interactive REPL mode."""
    print("\n" + "=" * 60)
    print("NERVA Interactive Mode")
    print("=" * 60)
    print("\nCommands:")
    print("  daily          - Run daily ops")
    print("  voice <text>   - Send voice/text command")
    print("  repo <q>       - Ask about current repo")
    print("  screen         - Analyze current screen")
    print("  exit           - Exit NERVA")
    print()

    while True:
        try:
            user_input = input("nerva> ").strip()
            if not user_input:
                continue

            parts = user_input.split(maxsplit=1)
            command = parts[0].lower()

            if command == "exit":
                print("Goodbye!")
                break
            elif command == "daily":
                await cmd_daily_ops(orchestrator)
            elif command == "voice" and len(parts) > 1:
                await cmd_voice(orchestrator, parts[1])
            elif command == "repo" and len(parts) > 1:
                await cmd_repo(orchestrator, parts[1])
            elif command == "screen":
                await cmd_screen(orchestrator)
            else:
                print(f"Unknown command: {command}")
                print("Type 'exit' to quit or use one of the commands above.")

        except KeyboardInterrupt:
            print("\nUse 'exit' to quit.")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            print(f"Error: {e}")


async def main() -> None:
    """Main entrypoint."""
    if len(sys.argv) == 1:
        # No arguments - run interactive mode
        orchestrator = NervaOrchestrator()
        await interactive_mode(orchestrator)
        return

    # Command-line mode
    command = sys.argv[1].lower()
    orchestrator = NervaOrchestrator()

    if command == "daily":
        await cmd_daily_ops(orchestrator)

    elif command == "voice" and len(sys.argv) > 2:
        text = " ".join(sys.argv[2:])
        await cmd_voice(orchestrator, text)

    elif command == "repo" and len(sys.argv) > 2:
        question = " ".join(sys.argv[2:])
        await cmd_repo(orchestrator, question)

    elif command == "screen":
        await cmd_screen(orchestrator)

    else:
        print("NERVA - Neural Embodied Reasoning & Vision Assistant")
        print("\nUsage:")
        print("  nerva                    - Interactive mode")
        print("  nerva daily              - Run daily ops")
        print("  nerva voice <text>       - Send voice/text command")
        print("  nerva repo <question>    - Ask about current repo")
        print("  nerva screen             - Analyze current screen")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
