# NERVA Voice Testing Guide - Real Microphone Testing

This guide shows you how to test NERVA's voice commands with your actual microphone.

---

## Quick Start - Test Voice Commands Now!

### Option 1: Simple Live Voice Test (Recommended)
```bash
python test_voice_live.py
```

This will:
1. Let you choose single test or continuous chat
2. Record 5 seconds when you speak
3. Transcribe your speech with Whisper
4. Send to NERVA's LLM
5. Speak the response back to you

### Option 2: Full Microphone Test Suite
```bash
python test_microphone.py
```

Tests everything step-by-step:
- ✅ Microphone recording
- ✅ Whisper transcription
- ✅ Full voice pipeline (mic → transcription → LLM → TTS)

### Option 3: Full Voice Chat (Production)
```bash
python voice_chat.py
```

Complete voice assistant:
- Continuous listening
- Wake word detection ("NERVA")
- Full conversation memory
- Natural voice responses

---

## Testing Methods Comparison

| Method | Use Case | Microphone | Real-time |
|--------|----------|------------|-----------|
| `test_voice_live.py` | Quick functional testing | ✅ Yes | ✅ Yes |
| `test_microphone.py` | Detailed component testing | ✅ Yes | ✅ Yes |
| `voice_chat.py` | Full voice assistant | ✅ Yes | ✅ Yes |
| `test_voice.py --mode live` | Automated testing | ✅ Yes | ✅ Yes |
| `test_voice.py --mode mock` | No mic needed | ❌ No | ❌ No |

---

## Step-by-Step: Testing Voice Commands

### Step 1: Check Your Microphone

```bash
# List available audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"
```

Look for a device marked with `*` (default) or one that says "Microphone".

### Step 2: Quick Single Command Test

```bash
python test_voice_live.py
```

**What happens:**
```
============================================================
🎤 NERVA Live Voice Test
============================================================

Initializing voice components...
✅ Ready!

============================================================
🔴 Recording for 5 seconds - SPEAK NOW!
============================================================
Example commands:
  - What is 2 plus 2?
  - Tell me about quantum computing
  - What's the capital of France?

🎙️  Listening...
```

**Then speak clearly into your microphone!**

### Step 3: Verify the Results

You should see:
```
✅ You said: "what is 2 plus 2"

🤔 Processing...

🤖 NERVA: 2 + 2 = 4.

🔊 Speaking response...
[Audio plays: "2 plus 2 equals 4"]

============================================================
✅ Test completed!
============================================================
```

---

## Continuous Voice Chat Testing

Want to have a back-and-forth conversation? Use continuous mode:

```bash
python test_voice_live.py
# Choose option 2 or 3
```

**Example conversation:**
```
🎙️  Listening for 5 seconds...

👤 You: what is 2 plus 2

🤖 NERVA: 2 + 2 = 4.

🎙️  Listening for 5 seconds...

👤 You: and what is 10 minus 3

🤖 NERVA: 10 - 3 = 7.

🎙️  Listening for 5 seconds...

👤 You: goodbye

👋 Goodbye!
```

---

## Full Voice Chat with Wake Word

For the complete experience with wake word detection:

```bash
python voice_chat.py
```

**Usage:**
1. The app continuously listens
2. Say "**NERVA**" followed by your command
3. Example: "NERVA, what is the weather today?"
4. NERVA responds with voice
5. Say "NERVA exit" or "NERVA goodbye" to stop

---

## Troubleshooting

### No Speech Detected

**Problem:** `❌ No speech detected`

**Solutions:**
1. **Check microphone is not muted:**
   ```bash
   # Linux: Check PulseAudio mixer
   pavucontrol
   ```

2. **Speak louder and clearer:**
   - Get closer to the microphone
   - Speak in a quiet environment
   - Speak for the full 5 seconds

3. **Test microphone separately:**
   ```bash
   # Record a test
   arecord -d 3 test.wav
   # Play it back
   aplay test.wav
   ```

4. **Check audio device:**
   ```python
   import sounddevice as sd
   print(sd.query_devices())
   # Look for your microphone
   ```

### Transcription Issues

**Problem:** Wrong transcription or garbled text

**Solutions:**
1. **Use a better Whisper model:**
   ```python
   # In test scripts, change:
   asr = WhisperASR(model_path="tiny")
   # To:
   asr = WhisperASR(model_path="base")  # Better accuracy
   ```

