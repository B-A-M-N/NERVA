# Test NERVA Voice with Your Microphone

## 🎤 Quick Start - Test Voice NOW!

```bash
# Easiest way - just run and speak!
python test_voice_live.py
```

When it says "SPEAK NOW!", say something like:
- "What is 2 plus 2?"
- "Tell me about quantum computing"
- "What's the capital of France?"

---

## All Voice Testing Options

### 1. **test_voice_live.py** ⭐ **RECOMMENDED**
**Simple, fast, works with your mic**
```bash
python test_voice_live.py
```
- Choose single test or continuous chat
- Records when you speak
- Shows transcription
- NERVA responds with voice

### 2. **test_microphone.py**
**Step-by-step testing**
```bash
python test_microphone.py
```
- Tests mic recording
- Tests Whisper transcription
- Tests full pipeline
- Great for debugging

### 3. **voice_chat.py**
**Full voice assistant**
```bash
python voice_chat.py
```
- Say "NERVA" to activate
- Continuous listening
- Full conversation mode
- Production-ready

### 4. **test_voice.py**
**Advanced testing**
```bash
# Live microphone test
python test_voice.py --mode live

# Batch automated tests
python test_voice.py --mode batch

# Mock test (no mic needed)
python test_voice.py --mode mock --text "test"
```

---

## Example: What You'll See

```bash
$ python test_voice_live.py

============================================================
🎤 NERVA Live Voice Test
============================================================

Initializing voice components...
✅ Ready!

🔴 Recording for 5 seconds - SPEAK NOW!
🎙️  Listening...

✅ You said: "what is 2 plus 2"

🤔 Processing...

🤖 NERVA: 2 + 2 = 4.

🔊 Speaking response...
[Plays audio]

✅ Test completed!
```

---

## Troubleshooting

**No speech detected?**
- Check mic is not muted
- Speak louder and closer
- Run: `python test_microphone.py` to debug

**Wrong transcription?**
- Reduce background noise
- Speak more clearly
- Use a better Whisper model (edit script: `model_path="base"`)

**No audio output?**
- Check speakers/volume
- Verify: `python -c "from nerva.voice.kokoro_tts import KokoroTTS; KokoroTTS().speak('test')"`

---

## Files Created

- `test_voice_live.py` - Quick mic testing (START HERE!)
- `test_microphone.py` - Detailed component testing
- `test_voice.py` - Advanced testing framework
- `voice_chat.py` - Full voice assistant (already existed)
- `VOICE_TESTING_GUIDE.md` - Complete documentation

---

## TL;DR

**Just want to test voice commands with your mic?**

```bash
python test_voice_live.py
```

**Then speak when prompted!** 🎤
