#!/usr/bin/env python3
"""
Quick microphone test for NERVA

Tests:
1. Microphone recording (raw audio capture)
2. Whisper transcription (speech-to-text)
3. Full voice pipeline (mic -> transcription -> LLM -> TTS)

Usage:
  python test_microphone.py
"""
import asyncio
from nerva.voice.whisper_asr import WhisperASR
from nerva.voice.kokoro_tts import KokoroTTS


def test_mic_recording():
    """Test 1: Can we record from the microphone?"""
    print("\n" + "="*60)
    print("🎤 TEST 1: Microphone Recording")
    print("="*60)
    print("Recording 3 seconds of audio...")
    print("🔴 SPEAK NOW!")

    try:
        import sounddevice as sd
        import soundfile as sf
        import tempfile

        # Record 3 seconds
        duration = 3
        sample_rate = 16000
        frames = int(duration * sample_rate)

        audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()

        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(temp_file.name, audio, sample_rate)

        print(f"✅ Recording successful! Saved to: {temp_file.name}")
        print(f"   Duration: {duration}s, Sample rate: {sample_rate}Hz")
        return temp_file.name

    except Exception as e:
        print(f"❌ Recording failed: {e}")
        return None


def test_whisper_transcription(audio_file=None):
    """Test 2: Can Whisper transcribe the audio?"""
    print("\n" + "="*60)
    print("🎙️  TEST 2: Whisper Transcription")
    print("="*60)

    try:
        asr = WhisperASR(model_path="tiny")

        if audio_file:
            print(f"Transcribing from file: {audio_file}")
            text = asr.transcribe_once(audio_path=audio_file)
        else:
            print("Recording 5 seconds of audio...")
            print("🔴 SPEAK NOW!")
            text = asr.transcribe_once(duration=5.0)

        if text:
            print(f"✅ Transcription: \"{text}\"")
            return text
        else:
            print("❌ No speech detected")
            return None

    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_full_voice_pipeline():
    """Test 3: Full voice pipeline (mic -> transcription -> LLM -> TTS)"""
    print("\n" + "="*60)
    print("🎭 TEST 3: Full Voice Pipeline")
    print("="*60)
    print("Say something like: 'what is 2 plus 2'")
    print("Recording 5 seconds...")
    print("🔴 SPEAK NOW!")

    try:
        from nerva.llm.factory import create_llm_client
        from nerva.config import NervaConfig
        from nerva.memory.store import MemoryStore
        from nerva.run_context import RunContext
        from nerva.workflows import build_voice_dag

        # Initialize components
        asr = WhisperASR(model_path="tiny")
        tts = KokoroTTS()
        config = NervaConfig()
        llm = create_llm_client(config)
        memory = MemoryStore()

        # Record and transcribe
        transcription = asr.transcribe_once(duration=5.0)

        if not transcription:
            print("❌ No speech detected")
            return

        print(f"\n👤 You said: \"{transcription}\"")

        # Process through voice workflow
        ctx = RunContext(mode="voice", voice_text=transcription)
        dag = build_voice_dag(llm=llm, memory=memory)
        ctx = await dag.run(ctx)

        response = ctx.llm_raw_response or "No response generated"

        print(f"\n🤖 NERVA: {response}")

        # Speak response
        print("\n🔊 Speaking response...")
        tts.speak(response)

        print("\n✅ Full pipeline test completed!")

    except Exception as e:
        print(f"❌ Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    print("\n" + "="*60)
    print("NERVA Microphone Testing Suite")
    print("="*60)
    print("\nThis will test your microphone and voice pipeline.")
    print("Make sure your microphone is working and not muted!")

    # Test 1: Basic recording
    audio_file = test_mic_recording()

    # Test 2: Whisper transcription
    if audio_file:
        test_whisper_transcription(audio_file)
    else:
        print("\nSkipping transcription test (no audio file)")

    # Test 3: Full pipeline
    print("\n" + "="*60)
    print("Ready for full pipeline test?")
    print("="*60)
    input("Press ENTER to continue...")

    await test_full_voice_pipeline()

    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)
    print("\nTo use voice chat, run:")
    print("  python voice_chat.py")
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
