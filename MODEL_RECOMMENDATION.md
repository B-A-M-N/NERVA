# NERVA Model Recommendations

## Current Configuration
**Default model:** `qwen3:4b` (fast text model)

## The Problem with qwen3-vl:4b
`qwen3-vl:4b` is a **vision model** designed for image understanding. When used for text-only chat:
- Takes 20-60+ seconds per response
- Often times out (> 120 seconds)
- Uses excessive CPU/memory for simple text tasks
- Not suitable for interactive chat

## Recommended Models by Use Case

### For Text Chat (chat.py, voice commands)
Use **text-only models** - they're 10-20x faster:

```python
# Fast & efficient (recommended)
qwen_model: str = "qwen3:4b"              # Best balance
qwen_model: str = "qwen2.5:1.5b"          # Fastest
qwen_model: str = "llama3.1:8b"           # More capable

# Ultra-fast for testing
qwen_model: str = "qwen2.5:0.5b"          # Very fast but basic
```

### For Vision Tasks (screen understanding)
Use **vision models** - required for image analysis:

```python
qwen_model: str = "qwen3-vl:4b"           # Good vision + text
qwen_model: str = "qwen3-vl:8b"           # Better but slower
qwen_model: str = "llama3.2-vision"       # Alternative
```

## How to Switch Models

### Temporary (single command)
```bash
# Not directly supported in chat.py, but you can:
python -c "
from nerva.llm.qwen_client import QwenOllamaClient
import asyncio

async def test():
    client = QwenOllamaClient(model='llama3.1:8b')
    response = await client.chat([{'role': 'user', 'content': 'hello'}])
    print(response)

asyncio.run(test())
"
```

### Permanent (edit config)
```bash
# Edit nerva/config.py
nano nerva/config.py

# Change line 12:
qwen_model: str = "YOUR_MODEL_HERE"
```

## Performance Comparison

| Model | Speed | Quality | Use Case |
|-------|-------|---------|----------|
| qwen2.5:0.5b | ⚡⚡⚡ | ⭐⭐ | Quick testing |
| qwen2.5:1.5b | ⚡⚡ | ⭐⭐⭐ | Fast chat |
| qwen3:4b | ⚡ | ⭐⭐⭐⭐ | **Best for chat** |
| llama3.1:8b | ⚡ | ⭐⭐⭐⭐ | High quality |
| qwen3-vl:4b | 🐌 | ⭐⭐⭐⭐⭐ | **Vision only** |

## Current Issue (Fixed!)

**Problem:** qwen3-vl:4b timed out during chat
**Solution:** Switched to qwen3:4b for text chat
**Result:** Chat now responds in 3-10 seconds instead of 60+ seconds

## Best Practice

Use **separate models** for different workflows:

```python
# In nerva/console.py or custom scripts
text_llm = QwenOllamaClient(model="qwen3:4b")        # For chat
vision_llm = QwenOllamaClient(model="qwen3-vl:4b")   # For screenshots
```

This gives you fast text responses AND vision capabilities when needed.
