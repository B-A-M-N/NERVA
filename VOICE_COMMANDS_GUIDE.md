# How to Use NERVA with Voice Commands

Your microphone is now working! Here are all the ways to use voice with NERVA.

---

## Option 1: Full Voice Chat ⭐

**Best for:** Hands-free conversation with NERVA

```bash
python voice_chat.py
```

**How it works:**
1. Records audio in 5-second windows
2. Transcribes with Whisper
3. NERVA processes and responds
4. Repeats - say "exit" or "goodbye" to stop

**Example conversation:**
```
🎤 Listening (5s)...
👤 You: "What is the capital of France?"
🤖 NERVA: "The capital of France is Paris."

🎤 Listening (5s)...
👤 You: "Tell me about quantum computing"
🤖 NERVA: [responds]

🎤 Listening (5s)...
👤 You: "exit"
👋 Goodbye!
```

**Options:**
```bash
# Custom recording duration (longer for complex questions)
python voice_chat.py --duration 10

# Enable wake word detection (say "Alexa" to activate)
python voice_chat.py --wake-word
```

**Wake Word Mode:**
- Say "**Alexa**" to activate NERVA
- Then speak your command within 5 seconds
- Low CPU usage when idle (only lightweight detector running)
- Custom "NERVA" wake word model coming soon!

---

## Option 2: Test Voice (Single Command)

**Best for:** Quick testing

```bash
python test_voice_live.py
```

Choose option 1 (Single command test):
- Records for 5 seconds
- Transcribes your speech
- NERVA responds
- Done

---

## Option 3: Test Voice (Continuous)

```bash
python test_voice_live.py
```

Choose option 2 (Continuous chat):
- Records 5 seconds, you speak
- NERVA responds
- Repeat
- Say "exit" or "goodbye" to stop

---

## Option 4: Command Line Voice Mode

```bash
python test_voice.py --mode live
```

Records and processes a single voice command.

---

## Adding Voice to Regular Chat

You can add voice input to the regular chat interface:

### Create voice-enabled chat.py

```bash
# Currently chat.py is text-only
# We can add a --voice flag
```

Let me create this for you...

---

## Wake Word vs No Wake Word

**With wake word** (`voice_chat.py`):
- Say "NERVA" before each command
- Filters out background conversation
- More natural for always-on assistant

**No wake word** (`test_voice_live.py` option 2):
- Just speak when recording starts
- Better for focused sessions
- Less natural language overhead

---

## Voice Command Examples

**Questions:**
- "NERVA, what is 2 plus 2?"
- "NERVA, explain quantum computing"
- "NERVA, what's the capital of France?"

**Tasks:**
- "NERVA, remind me to call John"
- "NERVA, what's on my schedule?"
- "NERVA, search for Python tutorials"

**Control:**
- "NERVA exit" - Exit voice chat
- "NERVA goodbye" - Exit voice chat
- Press Ctrl+C anytime to stop

---

## Summary of Voice Scripts

| Script | Mode | Wake Word | Use Case |
|--------|------|-----------|----------|
| `voice_chat.py` | Continuous | Yes ("NERVA") | Production, hands-free |
| `test_voice_live.py` (opt 1) | Single | No | Quick test |
| `test_voice_live.py` (opt 2) | Continuous | No | Testing sessions |
| `test_voice.py --mode live` | Single | No | Automated testing |

---

## Next: Add Voice to Main Chat

Want voice commands in the main `chat.py`? I can add a `--voice` flag!
