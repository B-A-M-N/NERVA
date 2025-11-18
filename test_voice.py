#!/usr/bin/env python3
"""
NERVA Voice Testing Framework

Supports three testing modes:
  1. File-based: Test ASR with pre-recorded audio files
  2. Mock: Test voice workflow with simulated transcriptions
  3. Live: Test with real microphone input

Usage:
  # Test with audio file
  python test_voice.py --mode file --audio test_audio.wav

  # Test with mock transcription
  python test_voice.py --mode mock --text "what is 2+2"

  # Test with live microphone
  python test_voice.py --mode live

  # Batch test multiple mock scenarios
  python test_voice.py --mode batch
"""
import asyncio
import argparse
import sys
from pathlib import Path
from typing import Optional, List, Dict
from unittest.mock import Mock, patch

from nerva.voice.whisper_asr import WhisperASR
from nerva.voice.kokoro_tts import KokoroTTS
from nerva.llm.factory import create_llm_client
from nerva.config import NervaConfig
from nerva.memory.store import MemoryStore
from nerva.run_context import RunContext
from nerva.workflows import build_voice_dag


class VoiceTester:
    """Comprehensive voice testing framework for NERVA."""

    def __init__(self, enable_tts: bool = False):
        self.config = NervaConfig()
        self.llm = create_llm_client(self.config)
        self.memory = MemoryStore()
        self.enable_tts = enable_tts

        # Initialize TTS only if enabled
        self.tts = None
        if enable_tts:
            try:
                self.tts = KokoroTTS(model_path=self.config.kokoro_model)
            except Exception as e:
                print(f"⚠️  TTS disabled: {e}")

    async def test_file_asr(self, audio_path: str) -> Dict[str, any]:
        """Test ASR with a pre-recorded audio file."""
        print(f"\n{'='*60}")
        print(f"🎵 Testing File-Based ASR: {audio_path}")
        print(f"{'='*60}")

        if not Path(audio_path).exists():
            print(f"❌ Audio file not found: {audio_path}")
            return {"success": False, "error": "File not found"}

        try:
            asr = WhisperASR(model_path="tiny")
            print(f"📝 Transcribing audio file...")

            transcription = asr.transcribe_once(audio_path=audio_path)

            if not transcription:
                print("❌ No speech detected in audio file")
                return {"success": False, "error": "No speech detected"}

            print(f"✅ Transcription: {transcription}")

            # Process through voice workflow
            result = await self._process_voice_input(transcription)
            return {
                "success": True,
                "transcription": transcription,
                "response": result
            }

        except Exception as e:
            print(f"❌ Error: {e}")
            return {"success": False, "error": str(e)}

    async def test_mock_voice(self, mock_text: str) -> Dict[str, any]:
        """Test voice workflow with mocked transcription."""
        print(f"\n{'='*60}")
        print(f"🎭 Testing Mock Voice: '{mock_text}'")
        print(f"{'='*60}")

        try:
            result = await self._process_voice_input(mock_text)
            return {
                "success": True,
                "input": mock_text,
                "response": result
            }
        except Exception as e:
            print(f"❌ Error: {e}")
            return {"success": False, "error": str(e)}

    async def test_live_voice(self, duration: float = 5.0) -> Dict[str, any]:
        """Test with live microphone input."""
        print(f"\n{'='*60}")
        print(f"🎤 Testing Live Microphone (recording for {duration}s)")
        print(f"{'='*60}")
        print("🔴 Recording now... speak!")

        try:
            asr = WhisperASR(model_path="tiny")
            transcription = asr.transcribe_once(duration=duration)

            if not transcription or len(transcription) < 3:
                print("❌ No speech detected")
                return {"success": False, "error": "No speech detected"}

            print(f"✅ You said: {transcription}")

            result = await self._process_voice_input(transcription)
            return {
                "success": True,
                "transcription": transcription,
                "response": result
            }

        except Exception as e:
            print(f"❌ Error: {e}")
            return {"success": False, "error": str(e)}

    async def test_batch(self, test_cases: Optional[List[str]] = None) -> Dict[str, any]:
        """Run batch tests with predefined test cases."""
        print(f"\n{'='*60}")
        print("📦 Running Batch Voice Tests")
        print(f"{'='*60}")

        if test_cases is None:
            test_cases = [
                "what is 2 plus 2",
                "tell me about quantum computing",
                "what's the weather like today",
                "set a reminder for tomorrow",
                "search for python tutorials",
            ]

        results = []
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n--- Test {i}/{len(test_cases)}: '{test_case}' ---")
            result = await self.test_mock_voice(test_case)
            results.append({
                "test_case": test_case,
                "result": result
            })
            await asyncio.sleep(0.5)  # Brief pause between tests

        # Summary
        successful = sum(1 for r in results if r["result"]["success"])
        print(f"\n{'='*60}")
        print(f"📊 Batch Test Summary: {successful}/{len(test_cases)} passed")
        print(f"{'='*60}")

        return {
            "success": True,
            "total": len(test_cases),
            "passed": successful,
            "results": results
        }

    async def _process_voice_input(self, text: str) -> str:
        """Process voice input through NERVA's voice workflow."""
        ctx = RunContext(mode="voice", voice_text=text)
        dag = build_voice_dag(llm=self.llm, memory=self.memory)
        ctx = await dag.run(ctx)

        response = ctx.llm_raw_response or "No response generated"

        print(f"\n🤖 NERVA: {response}")

        # Speak response if TTS is enabled
        if self.enable_tts and self.tts:
            print("🔊 Speaking response...")
            self.tts.speak(response)

        return response


async def main():
    parser = argparse.ArgumentParser(description="NERVA Voice Testing Framework")
    parser.add_argument(
        "--mode",
        choices=["file", "mock", "live", "batch"],
        default="mock",
        help="Testing mode"
    )
    parser.add_argument(
        "--audio",
        type=str,
        help="Path to audio file (for file mode)"
    )
    parser.add_argument(
        "--text",
        type=str,
        default="what is 2 plus 2",
        help="Mock transcription text (for mock mode)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Recording duration in seconds (for live mode)"
    )
    parser.add_argument(
        "--tts",
        action="store_true",
        help="Enable TTS output"
    )

    args = parser.parse_args()

    tester = VoiceTester(enable_tts=args.tts)

    try:
        if args.mode == "file":
            if not args.audio:
                print("❌ Error: --audio required for file mode")
                sys.exit(1)
            result = await tester.test_file_asr(args.audio)

        elif args.mode == "mock":
            result = await tester.test_mock_voice(args.text)

        elif args.mode == "live":
            result = await tester.test_live_voice(args.duration)

        elif args.mode == "batch":
            result = await tester.test_batch()

        # Print final result
        print(f"\n{'='*60}")
        if result["success"]:
            print("✅ Test completed successfully")
        else:
            print(f"❌ Test failed: {result.get('error', 'Unknown error')}")
        print(f"{'='*60}\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
