# Wake Word Detection Implementation

## Current Status

✅ **Implemented**: Wake word detection framework using openWakeWord
⚠️ **Pending**: Pre-trained model files need to be downloaded or custom "NERVA" model trained

## What Was Built

### 1. Wake Word Detector Module (`nerva/voice/wake_word.py`)

A lightweight wake word detector that:
- Uses openWakeWord with TFLite inference
- Continuously listens with minimal CPU usage
- Only activates Whisper when wake word detected
- Supports custom wake word models

**Key Features:**
- `listen_once(timeout)` - Wait for wake word with timeout
- `listen_continuous(callback)` - Continuous listening mode
- Configurable confidence threshold
- PulseAudio/PipeWire compatible (uses `parec`)

### 2. Updated Voice Chat (`voice_chat.py`)

Two modes:
1. **Continuous Recording (default)** - Records in N-second windows, transcribes each
2. **Wake Word Mode (experimental)** - Only activates on wake word detection

```bash
# Default: Continuous recording (works now)
python voice_chat.py

# With custom duration
python voice_chat.py --duration 10

# Experimental: Wake word mode (requires models)
python voice_chat.py --wake-word
```

## How It Works

### Without Wake Word (Current Default)
```
┌─────────────────────────────────────┐
│  Record 5s → Whisper → Process      │
│  Record 5s → Whisper → Process      │
│  Record 5s → Whisper → Process      │
└─────────────────────────────────────┘
```
- Simple but CPU intensive (Whisper runs constantly)
- Works reliably with no setup

### With Wake Word (Future/Experimental)
```
┌─────────────────────────────────────┐
│  Lightweight detector listens...    │
│  ✅ "NERVA" detected!               │
│  Record command → Whisper → Process │
│  Back to listening...                │
└─────────────────────────────────────┘
```
- Low CPU when idle (lightweight detector only)
- Whisper only runs when needed
- **Requires**: Pre-trained wake word models

## What's Missing

### Pre-trained Models

OpenWakeWord needs model files in:
```
/home/joker/.local/lib/python3.10/site-packages/openwakeword/resources/models/
```

**Options:**

1. **Use existing models** (Alexa, Hey Mycroft, etc.)
   - Download from openWakeWord repository
   - Place in models directory

2. **Train custom "NERVA" model**
   - Collect audio samples of people saying "NERVA"
   - Use openWakeWord training tools
   - Export as .tflite model

## Training Custom "NERVA" Wake Word

### Step 1: Collect Samples

Record yourself and others saying "NERVA" in different:
- Accents
- Volumes
- Distances from microphone
- Background noise levels

Need ~500-1000 samples for good accuracy.

### Step 2: Train Model

```bash
# Clone openWakeWord
git clone https://github.com/dscripka/openWakeWord.git
cd openWakeWord

# Follow training guide
# https://github.com/dscripka/openWakeWord#training-new-models
```

### Step 3: Export and Install

```bash
# Copy trained model
cp your_nerva_model.tflite ~/.local/lib/python3.10/site-packages/openwakeword/resources/models/

# Update voice_chat.py
# Change wake_word="hey_mycroft" to wake_word="nerva"
```

## Alternative: Use Existing Wake Words

While we wait for a custom "NERVA" model, you can use existing ones:

- **"hey_mycroft"** - Default, similar to "NERVA"
- **"alexa"** - Amazon's wake word
- **"hey_jarvis"** - Iron Man style

Just need to download the .tflite files.

## Why This Approach?

**Continuous Recording (Current):**
- ✅ Works immediately, no setup
- ✅ Reliable
- ❌ CPU intensive (Whisper always running)
- ❌ Privacy concern (always recording)

**Wake Word Detection (Future):**
- ✅ Low CPU when idle
- ✅ Better privacy (only records after wake word)
- ✅ More natural interaction
- ❌ Requires model files
- ❌ Can have false positives/negatives

## Next Steps

1. Download pre-trained models from openWakeWord
2. OR collect samples and train custom "NERVA" model
3. Test wake word accuracy
4. Make wake word mode the default once models are ready

## Files Created

- `nerva/voice/wake_word.py` - Wake word detector module
- Updated `voice_chat.py` - Dual-mode voice chat
- This documentation

## References

- [openWakeWord GitHub](https://github.com/dscripka/openWakeWord)
- [Training Guide](https://github.com/dscripka/openWakeWord#training-new-models)
- [Pre-trained Models](https://github.com/dscripka/openWakeWord/tree/main/openwakeword/resources/models)