2. **Reduce background noise:**
   - Move to a quieter room
   - Close windows/doors
   - Turn off fans/AC

3. **Speak more clearly:**
   - Articulate words
   - Speak at moderate pace
   - Avoid mumbling

### TTS Not Working

**Problem:** No audio output from NERVA

**Solutions:**
1. **Check speakers/headphones:**
   ```bash
   # Test system audio
   speaker-test -t wav -c 2
   ```

2. **Verify Kokoro is installed:**
   ```bash
   python -c "from nerva.voice.kokoro_tts import KokoroTTS; tts = KokoroTTS(); tts.speak('test')"
   ```

3. **Check TTS fallback:**
   - If Kokoro fails, NERVA uses pyttsx3
   - Install with: `pip install pyttsx3`

---

## Advanced Testing

### Test Different Recording Durations

```python
# Shorter recording (3 seconds)
python test_voice.py --mode live --duration 3

# Longer recording (10 seconds)
python test_voice.py --mode live --duration 10
```

### Test with Different Whisper Models

**Available models:**
- `tiny` - Fastest, least accurate (default for testing)
- `base` - Good balance
- `small` - Better accuracy
- `medium` - Very good accuracy (slower)
- `large` - Best accuracy (very slow)

Edit any test script and change:
```python
asr = WhisperASR(model_path="base")  # or "small", "medium", etc.
```

### Test with GPU Acceleration

```bash
# Set environment variable
export WHISPER_DEVICE=cuda

# Then run any test
python test_voice_live.py
```

---

## What Each Test Script Does

### `test_voice_live.py` ⭐ **Start here!**
- **Purpose:** Quick, easy voice command testing
- **Best for:** Verifying microphone and voice pipeline work
- **Features:** Single test or continuous chat mode
- **Time:** ~10 seconds per test

### `test_microphone.py`
- **Purpose:** Detailed component-by-component testing
- **Best for:** Debugging specific issues
- **Features:** Tests recording, transcription, and full pipeline separately
- **Time:** ~1 minute total

### `voice_chat.py`
- **Purpose:** Full production voice assistant
- **Best for:** Real usage and extended conversations
- **Features:** Wake word detection, conversation memory, continuous listening
- **Time:** Runs until you say "exit"

### `test_voice.py`
- **Purpose:** Automated testing framework
- **Best for:** CI/CD, batch testing, no-mic testing
- **Features:** Multiple modes (live, mock, file, batch)
- **Time:** Varies by mode

---

## Example Test Session

Here's a complete test session from start to finish:

```bash
# 1. Check microphone is available
$ python -c "import sounddevice as sd; print(sd.query_devices())" | grep -i mic
  10 sof-hda-dsp Digital Microphone, JACK Audio Connection Kit (2 in, 0 out)

# 2. Run quick live test
$ python test_voice_live.py

============================================================
NERVA Live Voice Testing
============================================================

Choose test mode:
  1. Single command test
  2. Continuous voice chat
  3. Both (single test first, then continuous)

Enter choice (1/2/3) [default: 1]: 1

============================================================
🎤 NERVA Live Voice Test
============================================================

Initializing voice components...
✅ Ready!

============================================================
🔴 Recording for 5 seconds - SPEAK NOW!
============================================================
Example commands:
  - What is 2 plus 2?
  - Tell me about quantum computing
  - What's the capital of France?

🎙️  Listening...

✅ You said: "what is 2 plus 2"

🤔 Processing...

🤖 NERVA: 2 + 2 = 4.

🔊 Speaking response...
[Plays audio: "2 plus 2 equals 4"]

============================================================
✅ Test completed!
============================================================
```

---

## Summary - Quick Commands

**Test with microphone right now:**
```bash
python test_voice_live.py
```

**Test full pipeline step-by-step:**
```bash
python test_microphone.py
```

**Full voice chat with wake word:**
```bash
python voice_chat.py
```

**All test modes:**
```bash
# Live mic test
python test_voice.py --mode live

# Mock test (no mic)
python test_voice.py --mode mock --text "hello"

# Batch test
python test_voice.py --mode batch
```

---

## Next Steps

1. **Start with:** `python test_voice_live.py`
2. **If issues:** `python test_microphone.py` to debug
3. **For real use:** `python voice_chat.py`
4. **For automation:** `python test_voice.py --mode batch`

Your microphone is ready! Just run the scripts and start talking to NERVA.
