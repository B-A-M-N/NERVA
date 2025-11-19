# NERVA

**Neural Embodied Reasoning & Vision Assistant**

A local-first AI assistant with vision, voice, and browser automation. Routes LLMs via SOLLOL across your Ollama cluster. Complete privacy - zero cloud dependencies.

> **⚠️ PROJECT STATUS: Active Development**
>
> NERVA is a work-in-progress. Many features are functional, some are experimental, and others need verification. See the [Current Status](#current-status) section below for detailed breakdown.

---

## Current Status

### ✅ Working & Tested
- **SOLLOL Integration** - Fully integrated for LLM routing across Ollama clusters
- **Vision (Qwen3-VL)** - Browser automation with vision analysis via SOLLOL routing
- **Voice Interface** - Wake word detection (ONNX), Whisper ASR, Kokoro TTS
- **Browser Automation** - Playwright-based web interaction with deterministic playbooks
- **Task Dispatcher** - Routes voice/text commands to appropriate skills (calendar, email, drive, browser)
- **Google Skills** - Calendar, Gmail, Drive integration (OAuth-based)
- **Memory System** - In-memory knowledge store with semantic search
- **Knowledge Graph** - Entity relationship tracking across repos, people, services
- **Task Threads** - Persistent project thread tracking with entry logging

### 🔧 Implemented, Needs Testing
- **Automated Playbooks** - Declarative browser workflows for deterministic automation:
  - **Google Skills**: Calendar (day/week view, events, rescheduling), Gmail (inbox, compose, archive, labels, reply), Drive (search, upload, share)
  - **Lookup**: Google search with consent dismissal and first result navigation
  - **Research**: Multi-result SERP extraction with screenshot capture
  - **Generic Forms**: Login automation and arbitrary form submission
- **Desktop Automation** - PyAutoGUI wrapper for native app control
- **Daily Ops Cycles** - Scheduled summary generation from GitHub/TODO/system collectors
- **GitHub Autopilot** - Branch creation, PR management, troubleshooting
- **Finance Ledger** - CSV-backed personal expense tracking

### ⏳ Partially Implemented
- **Repo Analysis** - Code indexing exists, HydraContext integration pending
- **Screen Understanding** - Screenshot capture works, full DAG workflow needs testing
- **Vector Search** - Embedder client exists, FAISS/Chroma integration pending

### 📋 Planned / TODO
- Full HydraContext integration for deep codebase understanding
- Web UI for memory browsing and visualization
- TUI with Textual for better command-line UX
- Background scheduler for automated daily ops
- Hotkey bindings for screen/voice triggers
- VR/AR spatial workflow bindings

---

## Overview

NERVA is a multi-modal AI assistant that runs entirely on your local machine. It combines:

- **Screen Understanding** - Vision-capable LLM (Qwen3-VL) analyzes your workspace and suggests next actions
- **Voice Interface** - Whisper ASR + Kokoro TTS for hands-free operation
- **Repo-Aware Assistant** - Deep codebase understanding with HydraContext integration
- **Daily Ops Mode** - Personal SRE that aggregates GitHub, TODOs, logs, and system events
- **LLM-Native Memory** - Zettelkasten-style knowledge base with semantic search

Unlike cloud-based assistants, NERVA:
- Runs on your infrastructure with your models
- Never sends code or data to external APIs
- **Requires SOLLOL** for distributed LLM routing across Ollama clusters
- Uses DAG-based workflows for predictable, composable operations

---

## Architecture

NERVA uses a **DAG (Directed Acyclic Graph) execution model** where each workflow is composed of:

1. **RunContext** - Shared state passed through workflow nodes
2. **DAG Nodes** - Async functions that read/write context
3. **Workflows** - Pre-built DAGs for common tasks (screen, voice, repo, ops)

This design keeps workflows:
- **Explicit** - Easy to understand execution order
- **Composable** - Mix and match nodes
- **Testable** - Each node is an isolated async function
- **Observable** - Built-in logging and context tracking

### Components

```
nerva/
  config.py           # Global configuration
  types.py            # Core types and enums
  bus.py              # Event bus (optional pub/sub layer)
  run_context.py      # Shared workflow state
  dag.py              # DAG execution engine
  workflows.py        # Pre-built workflow definitions

  llm/
    client_base.py    # LLM client interface
    qwen_client.py    # Qwen3-VL via Ollama/SOLLOL

  vision/
    screenshot.py     # Screen capture utilities

  voice/
    whisper_asr.py    # Speech recognition
    kokoro_tts.py     # Text-to-speech

  repos/
    repo_index.py     # Code indexing and structure analysis

  memory/
    schemas.py        # Memory item types
    store.py          # In-memory knowledge store
    embedder.py       # Local embedding model client

  ops/
    collectors.py     # GitHub, logs, TODOs, system events

  hydra_adapter/
    context_builder.py # HydraContext integration (TODO)

  main.py             # CLI orchestrator
```

---

## Installation

### Prerequisites

1. **Python 3.10+**
2. **SOLLOL** - Required for distributed LLM routing across Ollama clusters
   ```bash
   pip install sollol
   ```
3. **Ollama instances** with Qwen3-VL model on cluster nodes:
   ```bash
   ollama pull qwen3-vl:4b
   ```
4. **Whisper** and **Kokoro** models (for voice interface)

### Install NERVA

```bash
# Clone the repository
git clone https://github.com/B-A-M-N/NERVA.git
cd NERVA

# Install with all dependencies
pip install -e ".[all]"

# Or install with specific extras only
pip install -e ".[voice,vision]"
```

### Configuration

Edit `nerva/config.py` or set environment variables:

```python
# nerva/config.py
@dataclass
class NervaConfig:
    ollama_base_url: str = "http://localhost:11434"
    qwen_model: str = "qwen3-vl:4-8b"
    repos_root: Path = Path.home() / "projects"
    memory_db_path: Path = Path.home() / ".nerva" / "memory.db"
```

---

## Usage

### CLI Mode

```bash
# Daily ops report
nerva daily

# Voice/text command
nerva voice "What should I work on next?"

# Repo query (analyzes current directory)
nerva repo "How does the routing engine work?"

# Screen understanding (requires screenshot implementation)
nerva screen

# Interactive REPL mode
nerva
```

### Interactive Mode

```
$ nerva

NERVA Interactive Mode
Commands:
  daily          - Run daily ops
  voice <text>   - Send voice/text command
  repo <q>       - Ask about current repo
  screen         - Analyze current screen
  exit           - Exit NERVA

nerva> daily
... (runs daily ops workflow)

nerva> voice Tell me about SOLLOL routing
... (processes command and responds)

nerva> repo What is the purpose of the DAG engine?
... (analyzes codebase and answers)
```

### Python API

```python
import asyncio
from nerva.main import NervaOrchestrator

async def main():
    orchestrator = NervaOrchestrator()

    # Run daily ops
    ctx = await orchestrator.run_daily_ops()
    print(ctx.daily_summary)

    # Ask about repo
    ctx = await orchestrator.run_repo_mode(
        question="Explain the memory system",
        repo_root="/home/user/nerva"
    )
    print(ctx.repo_answer)

asyncio.run(main())
```

---

## Workflows

### 1. Screen Understanding

**DAG:** `capture` → `llm_analyze` → `memory_write`

Captures screenshot, sends to Qwen3-VL, extracts:
- Visible repo/file
- Error messages
- User intent
- Suggested next actions

### 2. Voice Command

**DAG:** `input` → `intent_and_answer` → `memory_write`

Processes voice/text input, classifies intent (screen/repo/ops/generic), generates response, stores Q&A.

### 3. Daily Ops

**DAG:** `collect` → `llm` → `memory`

Aggregates:
- GitHub notifications
- Local TODOs
- System events (logs, SOLLOL status)

Produces prioritized task list for the day.

### 4. Repo-Aware Assistant

**DAG:** `index` → `llm` → `memory`

Indexes repository files, builds structured context (with HydraContext), answers code questions with file references.

---

## Extending NERVA

### Add a Custom Workflow

```python
from nerva.dag import Dag, DagNode
from nerva.run_context import RunContext

def build_my_workflow(llm, memory) -> Dag:
    dag = Dag("my-workflow")

    async def node_a(ctx: RunContext) -> None:
        # Do something
        ctx.extra["result"] = "foo"

    async def node_b(ctx: RunContext) -> None:
        # Depends on node_a
        result = ctx.extra["result"]
        # Process result

    dag.add_node(DagNode("a", node_a, deps=[]))
    dag.add_node(DagNode("b", node_b, deps=["a"]))

    return dag
```

### SOLLOL Integration (Fully Integrated ✅)

SOLLOL routing is **fully integrated** and enabled by default. NERVA automatically routes:
- **All LLM requests** through SOLLOL for intelligent load balancing across Ollama clusters
- **Vision requests** to GPU nodes with vision models (e.g., qwen3-vl:4b)
- **Text chat** to any available node in the cluster

Configuration via environment variables:

```bash
export NERVA_USE_SOLLOL=1          # Enable SOLLOL routing (default: enabled)
export SOLLOL_BASE_URL=http://localhost:8000  # SOLLOL gateway URL
export OLLAMA_NODES="localhost:11434,10.9.66.90:11434,10.9.66.154:11434"  # Cluster nodes
```

NERVA will automatically:
- Route all text chat through SOLLOL (`SolLolLLMClient`)
- Route vision requests (Qwen3-VL) through SOLLOL to GPU nodes
- Auto-detect the SOLLOL gateway if the default URL is unreachable
- Fall back to direct Ollama if SOLLOL is unavailable

To start SOLLOL with your cluster:

```bash
export OLLAMA_NODES="localhost:11434,10.9.66.90:11434,10.9.66.154:11434"
sollol up --port 8000
```

To disable routing (e.g., for fully offline demos):

```bash
export NERVA_USE_SOLLOL=0
```

### Git/GitHub Helpers

Use the bundled `github_tools.py` script for common git + GitHub management tasks:

```bash
# Show repo status / ahead-behind counts
python github_tools.py status

# Pull or push the current branch
python github_tools.py pull
python github_tools.py push

# Inspect PRs / issues / notifications via gh CLI
python github_tools.py prs --limit 5
python github_tools.py issues --limit 5
python github_tools.py notifications

# Diagnose common git problems (merge conflicts, untracked files, missing remotes, etc.)
python github_tools.py troubleshoot
```

Under the hood the script uses the new `nerva.github` package (`GitHubManager` + `GitTroubleshooter`) so you can import those classes directly when you need custom workflows.

### Add HydraContext

Implement in `nerva/hydra_adapter/context_builder.py`:

```python
from hydra_context import HydraContext

def build_context_for_repo(repo_root, question, max_tokens=8000):
    hydra = HydraContext(repo_root)
    return hydra.build_context(
        query=question,
        max_tokens=max_tokens,
        include_imports=True,
        include_definitions=True,
    )
```

### Task Threads & Knowledge Graph

Use `ThreadStore` to persist long-running project threads and `KnowledgeGraph` to connect related work across repos, people, and services.

```python
from nerva.task_tracking import ThreadStore
from nerva.knowledge import KnowledgeGraph

threads = ThreadStore()
thread = threads.create(project="infra", title="Improve observability")
threads.add_entry(thread.thread_id, "Investigated SOLLOL routing latency.")

graph = KnowledgeGraph()
graph.ingest_thread(thread.thread_id, thread.title, [entry.__dict__ for entry in thread.entries])
related = graph.related(thread.thread_id)
```

Pass `thread_store` and `knowledge_graph` into the `TaskDispatcher` to automatically log every routed task; each dispatcher call now belongs to a thread and is added to the graph for later recall.

### Desktop Automation & UI Playbooks

Need to control native apps or run deterministic multi-step flows? Use:

- `DesktopAutomation` (`nerva/desktop/automation.py`) – optional pyautogui wrapper for moving/clicking/typing outside the browser.
- `PlaybookRunner` (`nerva/automation/playbooks.py`) – declarative sequences of BrowserAutomation actions with guards (great for logins/approvals).
- Lookup templates (`nerva/automation/playbooks_lookup.py`) power tasks like “What’s the phone number for Target in Tinley Park?” by auto-running a Google search, opening results, and extracting the answer.
- Google-specific playbooks (`nerva/automation/playbooks_google.py`) cover Calendar (day/week/reschedule), Gmail (inbox/compose/archive/mark read/label/reply), and Drive (main/search/upload/share), so those skills can navigate reliably before vision analysis.
- Research and generic form helpers (`nerva/automation/playbooks_research.py`, `nerva/automation/playbooks_generic.py`) script SERP multi-result captures and common login/form submissions.

```python
from nerva.automation import Playbook, PlaybookStep
from nerva.agents import VisionActionAgent

playbook = Playbook(
    name="Approve expenses",
    steps=[
        PlaybookStep("open", "navigate", {"url": "https://expenses.example.com"}),
        PlaybookStep("login", "fill", {"selector": "#email", "text": "me@example.com"}, wait_for="#password"),
        PlaybookStep("submit", "click", {"selector": "button.submit"}),
    ],
)

agent = VisionActionAgent()
await agent.run_playbook(playbook)
```

### Daily Ops Cycles

`nerva/ops/cycles.py` introduces `DailyCycleManager`, a scheduler that combines collectors (GitHub/TODO/system/SOLLOL) with dispatcher commands:

```python
from nerva.ops.cycles import DailyCycleManager

cycles = DailyCycleManager(dispatcher, interval_minutes=60)
await cycles.start()  # runs summaries every hour
```

### Git/GitHub Autopilot

The updated `GitHubManager` (and `github_tools.py`) now support:
- Branch creation (`create_branch`)
- Automated PR creation/merging via `gh`
- Troubleshooting (merge conflicts, missing remotes, divergence) using `GitTroubleshooter`

```python
manager.create_branch("feature/vision-playbooks")
# after committing
manager.open_pull_request("Add vision playbooks", body="Implements stateful automation.")
```

### Finance & Life Management

`nerva/life/finance.py` ships a CSV-backed `FinanceLedger` so NERVA can log personal expenses/subscriptions and feed them into future planning flows.

```python
from nerva.life import FinanceLedger, BudgetEntry

ledger = FinanceLedger()
ledger.add_entry(BudgetEntry(category="SaaS", amount=29.99, description="VPS hosting"))
print(ledger.summarize())
```

---

## TODO / Roadmap

### ✅ Completed
- [x] Implement real screen capture (mss, pyautogui)
- [x] Wire Whisper ASR with mic input (parec-based for PulseAudio/PipeWire)
- [x] Integrate Kokoro TTS with audio playback
- [x] Add SOLLOL routing adapter (fully integrated)
- [x] Implement wake word detection (OpenWakeWord with ONNX backend)
- [x] Build browser automation with Playwright
- [x] Create deterministic playbooks for common tasks
- [x] Integrate Google Skills (Calendar, Gmail, Drive)
- [x] Add task dispatcher with intelligent routing
- [x] Implement memory store with semantic search
- [x] Add knowledge graph for entity relationships
- [x] Build task thread tracking system

### 🚧 In Progress
- [ ] Test and verify all 7 automated playbooks
- [ ] Full end-to-end voice assistant testing
- [ ] Vision model performance optimization
- [ ] Desktop automation testing (PyAutoGUI integration)

### 📋 Planned
- [ ] Add vector search with FAISS/Chroma (embedder client exists)
- [ ] Build HydraContext integration for deep repo understanding
- [ ] Create TUI with Textual for better UX
- [ ] Add background scheduler for daily ops (cycle manager exists)
- [ ] Implement hotkey bindings for screen/voice triggers
- [ ] Add memory export/import (JSON, SQLite)
- [ ] Build web UI for browsing memory/history
- [ ] Create VR/AR bindings for spatial workflows

---

## Architecture Notes

### Why DAGs instead of agents?

NERVA uses **explicit DAG workflows** rather than autonomous agents because:

1. **Predictability** - You know exactly what will execute and in what order
2. **Debuggability** - Easy to inspect context at any node
3. **Composability** - Mix and match nodes without callback hell
4. **Efficiency** - No unnecessary LLM calls or tool loops
5. **Control** - You decide when to run workflows, not the agent

For autonomous behavior, you can still:
- Trigger workflows via hotkeys, timers, or events
- Chain workflows based on intent classification
- Use the event bus for loose coupling between systems

### Memory System

NERVA's memory is designed to be **LLM-native**:

- Items stored as human-readable text + metadata
- Optional vector embeddings for semantic search
- Tags for quick filtering
- Types: Q&A, TODO, REPO_INSIGHT, DAILY_OP, SYSTEM

Eventually will support:
- Full Zettelkasten linking (backlinks, bidirectional references)
- Periodic summarization and consolidation
- Export to markdown for external tools (Obsidian, Logseq)

---

## License

MIT

---

## Contributing

Contributions welcome! This is a personal infrastructure tool that's being open-sourced.

Focus areas:
- Screen capture implementation
- Voice interface (Whisper + Kokoro)
- HydraContext integration
- SOLLOL adapter
- Memory persistence and vector search

---

## Acknowledgments

- **Qwen3-VL** for local vision understanding
- **Whisper** for robust ASR
- **Kokoro-82M** for fast, local TTS
- **SOLLOL** for LLM routing
- **HydraContext** for structured code understanding

Built for engineers who want full control over their AI tools without sending data to the cloud.
