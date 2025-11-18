# How to Talk to NERVA

Quick reference for all the ways to interact with NERVA.

---

## 🎯 Text Chat (Easiest - Works Now!)

### Method 1: Simple Chat Script ⭐ RECOMMENDED

```bash
python chat.py
```

**Interactive conversation:**
```
You: What is NERVA?
NERVA: NERVA is a local cognitive exoskeleton for AI infrastructure engineers...

You: What should I work on today?
NERVA: [gives suggestions based on context]

You: /memory
📝 Shows recent conversations

You: /screen
📸 Captures current desktop and runs the screen DAG

You: /quit
```

**Single question:**
```bash
python chat.py "Explain the DAG execution model"
```

**Works without Ollama (mock mode):**
```bash
python chat.py --mock
```

---

### Method 2: TUI Console

```bash
nerva-console
```

1. Press **F2** (Voice tab)
2. Type your question
3. Press **Enter**
4. See response below

**Pros:**
- Beautiful interface
- Multi-tab (Voice, Daily Ops, Repo, Memory)
- Live event logs
- Keyboard shortcuts (F1-F6)

**Cons:**
- More complex UI if you just want chat

---

### Method 3: CLI Commands

```bash
# Ask a question
nerva voice "What is NERVA?"

# Interactive REPL
nerva
# Then type: voice <your question>
```

---

## 🎤 Voice Chat (Requires Setup)

### Full Voice (Needs Whisper + Kokoro)

**1. Install dependencies:**
```bash
pip install faster-whisper sounddevice soundfile
```

**2. Implement ASR stub** in `nerva/voice/whisper_asr.py`

See `VOICE_SETUP.md` for complete instructions.

**3. Run voice chat:**
```bash
python voice_chat.py

# or use the chat script in voice mode
python chat.py --voice
```

Now you can actually speak to NERVA!

---

## 📊 Which Method Should I Use?

### Just want to chat? → `python chat.py`
- Cleanest text chat experience
- Works immediately
- No complex UI

### Want full features? → `nerva-console`
- Daily ops summary
- Repo querying
- Memory browser
- Node status (when implemented)

### Want hands-free? → Setup voice (see VOICE_SETUP.md)
- Requires Whisper + Kokoro
- Once installed, run `python chat.py --voice` (wake word “NERVA”)
- Or run `python voice_chat.py` for a dedicated voice loop

### Scripting/automation? → `nerva voice "question"`
- Command line integration
- Good for scripts
- One-shot questions

---

## 🔥 Quick Examples

### Daily Standup

```bash
python chat.py "What should I focus on today?"
```

or

```bash
nerva-console
# Press F3 for Daily Ops
# Click "Run Daily Ops DAG"
```

### Code Questions

```bash
python chat.py "Explain how the DAG engine works"
```

or

```bash
nerva repo "How does the DAG engine work?"
```

### Debugging Help

```bash
python chat.py "I'm getting an import error in console.py, what should I check?"
```

### Planning

```bash
python chat.py
```
```
You: I need to add screen capture support. What's the best approach?
NERVA: To add screen capture...

You: Should I use mss or pyautogui?
NERVA: mss is recommended because...

You: Show me example code
NERVA: Here's how to implement...
```

---

## ⚙️ Configuration

All chat methods use the same config in `nerva/config.py`:

```python
@dataclass
class NervaConfig:
    ollama_base_url: str = "http://localhost:11434"
    qwen_model: str = "qwen3-vl:4-8b"
```

**To use SOLLOL instead:**
```python
ollama_base_url: str = "http://localhost:YOUR_SOLLOL_PORT"
```

**To use different model:**
```bash
ollama pull llama3
```

```python
qwen_model: str = "llama3"
```

---

## 🚀 Start Chatting Right Now

```bash
# 1. Make sure you're in NERVA directory
cd /home/joker/NERVA

# 2. Start Ollama (in another terminal)
ollama serve

# 3. Start chatting!
python chat.py
```

That's it! No complex setup required for text chat.

---

## 💡 Pro Tips

### Save chat history
The memory system automatically saves all Q&A:
```bash
python chat.py
You: /memory
# Shows recent conversations
```

### Use with different repos
```bash
cd /path/to/your/project
python /home/joker/NERVA/chat.py "Explain this codebase"
```

### Quick daily summary
```bash
alias daily="python /home/joker/NERVA/chat.py 'Give me a daily ops summary'"
daily
```

### Create chat alias
```bash
# Add to ~/.bashrc
alias nerva-chat="python /home/joker/NERVA/chat.py"

# Then just:
nerva-chat "your question"
```

---

## 🐛 Troubleshooting

**"Connection refused"** → Start Ollama: `ollama serve`

**"Mock responses"** → Ollama not running, or wrong URL in config

**Slow responses** → Normal for large models, use smaller model or GPU

**No response** → Check Ollama logs: `ollama logs`

See **TROUBLESHOOTING.md** for more help.

---

## What's Next?

- ✅ Start with `python chat.py` (works now)
- 📱 Try TUI for full experience: `nerva-console`
- 🎤 Setup voice when ready (see VOICE_SETUP.md)
- 🔧 Integrate SOLLOL for routing
- 🧠 Add HydraContext for better code understanding

Happy chatting! 🚀
