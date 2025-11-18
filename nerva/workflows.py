# nerva/workflows.py
from __future__ import annotations
from typing import Any, Dict, List
import json
from pathlib import Path
import logging

from .run_context import RunContext
from .dag import Dag, DagNode
from .llm.client_base import BaseLLMClient
from .memory.store import MemoryStore
from .memory.schemas import MemoryItem, MemoryType
from .ops.collectors import (
    collect_github_notifications,
    collect_local_todos,
    collect_system_events,
    collect_sollol_status,
)
from .repos.repo_index import index_repo, summarize_repo_structure
from .hydra_adapter.context_builder import build_context_for_repo


logger = logging.getLogger(__name__)


# ============================================================================
# 1. SCREEN UNDERSTANDING WORKFLOW
# ============================================================================

SCREEN_PROMPT = """You are NERVA's screen-understanding module.

You are looking at a developer workstation screenshot. Extract:

- repo name if visible
- likely file path or module being edited
- any visible error messages or stack traces
- what the user is probably trying to do
- 1-3 next recommended actions (shell commands, edits, or checks)

Respond as compact JSON with keys:
"repo", "file", "error_summary", "intent_guess", "next_actions" (array of strings).
"""


def build_screen_dag(llm: BaseLLMClient, memory: MemoryStore) -> Dag:
    """Build the screen understanding workflow DAG."""
    dag = Dag("screen-understanding")

    async def node_capture(ctx: RunContext) -> None:
        """Validate screenshot input is present."""
        if ctx.screenshot_bytes is None:
            raise RuntimeError("screen-understanding: screenshot_bytes is missing")
        logger.info("[Screen] Screenshot validated")

    async def node_llm_analyze(ctx: RunContext) -> None:
        """Send screenshot to vision LLM for analysis."""
        messages = [
            {"role": "system", "content": SCREEN_PROMPT},
            {"role": "user", "content": "Analyze this screenshot and respond with JSON only."},
        ]
        logger.info("[Screen] Analyzing screenshot with vision LLM")
        raw = await llm.vision_chat(messages=messages, images=[ctx.screenshot_bytes])
        ctx.llm_raw_response = raw

        try:
            ctx.screen_analysis = json.loads(raw)
            logger.info(f"[Screen] Analysis complete: {ctx.screen_analysis.get('intent_guess', 'unknown')}")
        except json.JSONDecodeError:
            logger.warning("[Screen] Failed to parse JSON response, storing as raw")
            ctx.screen_analysis = {"raw": raw}

    async def node_memory_write(ctx: RunContext) -> None:
        """Store screen analysis in memory."""
        text = f"Screen analysis: {json.dumps(ctx.screen_analysis, indent=2)}"
        item = MemoryItem.new(
            MemoryType.REPO_INSIGHT,
            text=text,
            meta={"mode": "screen", "analysis": ctx.screen_analysis},
            tags=["screen", "visual"],
        )
        memory.add(item)
        ctx.memory_items.append({"id": item.id, "type": str(item.type)})
        logger.info("[Screen] Analysis stored in memory")

    dag.add_node(DagNode("capture", node_capture, deps=[]))
    dag.add_node(DagNode("llm_analyze", node_llm_analyze, deps=["capture"]))
    dag.add_node(DagNode("memory_write", node_memory_write, deps=["llm_analyze"]))

    return dag


# ============================================================================
# 2. VOICE COMMAND WORKFLOW
# ============================================================================

VOICE_SYSTEM_PROMPT = """You are NERVA, a local AI assistant.

Your capabilities:
- Answer questions on various topics
- Provide technical explanations and guidance
- Remember conversation history during this session
- Run completely locally (no cloud services)

Rules:
- Keep responses concise and practical (2-4 sentences max)
- Be direct and technically accurate
- If you don't know something, say so immediately
- Focus on actionable information and next steps
- No therapy, philosophy, or speculation
"""


