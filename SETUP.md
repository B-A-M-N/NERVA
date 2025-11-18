# NERVA Setup Guide

Complete setup instructions for NERVA and all dependencies.

---

## Prerequisites

### 1. Python 3.10+

```bash
python3 --version  # Should be 3.10 or higher
```

### 2. System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    portaudio19-dev \
    python3-dev \
    ffmpeg \
    libsndfile1
```

**macOS:**
```bash
brew install portaudio ffmpeg libsndfile
```

---

## Core Dependencies

### 1. SOLLOL (LLM Routing)

SOLLOL is your local LLM orchestration layer. Install from your local repo:

```bash
cd /path/to/SOLLOL
pip install -e .

# Verify installation
python -c "import sollol; print(sollol.__version__)"
```

**Or install Ollama as a simpler alternative:**

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull Qwen3-VL model
ollama pull qwen3-vl:4-8b

# Verify Ollama is running
ollama list
```

### 2. Kokoro-82M (Text-to-Speech)

Kokoro-82M is a fast, local TTS model. Installation depends on the specific implementation you're using.

**Option A: From Git Repository**

```bash
# Clone Kokoro repo (adjust URL to actual repo)
git clone https://github.com/yourusername/kokoro-82m.git /tmp/kokoro-82m
cd /tmp/kokoro-82m

# Install
pip install -e .

# Download model weights (if not included)
# Follow repo-specific instructions
```

**Option B: Manual Installation**

If Kokoro is not pip-installable yet, you can:

1. Clone/download the Kokoro-82M model files
2. Place in `~/.nerva/models/kokoro-82m/`
3. Update `nerva/voice/kokoro_tts.py` to load from that path

```python
# nerva/voice/kokoro_tts.py
class KokoroTTS:
    def __init__(self, model_path: str = "~/.nerva/models/kokoro-82m"):
        self.model_path = Path(model_path).expanduser()
        # Load model from self.model_path
```

**Verify Installation:**

```python
from nerva.voice.kokoro_tts import KokoroTTS
tts = KokoroTTS()
tts.speak("NERVA TTS is working")
```

### 3. Whisper (Speech Recognition)

**Option A: faster-whisper (Recommended for speed)**

```bash
pip install faster-whisper

# Test
python -c "from faster_whisper import WhisperModel; print('Whisper OK')"
```

**Option B: openai-whisper (Official implementation)**

```bash
pip install openai-whisper

# Download model
python -c "import whisper; whisper.load_model('tiny')"
```

**Verify Installation:**

```python
from nerva.voice.whisper_asr import WhisperASR
asr = WhisperASR(model_path="tiny")
```

---

## NERVA Installation

### 1. Clone and Install

```bash
cd /home/joker
git clone https://github.com/yourusername/NERVA.git
cd NERVA

# Install with all optional dependencies
pip install -e ".[all]"

# Or install specific features only
pip install -e ".[voice,vision,embeddings]"
```

### 2. Verify Installation

```bash
# Check that nerva command is available
nerva --help

# Or run directly
python -m nerva.main
```

### 3. Configure

Edit `nerva/config.py` to match your setup:

```python
@dataclass
class NervaConfig:
    # LLM settings
    ollama_base_url: str = "http://localhost:11434"  # Or SOLLOL endpoint
    qwen_model: str = "qwen3-vl:4-8b"

    # Paths
    repos_root: Path = Path.home() / "projects"
    memory_db_path: Path = Path.home() / ".nerva" / "memory.db"
    logs_path: Path = Path.home() / ".nerva" / "logs"

    # Voice settings
    whisper_model: str = "tiny"  # or "base", "small", "medium", "large"
    kokoro_model: str = "~/.nerva/models/kokoro-82m"  # adjust to your path
```

---

## Optional Dependencies

### 1. Screen Capture

**mss (Recommended - fast screenshot library):**

```bash
pip install mss

# Test
python -c "import mss; print('Screen capture OK')"
```

**Pillow (For clipboard and image processing):**

```bash
pip install pillow
```

### 2. Audio I/O

**sounddevice (Recommended for mic/speaker access):**

```bash
pip install sounddevice soundfile

# Test mic recording
python -c "import sounddevice as sd; print(sd.query_devices())"
```

### 3. Embeddings & Vector Search

**sentence-transformers (For mxbai-embed-large):**

```bash
pip install sentence-transformers

# Download model (optional, happens on first use)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('mxbai-embed-large')"
```

