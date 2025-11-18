#!/usr/bin/env python3
"""
Test raw microphone recording to see if audio is being captured
"""
import subprocess
import time
import os

print("="*60)
print("Raw Microphone Test")
print("="*60)

# Test 1: Record with parec
print("\n📍 Test 1: Recording with parec (what the fix uses)")
print("Recording 3 seconds of raw audio...")
print("🔴 SPEAK LOUDLY NOW!")

raw_file = "/tmp/test_parec.raw"
process = subprocess.Popen(
    ["parec", "--format=s16le", "--rate=16000", "--channels=1", raw_file],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

time.sleep(3)
process.terminate()
process.wait(timeout=2)

# Check file size
if os.path.exists(raw_file):
    size = os.path.getsize(raw_file)
    print(f"\n✅ Recorded {size} bytes")

    if size == 0:
        print("❌ PROBLEM: File is empty - microphone not capturing audio!")
    elif size < 10000:
        print("⚠️  WARNING: Very small file - mic might be too quiet")
    else:
        print("✅ File size looks good!")

    # Convert to WAV and try to play it
    wav_file = "/tmp/test_parec.wav"
    print(f"\nConverting to WAV...")
    subprocess.run(
        ["ffmpeg", "-f", "s16le", "-ar", "16000", "-ac", "1", "-i", raw_file, "-y", wav_file],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if os.path.exists(wav_file):
        wav_size = os.path.getsize(wav_file)
        print(f"✅ WAV file created: {wav_size} bytes")
        print(f"\n💡 To play it back: aplay {wav_file}")
        print(f"   Or check with: ffmpeg -i {wav_file} 2>&1 | grep Duration")

        # Try to get audio info
        result = subprocess.run(
            ["ffmpeg", "-i", wav_file],
            capture_output=True,
            text=True
        )
        for line in result.stderr.split('\n'):
            if 'Duration' in line or 'Stream' in line:
                print(f"   {line.strip()}")
else:
    print("❌ No file created!")

print("\n" + "="*60)
print("Now testing with Whisper transcription...")
print("="*60)

if os.path.exists(wav_file):
    print("\nTranscribing recorded audio with Whisper...")
    import sys
    sys.path.insert(0, '/home/joker/NERVA')
    from nerva.voice.whisper_asr import WhisperASR

    asr = WhisperASR(model_path="tiny")
    text = asr.transcribe_once(audio_path=wav_file)

    if text:
        print(f"\n✅ SUCCESS! Transcribed: \"{text}\"")
    else:
        print("\n❌ Whisper detected no speech")
        print("   This means:")
        print("   1. Audio was recorded but too quiet")
        print("   2. Or no actual speech in the recording")
        print("   3. Or background noise only")

print("\n" + "="*60)
