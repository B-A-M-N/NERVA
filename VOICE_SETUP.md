# Setting Up Voice Chat for NERVA

Hands-free control now works end-to-end: Whisper-based ASR records from the microphone, and Kokoro TTS (with fallbacks) speaks responses. This guide shows the minimal steps to get both pieces online.

---

## Current Status
- ✅ **Text Chat** – fully functional (`python chat.py`)
- ✅ **Voice Input (ASR)** – Whisper integration (faster-whisper or openai-whisper) with mic recording
- ✅ **Voice Output (TTS)** – Kokoro implementation with pyttsx3/system fallbacks

---

## Quick Start

```bash
# 1. Install voice dependencies
pip install faster-whisper sounddevice soundfile  # or: pip install openai-whisper

# 2. (Optional) Install Kokoro from your source repo (see KOKORO_SETUP.md)

# 3. Launch full voice chat
python voice_chat.py
```

`voice_chat.py` now listens for the wake word **“NERVA”** (or runs in continuous barge-in mode), captures speech until you’ve been silent for a couple seconds, and then routes the transcript through the TaskDispatcher (so Calendar/Gmail/Drive and the vision/browser agent are available). Responses are spoken via `KokoroTTS`.

---

## Testing Components Individually

### Verify ASR
```python
from nerva.voice.whisper_asr import WhisperASR
asr = WhisperASR("tiny")
print(asr.transcribe_once(duration=3) or "No speech detected")
```
- Uses `faster-whisper` if installed, otherwise `openai-whisper`.
- Records from the default microphone via `sounddevice`/`soundfile`. Pass `audio_path="file.wav"` to transcribe existing audio without recording.

### Verify TTS
```python
from nerva.voice.kokoro_tts import KokoroTTS
tts = KokoroTTS()
tts.speak("NERVA voice output is online.")
```
- Prefers Kokoro ONNX models.
- Falls back to `pyttsx3`, `say`, `espeak`, or console printing if audio backends are missing.

---

## Voice Chat Flow
1. **Listen** – `WhisperASR.transcribe_until_silence()` waits for speech, keeps a rolling buffer, and stops when you’ve been quiet for ~3s (or hits the `--max-duration` cap). Continuous “barge-in” mode (`--barge-in`) skips the wake word entirely.
2. **Process** – The transcript is sent to `TaskDispatcher`, which decides whether to run Google skills, the VisionActionAgent (for web searches), or a generic voice response. Memory, task threads, and the knowledge graph are updated automatically.
3. **Speak** – `KokoroTTS.speak()` plays the dispatcher summary (and any extracted “answer” payload, e.g., phone numbers).
4. **Loop** – The cycle repeats until you say “exit”/`Ctrl+C`.

**Advanced flags:**
```bash
python voice_chat.py --barge-in --silence 2 --max-duration 20 \
    --profile ~/.config/google-chrome/Default
```
- `--barge-in` – always listening; no wake word needed.
- `--silence` / `--max-duration` / `--min-duration` – tune detection window.
- `--profile` – reuse a Chrome profile for Google Calendar/Gmail/Drive tasks.

---

## Troubleshooting
- **No microphone detected** – Install `sounddevice` + system PortAudio (`sudo apt install portaudio19-dev`) and ensure the device isn’t muted.
- **Transcription empty** – Increase `duration`, reduce background noise, or test with `asr.transcribe_once(audio_path="sample.wav")`.
- **Kokoro errors** – Follow `KOKORO_SETUP.md`; if unavailable, `pyttsx3`/system TTS handles speech.
- **Use GPU for Whisper** – Set `WHISPER_DEVICE=cuda` before running to load the faster-whisper model on GPU.

Once both ASR and TTS pass their standalone tests, `python voice_chat.py` delivers a complete, local voice loop powered by Ollama + Kokoro.
