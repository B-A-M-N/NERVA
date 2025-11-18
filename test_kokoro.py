#!/usr/bin/env python3
"""Test Kokoro TTS setup."""
import logging
import sys

# Enable debug logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)

from nerva.voice.kokoro_tts import KokoroTTS

def main():
    print("=" * 60)
    print("NERVA - Kokoro TTS Test")
    print("=" * 60)
    print()

    print("Initializing Kokoro TTS...")
    print("(Models will auto-download on first run - ~300MB)")
    print()

    try:
        tts = KokoroTTS(voice="af_bella")
        print(f"✓ TTS initialized with backend: {tts.backend}")
        print()

        if tts.backend == "kokoro":
            print("Testing Kokoro speech synthesis...")
            test_text = "NERVA voice output is working perfectly!"
            print(f"Speaking: '{test_text}'")
            print()
            tts.speak(test_text, blocking=True)
            print()
            print("✓ Kokoro TTS test complete!")

        elif tts.backend == "pyttsx3":
            print("Using pyttsx3 fallback backend")
            test_text = "NERVA is using pyttsx3 for speech."
            tts.speak(test_text, blocking=True)
            print("✓ pyttsx3 test complete!")

        elif tts.backend in ["say", "espeak"]:
            print(f"Using system TTS: {tts.backend}")
            test_text = "NERVA is using system TTS."
            tts.speak(test_text, blocking=True)
            print("✓ System TTS test complete!")

        else:
            print("⚠ Using print fallback (no TTS available)")
            print()
            print("To get real speech, install:")
            print("  - Kokoro: pip install kokoro-onnx")
            print("  - pyttsx3: pip install pyttsx3")
            print("  - Or use system TTS (espeak/say)")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