**ChromaDB (Vector database):**

```bash
pip install chromadb
```

**FAISS (Facebook's vector search - faster for large datasets):**

```bash
pip install faiss-cpu  # or faiss-gpu for GPU support
```

### 4. GitHub Integration

```bash
pip install pygithub

# Configure GitHub token (optional)
export GITHUB_TOKEN="your_token_here"
```

---

## Testing Your Setup

### 1. Test LLM Connection

```bash
python << 'EOF'
import asyncio
from nerva.llm.qwen_client import QwenOllamaClient

async def test():
    client = QwenOllamaClient()
    response = await client.chat([
        {"role": "user", "content": "Say 'NERVA is ready'"}
    ])
    print(response)

asyncio.run(test())
EOF
```

### 2. Test Daily Ops

```bash
nerva daily
```

Expected output:
```
==============================================================
DAILY OPS MODE
==============================================================

Summary:
[Your daily summary here]

Tasks (X):
1. [HIGH] Task 1
   → Reason...
...
```

### 3. Test Voice Mode

```bash
nerva voice "What is NERVA?"
```

### 4. Test Repo Mode

```bash
cd /home/joker/NERVA
nerva repo "Explain the DAG execution model"
```

---

## Troubleshooting

### LLM Connection Failed

```
Error: Connection refused to http://localhost:11434
```

**Solution:** Make sure Ollama or SOLLOL is running:

```bash
# For Ollama
ollama serve

# For SOLLOL
cd /path/to/SOLLOL
python -m sollol.server
```

### Kokoro TTS Not Working

```
Error: Kokoro model not found
```

**Solution:** Check your model path configuration:

```bash
ls ~/.nerva/models/kokoro-82m/
# Should contain model files

# Update config.py with correct path
```

### Whisper Import Error

```
ModuleNotFoundError: No module named 'whisper'
```

**Solution:** Install Whisper:

```bash
pip install openai-whisper
# or
pip install faster-whisper
```

### Screen Capture Not Working

```
RuntimeError: screenshot_bytes is missing
```

**Solution:** Implement screen capture in `nerva/vision/screenshot.py`:

```python
import mss
import mss.tools

def capture_screen() -> Optional[bytes]:
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # Primary monitor
        screenshot = sct.grab(monitor)
        return mss.tools.to_png(screenshot.rgb, screenshot.size)
```

---

## Next Steps

Once setup is complete:

1. **Run daily ops** to get familiar with the workflow
2. **Test voice commands** to verify ASR/TTS pipeline
3. **Query a repo** to see code understanding in action
4. **Customize workflows** in `nerva/workflows.py` for your needs
5. **Integrate SOLLOL** for advanced LLM routing
6. **Add HydraContext** for deeper code analysis

---

## Environment Variables (Optional)

Create a `.env` file in the NERVA directory:

```bash
# LLM
OLLAMA_BASE_URL=http://localhost:11434
QWEN_MODEL=qwen3-vl:4-8b

# Paths
NERVA_REPOS_ROOT=/home/joker/projects
NERVA_MEMORY_DB=/home/joker/.nerva/memory.db

# GitHub
GITHUB_TOKEN=your_token_here

# Voice
WHISPER_MODEL=tiny
KOKORO_MODEL=/home/joker/.nerva/models/kokoro-82m
```

Then load in `config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class NervaConfig:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    qwen_model: str = os.getenv("QWEN_MODEL", "qwen3-vl:4-8b")
    # ...
```

---

## Advanced: SOLLOL Integration

SOLLOL routing is plug-and-play (enabled by default). NERVA automatically probes
common hosts and discovered Ollama nodes to find the gateway, so you usually don't
need to set anything. Override via env vars only if you need a specific host/port:

1. Install SOLLOL (if you haven't):

```bash
cd /path/to/SOLLOL
pip install -e .
```

2. Set environment variables (or edit `NervaConfig`):

```bash
export NERVA_USE_SOLLOL=1      # optional; defaults to 1
export SOLLOL_BASE_URL=http://localhost:8000
export SOLLOL_MODEL=llama3.2
# optional priority override
export SOLLOL_PRIORITY=5
```

3. Start NERVA normally – all text chat goes through SOLLOL automatically, while
   screenshot/vision workflows continue to use your configured Qwen/Ollama instance.

---

Need to disable SOLLOL temporarily? `export NERVA_USE_SOLLOL=0` before launching.

---

You're now ready to run NERVA! 🚀
