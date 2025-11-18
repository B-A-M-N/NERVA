# Microphone Fix for NERVA

## Problem

Your microphone works fine at the system level (PulseAudio/PipeWire), but **sounddevice** (the Python library used for recording) cannot access it. This is a common issue on modern Linux systems using PipeWire instead of traditional ALSA/PulseAudio.

**Diagnosis:**
- ✅ Microphone exists: `alsa_input.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__hw_sofhdadsp__source`
- ✅ Not muted: Volume at 100%
- ✅ Status: RUNNING
- ❌ sounddevice gets 0.0000 audio level (can't access mic)

## Solution

Created **`whisper_asr_fixed.py`** that uses `parec` (PulseAudio/PipeWire native) instead of sounddevice.

## How to Test

### Quick Test

```bash
python test_mic_fixed.py
```

When prompted, press ENTER and speak clearly into your microphone when it says "SPEAK NOW!"

### Expected Output

```
============================================================
Testing Microphone with parec (PulseAudio/PipeWire)
============================================================

Initializing Whisper...

✅ Ready!
============================================================
Press ENTER to start recording...

🎤 Recording will start...
🔴 Recording for 5.0 seconds - SPEAK NOW!

✅ You said: "hello this is a test"

============================================================
Test complete!
============================================================
```

## Next Steps

If the fixed version works, you have two options:

### Option 1: Replace the original (Recommended)

```bash
# Backup original
mv /home/joker/NERVA/nerva/voice/whisper_asr.py /home/joker/NERVA/nerva/voice/whisper_asr_old.py

# Replace with fixed version
mv /home/joker/NERVA/nerva/voice/whisper_asr_fixed.py /home/joker/NERVA/nerva/voice/whisper_asr.py
```

Then all voice scripts will automatically use the fixed version.

### Option 2: Update test scripts to use fixed version

Modify `test_voice_live.py` and other scripts to import from `whisper_asr_fixed` instead of `whisper_asr`.

## What Changed

**Original** (`whisper_asr.py`):
- Uses `sounddevice` library
- Calls `sd.rec()` directly
- Works with ALSA but not PipeWire

**Fixed** (`whisper_asr_fixed.py`):
- Uses `parec` command (PulseAudio/PipeWire native)
- Records to raw audio, converts with `ffmpeg`
- Fully compatible with PipeWire

## Technical Details

The recording process now:

1. **Calls `parec`**: Records raw audio from PulseAudio/PipeWire
   ```bash
   parec --format=s16le --rate=16000 --channels=1 output.raw
   ```

2. **Converts to WAV**: Uses `ffmpeg` to convert raw audio to WAV
   ```bash
   ffmpeg -f s16le -ar 16000 -ac 1 -i output.raw output.wav
   ```

3. **Transcribes**: Passes WAV to Whisper as before

## Why This Happens

Modern Linux audio stack:
- **Old**: ALSA → Application
- **New**: Application → PulseAudio → PipeWire → ALSA

`sounddevice` tries to use ALSA directly, bypassing PulseAudio/PipeWire, which fails on modern systems. Using `parec` works because it's the native PulseAudio recording tool.

## Verification

Confirm your audio system:
```bash
# Check if PipeWire is running
pactl info | grep "Server Name"
# Should show: PulseAudio (on PipeWire)

# List audio sources
pactl list sources short

# Test recording with parec
timeout 3 parec --format=s16le test.raw && echo "Mic works!"
```

---

**Ready to test?** Run:
```bash
python test_mic_fixed.py
```
