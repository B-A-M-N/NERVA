# NERVA - Start Here 🚀

You have **3 ways to talk to NERVA** right now:

---

## ✅ Method 1: Simple Text Chat (EASIEST)

```bash
python chat.py
```

Then just type your questions!

**Try it:**
```bash
python chat.py --mock "What is NERVA?"
```

Works without Ollama using mock responses.

---

## ✅ Method 2: TUI Console (FULL FEATURES)

```bash
nerva-console
```

- Press **F2** for Voice (text input)
- Press **F3** for Daily Ops summary
- Press **F4** to query repos
- Press **F5** to browse memory

---

## ✅ Method 3: CLI Commands

```bash
nerva voice "What should I work on?"
nerva daily
nerva repo "How does the DAG work?"
```

---

## 🔥 Quick Start Right Now

```bash
# 1. Simple chat (works immediately - no setup!)
python chat.py --mock

# Type: What can you help me with?
# Type: /quit to exit

# 2. Single question
python chat.py --mock "Explain NERVA workflows"

# 3. With real LLM (requires Ollama + model)
# First: ollama serve (in another terminal)
# Then: ollama pull llama3  (or any model - see MODELS.md)
python chat.py "What is NERVA?"
```

---

## 📚 Documentation

- **HOW_TO_CHAT.md** - All chat methods explained
- **QUICKSTART.md** - 5-minute setup guide
- **VOICE_SETUP.md** - Enable hands-free voice
- **README.md** - Full architecture docs
- **TROUBLESHOOTING.md** - Common issues

---

## 🎤 Want Voice Chat?

**Text mode works now.** Voice (mic input) needs:
1. Install Whisper: `pip install faster-whisper`
2. Implement stub in `nerva/voice/whisper_asr.py`

See **VOICE_SETUP.md** for details.

---

## ⚡ TL;DR

**Just want to chat?**
```bash
python chat.py --mock
```

**Want the full experience?**
```bash
nerva-console
```

That's it! Start chatting!
