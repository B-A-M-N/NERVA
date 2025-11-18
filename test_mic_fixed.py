#!/usr/bin/env python3
"""Test with fixed microphone recording using parec"""

import sys
sys.path.insert(0, '/home/joker/NERVA')

from nerva.voice.whisper_asr_fixed import WhisperASRFixed

print("="*60)
print("Testing Microphone with parec (PulseAudio/PipeWire)")
print("="*60)

print("\nInitializing Whisper...")
asr = WhisperASRFixed(model_path="tiny")

print("\n✅ Ready!")
print("="*60)
input("Press ENTER to start recording...")

print("\n🎤 Recording will start...")
text = asr.transcribe_once(duration=5.0)

if text:
    print(f"\n✅ You said: \"{text}\"")
else:
    print("\n❌ No speech detected")

print("\n"+ "="*60)
print("Test complete!")
print("="*60)
