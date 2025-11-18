# NERVA - Model Configuration

Quick guide for choosing and configuring LLM models.

---

## Current Default

```python
# nerva/config.py
qwen_model: str = "qwen3-vl:4b"
```

**Note:** This model supports vision (screen understanding). To use it:
```bash
ollama pull qwen3-vl:4b
```

---

## For Text-Only Chat (Recommended)

If you just want to use the chat/voice/repo features (no screen understanding), use any text model:

### Option 1: Use Llama 3 (Most Common)

```bash
# Pull the model
ollama pull llama3

# Or smaller/faster versions
ollama pull llama3:8b
ollama pull llama3.2
```

Then edit `nerva/config.py`:
```python
qwen_model: str = "llama3"
```

### Option 2: Use Qwen 2 (Good Balance)

```bash
ollama pull qwen2:7b
```

```python
qwen_model: str = "qwen2:7b"
```

### Option 3: Use Tiny Models (Fast Testing)

```bash
ollama pull tinyllama
# or
ollama pull phi
```

```python
qwen_model: str = "tinyllama"
```

---

## For Vision + Text (Screen Understanding)

If you want the full NERVA experience including screen analysis:

### Qwen3-VL (Recommended)

```bash
ollama pull qwen3-vl:4-8b
# or
ollama pull qwen3-vl:2b  # Smaller, faster
```

```python
qwen_model: str = "qwen3-vl:4-8b"
```

### LLaVA (Alternative)

```bash
ollama pull llava
```

```python
qwen_model: str = "llava"
```

---

## Check What You Have

```bash
ollama list
```

Shows all installed models. Use any name from that list in your config.

---

## Model Sizes & Performance

| Model | Size | Speed | Quality | Vision |
|-------|------|-------|---------|--------|
| tinyllama | ~600MB | Very Fast | Basic | No |
| phi | ~1.6GB | Fast | Good | No |
| qwen2:7b | ~4GB | Medium | Great | No |
| llama3:8b | ~4.7GB | Medium | Excellent | No |
| qwen3-vl:2b | ~2GB | Fast | Good | Yes |
| qwen3-vl:4-8b | ~5GB | Medium | Excellent | Yes |
| llava | ~4.5GB | Medium | Very Good | Yes |

---

## Quick Setup

**Just want to test right now?**

```bash
# Pull a small model
ollama pull phi

# Update config
sed -i 's/qwen3-vl:4-8b/phi/' nerva/config.py

# Or use mock mode (no model needed)
python chat.py --mock
```

**Want the full experience?**

```bash
# Pull the vision model (takes a few minutes)
ollama pull qwen3-vl:4-8b

# Config is already set for this
python chat.py "What is NERVA?"
```

---

## Troubleshooting

### "Model not found" error

```bash
# Check what models you have
ollama list

# Pull the model you need
ollama pull <model-name>

# Update config to match
```

### Ollama not responding

```bash
# Start Ollama server
ollama serve

# Test it's running
curl http://localhost:11434/api/tags
```

### Want to use a different model just once?

You can't do this via chat.py directly, but you can:

1. Temporarily edit `nerva/config.py`
2. Or create a custom script:

```python
from nerva.llm.qwen_client import QwenOllamaClient
import asyncio

async def main():
    llm = QwenOllamaClient(model="llama3")  # Use any model
    response = await llm.chat([
        {"role": "user", "content": "Hello!"}
    ])
    print(response)

asyncio.run(main())
```

---

## SOLLOL Users

If you're using SOLLOL for routing, you don't need to worry about specific models. SOLLOL will route to the appropriate model automatically.

Create a SOLLOL client adapter (see SETUP.md for details).

---

## Recommended Setup by Use Case

**Just testing NERVA:**
```bash
python chat.py --mock  # No model needed
```

**Daily use (text only):**
```bash
ollama pull llama3
# Edit config: qwen_model = "llama3"
```

**Full features (vision):**
```bash
ollama pull qwen3-vl:4-8b
# Config already set
```

**Fastest possible:**
```bash
ollama pull tinyllama
# Edit config: qwen_model = "tinyllama"
```

**Best quality:**
```bash
ollama pull llama3:70b  # If you have GPU
# Edit config: qwen_model = "llama3:70b"
```

---

See **SETUP.md** for more details on Ollama installation and configuration.
