#!/usr/bin/env python3
"""
Microphone diagnostic and testing tool
"""
import sounddevice as sd
import numpy as np
import time

print("="*60)
print("Microphone Diagnostic Tool")
print("="*60)

# List all devices
print("\n📋 Available Audio Devices:")
print(sd.query_devices())

# Get default input device
print("\n🎤 Default Input Device:")
default_input = sd.query_devices(kind='input')
print(default_input)

print("\n" + "="*60)
print("🔴 RECORDING TEST - Speak loudly for 5 seconds!")
print("="*60)

# Record with level monitoring
duration = 5
sample_rate = 16000

def callback(indata, frames, time, status):
    """Monitor audio levels during recording"""
    volume_norm = np.linalg.norm(indata) * 10
    print(f"🎚️  Level: {int(volume_norm):4d} | {'█' * min(int(volume_norm / 10), 50)}", end='\r')

print("\n🔴 SPEAK NOW!\n")

# Start recording stream with callback
stream = sd.InputStream(
    samplerate=sample_rate,
    channels=1,
    dtype='float32',
    callback=callback
)

# Simple recording without callback for analysis
recording = sd.rec(
    int(duration * sample_rate),
    samplerate=sample_rate,
    channels=1,
    dtype='float32'
)
sd.wait()

print("\n\n✅ Recording complete!")

# Analyze recording
max_level = np.max(np.abs(recording))
avg_level = np.mean(np.abs(recording))

print(f"\n📊 Audio Analysis:")
print(f"   Max level: {max_level:.4f}")
print(f"   Avg level: {avg_level:.4f}")

if max_level < 0.01:
    print("\n❌ PROBLEM: Audio level too low!")
    print("   Possible issues:")
    print("   1. Wrong microphone selected")
    print("   2. Microphone is muted")
    print("   3. Microphone volume too low")
    print("\n💡 Try:")
    print("   - Check system audio settings")
    print("   - Run: pavucontrol (if on Linux)")
    print("   - Speak VERY loudly during test")
elif max_level < 0.1:
    print("\n⚠️  WARNING: Audio level low but detected")
    print("   This might work but speak louder for better results")
else:
    print("\n✅ Audio level looks good!")

# Save recording for playback test
import soundfile as sf
output_file = "/tmp/mic_test.wav"
sf.write(output_file, recording, sample_rate)
print(f"\n💾 Recording saved to: {output_file}")
print("   Play it back with: aplay /tmp/mic_test.wav")

# Try to transcribe
print("\n" + "="*60)
print("🎙️  Testing Whisper Transcription")
print("="*60)

try:
    from nerva.voice.whisper_asr import WhisperASR

    print("Loading Whisper model (tiny)...")
    asr = WhisperASR(model_path="tiny")

    print("Transcribing recorded audio...")
    text = asr.transcribe_once(audio_path=output_file)

    if text:
        print(f"\n✅ Transcription: \"{text}\"")
    else:
        print("\n❌ No speech detected in transcription")
        print("   The audio was recorded but Whisper couldn't understand it")
        print("   Try speaking more clearly and loudly")

except Exception as e:
    print(f"\n❌ Transcription error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Diagnostic complete!")
print("="*60)
