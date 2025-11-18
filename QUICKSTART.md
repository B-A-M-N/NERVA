# NERVA Quickstart Guide

Get NERVA running in 5 minutes.

---

## 1. Prerequisites

Make sure you have:

- **Python 3.10+**
- **Ollama** running locally (or SOLLOL)

```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.com/install.sh | sh

# Pull Qwen3-VL model
ollama pull qwen3-vl:4-8b

# Verify Ollama is running
ollama list
```

---

## 2. Install NERVA

```bash
cd /home/joker/NERVA

# Install in development mode with core dependencies
pip install -e .

# Or install with all optional features
pip install -e ".[all]"
```

---

## 3. Run NERVA

### Option A: TUI Console (Recommended)

Launch the full Textual TUI interface:

```bash
nerva-console
```

This gives you a tabbed interface with:
- **F1** - Screen Understanding
- **F2** - Voice Commands
- **F3** - Daily Ops
- **F4** - Repo Assistant
- **F5** - Memory Browser
- **F6** - Node Status

### Option B: CLI Mode

Run individual workflows from the command line:

```bash
# Daily ops summary
nerva daily

# Voice/text command
nerva voice "What should I work on today?"

# Query current repo
cd /home/joker/NERVA
nerva repo "Explain the DAG execution model"

# Interactive REPL
nerva
```

---

## 4. Try It Out

### Test Voice Mode

In the TUI console:
1. Press **F2** to switch to Voice tab
2. Type: `NERVA, explain the workflow system`
3. Press Enter or click "Send Command"

Or via CLI:
```bash
nerva voice "NERVA, explain the workflow system"
```

### Test Daily Ops

In the TUI console:
1. Press **F3** to switch to Daily Ops tab
2. Click "Run Daily Ops DAG"

Or via CLI:
```bash
nerva daily
```

### Test Repo Assistant

In the TUI console:
1. Press **F4** to switch to Repo tab
2. Question: `What are the main components of NERVA?`
3. Click "Ask Question"

Or via CLI:
```bash
cd /home/joker/NERVA
nerva repo "What are the main components of NERVA?"
```

---

## 5. What Works Right Now

✅ **Voice Command Mode** - Text input → LLM response (full pipeline)
✅ **Daily Ops Mode** - Aggregates TODOs, logs, events (collectors are stubs)
✅ **Repo Assistant** - Indexes repos and answers questions (basic)
✅ **Memory System** - Stores all Q&A, insights, daily ops
✅ **TUI Console** - Full interactive interface
✅ **DAG Workflows** - All 4 workflows implemented

---

## 6. What Needs Implementation

⚠️ **Screen Capture** - Stub only, needs `mss` implementation
⚠️ **Voice ASR** - Whisper integration pending
⚠️ **Voice TTS** - Kokoro integration pending
⚠️ **SOLLOL Integration** - Node status, routing
⚠️ **HydraContext** - Structured code context
⚠️ **Vector Search** - Memory embeddings and semantic search
⚠️ **GitHub API** - Real notification/issue collection

See SETUP.md for detailed implementation instructions.

---

## 7. Configuration

Edit `nerva/config.py` to customize:

```python
@dataclass
class NervaConfig:
    # LLM
    ollama_base_url: str = "http://localhost:11434"
    qwen_model: str = "qwen3-vl:4-8b"

    # Paths
    repos_root: Path = Path.home() / "projects"
    memory_db_path: Path = Path.home() / ".nerva" / "memory.db"

    # Voice (when implemented)
    whisper_model: str = "tiny"
    kokoro_model: str = "kokoro-82m"
```

---

## 8. Troubleshooting

### "Connection refused" Error

```
Error: Connection refused to http://localhost:11434
```

**Fix:** Start Ollama:
```bash
ollama serve
```

### "ModuleNotFoundError: No module named 'textual'"

**Fix:** Install dependencies:
```bash
pip install -e .
```

### TUI Looks Broken

**Fix:** Make sure your terminal supports 256 colors:
```bash
echo $TERM  # Should show something like "xterm-256color"
```

---

## 9. Next Steps

1. **Explore the TUI** - Press F1-F6 to explore different modes
2. **Try Voice Commands** - Ask NERVA questions about your workflow
3. **Query Your Repos** - Use the Repo Assistant on your codebases
4. **Check Memory** - Browse what NERVA has learned
5. **Implement Stubs** - Start with screen capture or voice integration

See README.md for full architecture details and SETUP.md for implementation guides.

---

## 10. Example Session

```bash
# Launch console
$ nerva-console

# In the TUI:
# - Press F2 (Voice)
# - Type: "What is NERVA?"
# - Press Enter
# - See response in output panel

# - Press F3 (Daily Ops)
# - Click "Run Daily Ops DAG"
# - See summary and task list

# - Press F4 (Repo)
# - Question: "How does the DAG engine work?"
# - Click "Ask Question"
# - See detailed answer with file references

# - Press F5 (Memory)
# - Click "Refresh Memory View"
# - See all stored Q&A and insights

# - Ctrl+C to exit
```

---

You're now running NERVA! 🚀

For more detailed setup and implementation guides, see:
- **SETUP.md** - Complete dependency installation guide
- **README.md** - Full architecture documentation
- **nerva/workflows.py** - See how DAGs are structured
- **nerva/console.py** - TUI implementation details
