#!/usr/bin/env python3
"""
NERVA Voice Chat - Hands-free voice interaction with wake word detection

Requires:
  - Whisper (faster-whisper or openai-whisper)
  - Kokoro-82M or another TTS
  - openWakeWord for wake word detection

Usage:
  python voice_chat.py
  Then just say "Hey Mycroft" (or NERVA when custom model is trained)
"""
import asyncio
from pathlib import Path
from typing import Optional

from nerva.llm.factory import create_llm_client
from nerva.config import NervaConfig
from nerva.memory.store import MemoryStore
from nerva.agents import (
    TaskDispatcher,
    TaskContext,
    VisionActionAgent,
    GoogleCalendarSkill,
    GmailSkill,
    GoogleDriveSkill,
)
from nerva.task_tracking import ThreadStore
from nerva.knowledge import KnowledgeGraph
from nerva.voice.whisper_asr import WhisperASR
from nerva.voice.kokoro_tts import KokoroTTS
from nerva.voice.wake_word import WakeWordDetector


class VoiceChat:
    def __init__(
        self,
        max_recording: float = 30.0,
        silence_timeout: float = 3.0,
        min_recording: float = 1.0,
        silence_threshold: int = 300,
        use_wake_word: bool = True,
        barge_in: bool = False,
        profile_path: Optional[str] = None,
    ):
        self.config = NervaConfig()
        self.llm = create_llm_client(self.config)
        self.memory = MemoryStore()
        self.asr = WhisperASR(model_path=self.config.whisper_model)
        self.tts = KokoroTTS(model_path=self.config.kokoro_model)
        self.max_recording = max_recording
        self.silence_timeout = silence_timeout
        self.min_recording = min_recording
        self.silence_threshold = silence_threshold
        self.barge_in = barge_in
        self.use_wake_word = use_wake_word and not barge_in
        self.profile_path = Path(profile_path).expanduser() if profile_path else None

        # Initialize wake word detector if enabled
        self.wake_detector = None
        if use_wake_word:
            try:
                # Use "alexa" for now - train custom "NERVA" model later
                self.wake_detector = WakeWordDetector(
                    wake_word="alexa",
                    threshold=0.5
                )
            except Exception as e:
                print(f"⚠️  Wake word detector unavailable: {e}")
                print("   Falling back to continuous recording mode")
                self.use_wake_word = False

        # Initialize dispatcher (Vision + Google skills)
        self.vision_agent = VisionActionAgent()
        calendar = gmail = drive = None
        if self.profile_path:
            try:
                calendar = GoogleCalendarSkill(user_data_dir=str(self.profile_path))
                gmail = GmailSkill(user_data_dir=str(self.profile_path))
                drive = GoogleDriveSkill(user_data_dir=str(self.profile_path))
            except Exception as exc:
                print(f"⚠️  Google skill init failed ({exc}) - continuing without logged-in profile")
        self.thread_store = ThreadStore()
        self.knowledge_graph = KnowledgeGraph()

        async def _skip_clarifier(question: str) -> Optional[str]:
            print(f"[Clarify] {question} (skipped in voice mode)")
            return None

        self.dispatcher = TaskDispatcher(
            llm=self.llm,
            memory=self.memory,
            vision_agent=self.vision_agent,
            calendar_skill=calendar,
            gmail_skill=gmail,
            drive_skill=drive,
            clarifier=_skip_clarifier,
            thread_store=self.thread_store,
            knowledge_graph=self.knowledge_graph,
        )

    async def chat_loop(self):
        """Voice chat loop with wake word detection."""
        print("\n" + "="*60)
        print("NERVA Voice Chat")
        print("="*60)

        if self.barge_in:
            print("\n📋 Instructions:")
            print("   1. No wake word required, just start speaking")
            print(
                f"   2. Recording starts when speech is detected and stops "
                f"{self.silence_timeout}s after silence (max {self.max_recording}s)"
            )
            print("   3. Say 'exit' or 'goodbye' to quit")
            print("\n⚙️  Mode: Continuous barge-in (always listening)\n")
            await self._barge_in_loop()
            return

        if self.use_wake_word:
            print(f"\n📋 Instructions:")
            print(f"   1. Say 'Alexa' to wake NERVA")
            print(f"   2. Then speak your command")
            print(
                f"   3. Recording stops {self.silence_timeout}s after silence "
                f"(max {self.max_recording}s total)"
            )
            print(f"   4. Say 'exit' or 'goodbye' to quit")
            print(f"\n⚙️  Mode: Wake Word Detection (low CPU)")
            print(f"   Wake Word: 'Alexa' (custom NERVA model coming soon)")
        else:
            print(f"\n📋 Instructions:")
            print(f"   1. Speak your command (no wake word needed)")
            print(
                f"   2. Recording stops {self.silence_timeout}s after silence "
                f"(max {self.max_recording}s total)"
            )
            print(f"   3. Say 'exit' or 'goodbye' to quit")
            print(f"\n⚙️  Mode: Continuous Recording (fallback mode)")

        print("🎤 Press Ctrl+C to stop anytime\n")

        while True:
            try:
                if self.use_wake_word:
                    # Wait for wake word with lightweight detector
                    print("👂 Listening for wake word...")
                    detected = self.wake_detector.listen_once(timeout=30.0)

                    if not detected:
                        continue  # Timeout, try again

                    print("✅ Wake word detected! Speak your command now...")

                    # Record command after wake word until silence
                    text = self.asr.transcribe_until_silence(
                        min_duration=self.min_recording,
                        silence_duration=self.silence_timeout,
                        max_duration=self.max_recording,
                        silence_threshold=self.silence_threshold,
                    )
                else:
                    # Fallback: continuous recording without wake word
                    print("\n🎤 Listening (stop speaking to finish)...")
                    text = self.asr.transcribe_until_silence(
                        min_duration=self.min_recording,
                        silence_duration=self.silence_timeout,
                        max_duration=self.max_recording,
                        silence_threshold=self.silence_threshold,
                    )

                if not text or len(text) < 3:
                    print("   (No speech detected)")
                    continue

                print(f"\n👤 You: {text}")

                if not await self._handle_transcription(text):
                    break

            except KeyboardInterrupt:
                print("\n\nStopping...")
                self.tts.speak("Goodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}")
                import traceback
                traceback.print_exc()

    async def _barge_in_loop(self):
        try:
            while True:
                try:
                    text = self.asr.transcribe_until_silence(
                        min_duration=self.min_recording,
                        silence_duration=self.silence_timeout,
                        max_duration=self.max_recording,
                        silence_threshold=self.silence_threshold,
                        wait_for_voice=True,
                    )
                except KeyboardInterrupt:
                    break

                if not text or len(text.strip()) < 3:
                    continue

                print(f"\n👤 You: {text}")
                if not await self._handle_transcription(text):
                    break
        except KeyboardInterrupt:
            pass

    async def _handle_transcription(self, text: str) -> bool:
        lowered = text.lower()
        if "exit" in lowered or "goodbye" in lowered:
            self.tts.speak("Goodbye!")
            return False

        result = await self.dispatcher.dispatch(
            text,
            TaskContext(
                source="voice",
                meta={
                    "profile": str(self.profile_path) if self.profile_path else "none",
                },
            ),
        )

        response = result.summary or "Task routed."
        answer = result.payload.get("answer") if isinstance(result.payload, dict) else None
        if isinstance(answer, str) and answer.strip():
            response = f"{response}\n{answer.strip()}"

        print(f"\n🤖 NERVA: {response}")
        self.tts.speak(response)
        return True


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="NERVA Voice Chat with Wake Word Detection")
    parser.add_argument(
        "--max-duration",
        type=float,
        default=30.0,
        help="Maximum recording duration before force stop (seconds, default: 30)",
    )
    parser.add_argument(
        "--silence",
        type=float,
        default=2.0,
        help="Stop recording after this many seconds of silence (default: 2)",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=1.0,
        help="Minimum time to record before listening for silence (default: 1)",
    )
    parser.add_argument(
        "--silence-threshold",
        type=int,
        default=300,
        help="Base RMS threshold for silence detection (default: 300)",
    )
    parser.add_argument(
        "--no-wake-word",
        action="store_true",
        help="Disable wake word detection and use continuous recording mode"
    )
    parser.add_argument(
        "--barge-in",
        action="store_true",
        help="Enable continuous barge-in mode (always listening for speech)",
    )
    parser.add_argument(
        "--profile",
        help="Path to Chrome profile for Google skills (e.g., ~/.config/google-chrome/Default)",
    )
    args = parser.parse_args()

    try:
        chat = VoiceChat(
            max_recording=args.max_duration,
            silence_timeout=args.silence,
            min_recording=args.min_duration,
            silence_threshold=args.silence_threshold,
            use_wake_word=not args.no_wake_word,
            barge_in=args.barge_in,
            profile_path=args.profile,
        )
        await chat.chat_loop()
    except Exception as e:
        print(f"\nFailed to initialize voice chat: {e}")
        print("\nMake sure you have:")
        print("  1. Whisper installed: pip install faster-whisper")
        print("  2. Kokoro installed and configured")
        print("  3. openWakeWord installed: pip install openwakeword")
        print("  4. A working microphone")


if __name__ == "__main__":
    asyncio.run(main())
