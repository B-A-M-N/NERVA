# NERVA Troubleshooting Guide

Common issues and solutions.

---

## Import Errors

### "cannot import name 'TextLog'"
**Fixed!** This was due to using the wrong widget name. The code now uses `RichLog` from Textual.

### "ModuleNotFoundError: No module named 'textual'"
```bash
pip install textual
# Or reinstall NERVA
pip install -e .
```

---

## Console Issues

### Console launches but shows "Mock Response"
This means Ollama/SOLLOL is not running or not reachable.

**Solution:**
```bash
# In another terminal, start Ollama
ollama serve

# Pull the model if you haven't
ollama pull qwen3-vl:4-8b

# Restart the console
nerva-console
```

**Check Ollama is running:**
```bash
curl http://localhost:11434/api/tags
# Should return JSON with available models
```

### "Connection refused" when running DAGs
Make sure Ollama is listening on the correct port:
```bash
# Check config
cat nerva/config.py | grep ollama_base_url

# Default should be: http://localhost:11434
```

If using a different port or SOLLOL:
```python
# Edit nerva/config.py
@dataclass
class NervaConfig:
    ollama_base_url: str = "http://localhost:YOUR_PORT"
```

### Console crashes with "can't set attribute 'log'"
**Fixed!** This was due to `log` being a reserved attribute in Textual. The code now uses `event_log`.

---

## Running the Console

### Method 1: Entry Point (Recommended)
```bash
nerva-console
```

If this doesn't work, you may need to reinstall:
```bash
pip install -e .
```

### Method 2: Direct Python
```bash
python -m nerva.console
```

### Method 3: Shell Script
```bash
./run_console.sh
```
This script checks if Ollama is running and shows helpful messages.

---

## Mock Mode

If you want to test the console without Ollama:

```python
# Edit nerva/console.py at the bottom
if __name__ == "__main__":
    run(use_mock_llm=True)  # Add this parameter
```

Or use the mock client programmatically:
```python
from nerva.console import NervaConsole

app = NervaConsole(use_mock_llm=True)
app.run()
```

---

## TUI Display Issues

### Colors don't show / TUI looks broken
Check your terminal supports 256 colors:
```bash
echo $TERM
# Should show something like "xterm-256color"
```

Set if needed:
```bash
export TERM=xterm-256color
```

### Layout is messed up
Try resizing your terminal window. Minimum recommended: 100x30 characters.

```bash
# Check terminal size
stty size
# Should show rows columns (e.g., 40 120)
```

---

## Workflow Errors

### Voice mode returns empty response
Check the LLM is actually being called:
```bash
# Watch Ollama logs
ollama logs

# Or check network
curl -X POST http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-vl:4-8b",
    "messages": [{"role": "user", "content": "test"}]
  }'
```

### Daily Ops shows no tasks
This is expected if:
- No GitHub notifications (stub not implemented)
- No TODOs in `~/notes/`
- No logs in `~/.nerva/logs/`

Create test data:
```bash
mkdir -p ~/notes
echo "- [ ] TODO: Test task" > ~/notes/test.md
```

### Repo mode says "no files found"
Make sure you're in a directory with code files:
```bash
ls *.py *.md *.toml
```

Or specify a repo path in the TUI input field.

---

## Performance Issues

### LLM responses are slow
This is normal for large models. Options:
1. Use a smaller model: `ollama pull qwen3-vl:2b`
2. Use faster-whisper instead of openai-whisper
3. Use GPU acceleration if available

### TUI is laggy
The TUI should be very fast. If it's slow:
1. Check CPU usage (LLM might be blocking)
2. Reduce log output verbosity
3. Clear memory periodically (F5 → view older items)

---

## Development Issues

### Changes to code don't take effect
Reinstall in development mode:
```bash
pip install -e . --force-reinstall
```

### Import errors after editing
Make sure all `__init__.py` files are present:

---

## Git / GitHub Issues

### "git push" fails / remote rejects
Use the helper to inspect branch state:
```bash
python github_tools.py status
```
Look for `Ahead` / `Behind` counts. If you're behind, run:
```bash
python github_tools.py pull
```
Resolve any conflicts, then push again.

### Merge conflicts
Detect conflicts and get fix instructions:
```bash
python github_tools.py troubleshoot
```
This runs the `GitTroubleshooter` checks (merge conflicts, untracked files, missing remotes, etc.) and prints step-by-step fixes.

### Need to review PRs/issues quickly
The script proxies the GitHub CLI (`gh`). Examples:
```bash
python github_tools.py prs --limit 5
python github_tools.py issues --limit 10
python github_tools.py notifications
```
Make sure `gh auth login` has been run beforehand.
```bash
python verify.py
```

---

## Still Having Issues?

1. **Run verification script:**
   ```bash
   python verify.py
   ```

2. **Check logs:**
   ```bash
   ls ~/.nerva/logs/
   tail ~/.nerva/logs/nerva.log  # If exists
   ```

3. **Try mock mode:**
   ```python
   python -m nerva.console  # Will auto-fallback to mock if Ollama fails
   ```

4. **Test components individually:**
   ```bash
   # Test LLM
   python -c "from nerva.llm.qwen_client import QwenOllamaClient; import asyncio; asyncio.run(QwenOllamaClient().chat([{'role':'user','content':'test'}]))"

   # Test memory
   python -c "from nerva.memory.store import MemoryStore; s = MemoryStore(); print('Memory OK')"

   # Test workflows
   python -c "from nerva.workflows import build_voice_dag; print('Workflows OK')"
   ```

5. **Check GitHub issues:**
   Look for similar issues or open a new one with:
   - Error message
   - Output of `python verify.py`
   - Python version: `python --version`
   - OS: `uname -a`

---

## Quick Fixes Summary

```bash
# Reinstall everything
pip uninstall nerva
pip install -e .

# Start Ollama
ollama serve

# Pull model
ollama pull qwen3-vl:4-8b

# Launch console
nerva-console

# Or use helper script
./run_console.sh
```