def build_voice_dag(llm: BaseLLMClient, memory: MemoryStore) -> Dag:
    """Build the voice command workflow DAG."""
    dag = Dag("voice-command")

    async def node_input(ctx: RunContext) -> None:
        """Validate voice input is present."""
        if not ctx.voice_text:
            raise RuntimeError("voice-command: voice_text missing")
        ctx.asr_transcript = ctx.voice_text
        logger.info(f"[Voice] Transcript: {ctx.asr_transcript[:100]}...")

    async def node_intent_and_answer(ctx: RunContext) -> None:
        """Process voice command and generate response."""
        messages = [
            {"role": "system", "content": VOICE_SYSTEM_PROMPT},
            {"role": "user", "content": ctx.asr_transcript or ""},
        ]
        logger.info("[Voice] Generating response")
        reply = await llm.chat(messages)
        ctx.llm_raw_response = reply

        # Simple intent classification
        lower = (ctx.asr_transcript or "").lower()
        if "screen" in lower or "look" in lower or "see" in lower:
            ctx.intent = "screen"
        elif "repo" in lower or "code" in lower or "explain" in lower:
            ctx.intent = "repo"
        elif "ops" in lower or "today" in lower or "todo" in lower or "tasks" in lower:
            ctx.intent = "daily_ops"
        else:
            ctx.intent = "generic"

        logger.info(f"[Voice] Intent: {ctx.intent}, Response: {reply[:100]}...")

    async def node_memory_write(ctx: RunContext) -> None:
        """Store Q&A in memory."""
        text = f"Q: {ctx.asr_transcript}\nA: {ctx.llm_raw_response}"
        item = MemoryItem.new(
            MemoryType.Q_AND_A,
            text=text,
            meta={"mode": "voice", "intent": ctx.intent},
            tags=["voice", "qa", ctx.intent],
        )
        memory.add(item)
        ctx.memory_items.append({"id": item.id, "type": str(item.type)})
        logger.info("[Voice] Q&A stored in memory")

    dag.add_node(DagNode("input", node_input, deps=[]))
    dag.add_node(DagNode("intent_and_answer", node_intent_and_answer, deps=["input"]))
    dag.add_node(DagNode("memory_write", node_memory_write, deps=["intent_and_answer"]))

    return dag


# ============================================================================
# 3. DAILY OPS WORKFLOW
# ============================================================================

DAILY_OPS_PROMPT = """You are NERVA's Daily Ops module - a personal SRE assistant.

You will be given:
- GitHub notifications and issues
- Local TODOs from notes
- System events (SOLLOL nodes, logs, etc.)

Produce:
- A concise summary (2-3 sentences) of what's happening
- A prioritized list of 3-7 concrete tasks the user should do today
- Each task should be small, actionable, and specific - not vague

Respond as JSON with keys:
"summary": str,
"tasks": [{ "title": str, "reason": str, "priority": "high"|"medium"|"low" }]

Sort tasks by priority (high first).
"""


def build_daily_ops_dag(llm: BaseLLMClient, memory: MemoryStore) -> Dag:
    """Build the daily operations workflow DAG."""
    dag = Dag("daily-ops")

    async def node_collect(ctx: RunContext) -> None:
        """Collect all daily ops inputs."""
        logger.info("[DailyOps] Collecting inputs")
        github = collect_github_notifications()
        todos = collect_local_todos()
        sys_events = collect_system_events()
        sollol_status = collect_sollol_status()

        ctx.daily_inputs = {
            "github": github,
            "todos": todos,
            "system_events": sys_events[:20],  # limit to recent
            "sollol_status": sollol_status,
        }
        logger.info(
            f"[DailyOps] Collected: {len(github)} GitHub, "
            f"{len(todos)} TODOs, {len(sys_events)} events"
        )

    async def node_llm(ctx: RunContext) -> None:
        """Generate daily summary and task list."""
        messages = [
            {"role": "system", "content": DAILY_OPS_PROMPT},
            {"role": "user", "content": json.dumps(ctx.daily_inputs, indent=2)},
        ]
        logger.info("[DailyOps] Generating summary")
        reply = await llm.chat(messages)
        ctx.llm_raw_response = reply

        try:
            data = json.loads(reply)
        except json.JSONDecodeError:
            logger.warning("[DailyOps] Failed to parse JSON, using raw response")
            data = {"summary": reply, "tasks": []}

        ctx.daily_summary = data.get("summary", "")
        ctx.daily_tasks = data.get("tasks", [])
        logger.info(f"[DailyOps] Generated {len(ctx.daily_tasks)} tasks")

    async def node_memory(ctx: RunContext) -> None:
        """Store daily ops report in memory."""
        text = f"Daily summary: {ctx.daily_summary}\n\nTasks:\n"
        for i, task in enumerate(ctx.daily_tasks, 1):
            text += f"{i}. [{task.get('priority', 'medium')}] {task.get('title', 'Untitled')}\n"

        item = MemoryItem.new(
            MemoryType.DAILY_OP,
            text=text,
            meta={"tasks": ctx.daily_tasks, "inputs": ctx.daily_inputs},
            tags=["daily_ops", "tasks"],
        )
        memory.add(item)
        ctx.memory_items.append({"id": item.id, "type": str(item.type)})
        logger.info("[DailyOps] Report stored in memory")

    dag.add_node(DagNode("collect", node_collect, deps=[]))
    dag.add_node(DagNode("llm", node_llm, deps=["collect"]))
    dag.add_node(DagNode("memory", node_memory, deps=["llm"]))

    return dag


