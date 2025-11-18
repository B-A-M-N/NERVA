#!/usr/bin/env python3
"""
NERVA Live Voice Testing - Quick microphone test

This is a simplified script for testing voice commands with your microphone.

Usage:
  python test_voice_live.py

Then just speak when prompted!
"""
import asyncio
from nerva.voice.whisper_asr import WhisperASR
from nerva.voice.kokoro_tts import KokoroTTS
from nerva.llm.factory import create_llm_client
from nerva.config import NervaConfig
from nerva.memory.store import MemoryStore
from nerva.run_context import RunContext
from nerva.workflows import build_voice_dag


async def test_single_command():
    """Test a single voice command."""
    print("\n" + "="*60)
    print("🎤 NERVA Live Voice Test")
    print("="*60)
    print("\nInitializing voice components...")

    # Initialize
    asr = WhisperASR(model_path="tiny")
    tts = KokoroTTS()
    config = NervaConfig()
    llm = create_llm_client(config)
    memory = MemoryStore()

    print("✅ Ready!")
    print("\n" + "="*60)
    print("🔴 Recording for 5 seconds - SPEAK NOW!")
    print("="*60)
    print("Example commands:")
    print("  - What is 2 plus 2?")
    print("  - Tell me about quantum computing")
    print("  - What's the capital of France?")
    print("\n🎙️  Listening...\n")

    # Record and transcribe
    transcription = asr.transcribe_once(duration=5.0)

    if not transcription or len(transcription) < 3:
        print("❌ No speech detected. Please try again.")
        return

    print(f"\n✅ You said: \"{transcription}\"")
    print("\n🤔 Processing...")

    # Process through NERVA
    ctx = RunContext(mode="voice", voice_text=transcription)
    dag = build_voice_dag(llm=llm, memory=memory)
    ctx = await dag.run(ctx)

    response = ctx.llm_raw_response or "No response generated"

    print(f"\n🤖 NERVA: {response}")

    # Speak response
    print("\n🔊 Speaking response...")
    tts.speak(response)

    print("\n" + "="*60)
    print("✅ Test completed!")
    print("="*60)


async def continuous_voice_loop():
    """Continuous voice chat loop."""
    print("\n" + "="*60)
    print("🎤 NERVA Continuous Voice Chat")
    print("="*60)
    print("\nInitializing voice components...")

    # Initialize
    asr = WhisperASR(model_path="tiny")
    tts = KokoroTTS()
    config = NervaConfig()
    llm = create_llm_client(config)
    memory = MemoryStore()

    print("✅ Ready!")
    print("\n" + "="*60)
    print("Voice chat is active!")
    print("Say 'exit' or 'goodbye' to stop")
    print("Press Ctrl+C to quit anytime")
    print("="*60)

    while True:
        try:
            print("\n🎙️  Listening for 5 seconds...")
            transcription = asr.transcribe_once(duration=5.0)

            if not transcription or len(transcription) < 3:
                print("   (No speech detected)")
                continue

            print(f"\n👤 You: {transcription}")

            # Check for exit
            if "exit" in transcription.lower() or "goodbye" in transcription.lower():
                print("\n👋 Goodbye!")
                tts.speak("Goodbye!")
                break

            # Process
            ctx = RunContext(mode="voice", voice_text=transcription)
            dag = build_voice_dag(llm=llm, memory=memory)
            ctx = await dag.run(ctx)

            response = ctx.llm_raw_response or "I didn't catch that."

            print(f"\n🤖 NERVA: {response}")
            tts.speak(response)

        except KeyboardInterrupt:
            print("\n\n👋 Stopping...")
            tts.speak("Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue

    print("\n" + "="*60)
    print("✅ Voice chat ended")
    print("="*60 + "\n")


async def main():
    print("\n" + "="*60)
    print("NERVA Live Voice Testing")
    print("="*60)
    print("\nChoose test mode:")
    print("  1. Single command test")
    print("  2. Continuous voice chat")
    print("  3. Both (single test first, then continuous)")
    print()

    choice = input("Enter choice (1/2/3) [default: 1]: ").strip() or "1"

    if choice == "1":
        await test_single_command()
    elif choice == "2":
        await continuous_voice_loop()
    elif choice == "3":
        await test_single_command()
        print("\n\n")
        input("Press ENTER to start continuous chat...")
        await continuous_voice_loop()
    else:
        print(f"Invalid choice: {choice}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user\n")