# ============================================================================
# 4. REPO-AWARE ASSISTANT WORKFLOW
# ============================================================================

REPO_PROMPT = """You are NERVA's repo-aware assistant.

Given:
- A question about the codebase
- A structured summary of relevant files and code structure

You must:
- Answer concisely and accurately
- Reference specific files/functions/classes where possible
- Avoid generating huge code dumps unless explicitly requested
- If you're unsure, say so - don't make up file paths or functions

Format your answer in markdown with code references like `file.py:123` when relevant.
"""


def build_repo_dag(llm: BaseLLMClient, memory: MemoryStore) -> Dag:
    """Build the repo-aware assistant workflow DAG."""
    dag = Dag("repo-assistant")

    async def node_index(ctx: RunContext) -> None:
        """Index repository files."""
        if not ctx.repo_root:
            raise RuntimeError("repo-assistant: repo_root missing")

        root = Path(ctx.repo_root).resolve()
        logger.info(f"[Repo] Indexing repository: {root}")
        files = index_repo(root)

        # Build structured context (will use HydraContext later)
        structure_summary = summarize_repo_structure(files)
        hydra_context = build_context_for_repo(root, question=ctx.repo_question)

        ctx.repo_context = {
            "root": str(root),
            "file_count": len(files),
            "structure": structure_summary,
            "hydra_context": hydra_context,
            "files": [{"path": f.rel_path, "size": f.size_bytes} for f in files[:100]],
        }
        logger.info(f"[Repo] Indexed {len(files)} files")

    async def node_llm(ctx: RunContext) -> None:
        """Generate answer using repo context."""
        # Prepare context string (with token limit awareness)
        context_str = json.dumps(ctx.repo_context, indent=2)
        if len(context_str) > 16000:  # rough token limit
            # Truncate if too large
            context_str = context_str[:16000] + "\n... (context truncated)"

        messages = [
            {"role": "system", "content": REPO_PROMPT},
            {
                "role": "user",
                "content": f"Question: {ctx.repo_question}\n\nRepository context:\n{context_str}",
            },
        ]

        logger.info(f"[Repo] Generating answer for: {ctx.repo_question[:100]}...")
        reply = await llm.chat(messages)
        ctx.llm_raw_response = reply
        ctx.repo_answer = reply
        logger.info(f"[Repo] Answer generated: {len(reply)} chars")

    async def node_memory(ctx: RunContext) -> None:
        """Store repo Q&A in memory."""
        text = f"Repo: {ctx.repo_root}\nQ: {ctx.repo_question}\nA: {ctx.repo_answer}"
        item = MemoryItem.new(
            MemoryType.REPO_INSIGHT,
            text=text,
            meta={"repo_root": ctx.repo_root, "question": ctx.repo_question},
            tags=["repo", "qa", Path(ctx.repo_root or "").name],
        )
        memory.add(item)
        ctx.memory_items.append({"id": item.id, "type": str(item.type)})
        logger.info("[Repo] Q&A stored in memory")

    dag.add_node(DagNode("index", node_index, deps=[]))
    dag.add_node(DagNode("llm", node_llm, deps=["index"]))
    dag.add_node(DagNode("memory", node_memory, deps=["llm"]))

    return dag
