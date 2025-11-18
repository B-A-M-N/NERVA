#!/usr/bin/env python3
"""
NERVA Chat - Text-based chat interface with TTS

Usage:
  python chat.py                    # Interactive chat with voice output
  python chat.py "your question"    # Single question with voice output
  python chat.py --voice            # Hands-free voice mode (wake word "NERVA")
  python chat.py --no-tts          # Disable text-to-speech
  python chat.py --mock            # Use mock LLM (testing)
"""
import asyncio
import sys
import functools
from pathlib import Path

import aiohttp

from nerva.config import NervaConfig
from nerva.llm.factory import create_llm_client
from nerva.llm.mock_client import MockLLMClient
from nerva.memory.store import MemoryStore
from nerva.memory.schemas import MemoryItem, MemoryType
from nerva.run_context import RunContext
from nerva.workflows import build_voice_dag, build_screen_dag
from nerva.voice.kokoro_tts import KokoroTTS
from nerva.voice.whisper_asr import WhisperASR
from nerva.vision.screenshot import capture_screen
from nerva.ops.collectors import collect_sollol_status
from nerva.sollol_integration import get_dashboard_integration, NERVADashboardIntegration


SYSTEM_PROMPT = """You are NERVA, a local AI chat assistant.

What you can do:
- Answer questions and have conversations
- Remember previous conversations in this session
- Provide technical information and explanations

What you are:
- Running locally via Ollama (never sending data to cloud)
- Using text-to-speech for voice output
- A general-purpose AI assistant

Key traits:
- Concise and practical responses
- Technical and direct (no fluff)
- Focus on actionable information
- Honest about limitations
"""


class NervaChat:
    def __init__(self, use_mock: bool = False, use_tts: bool = True) -> None:
        self.config = NervaConfig()
        self.memory = MemoryStore()
        self.use_tts = use_tts
        self.asr: WhisperASR | None = None
        self.wake_word = "nerva"
        self.dashboard: NERVADashboardIntegration | None = None

        # Try real LLM, fallback to mock
        try:
            self.llm = create_llm_client(self.config, use_mock=use_mock)
            if use_mock:
                print("⚠ Mock LLM enabled (use --no-mock to hit Ollama/SOLLOL)")
            elif self.config.use_sollol:
                print(f"✓ Connected to SOLLOL router @ {self.config.sollol_base_url}")
            else:
                print("✓ Connected to Ollama")
        except Exception as e:
            print("⚠ LLM init failed, falling back to mock responses")
            print(f"  Details: {e}")
            self.llm = MockLLMClient()

        # Initialize TTS
        if self.use_tts:
            try:
                self.tts = KokoroTTS(model_path=self.config.kokoro_model)
                print("✓ TTS initialized")
            except Exception as e:
                print(f"⚠ TTS initialization warning: {e}")
                self.use_tts = False

        # Connect to SOLLOL dashboard (read-only)
        try:
            self.dashboard = get_dashboard_integration()
            if self.dashboard:
                url = self.dashboard.get_dashboard_url() or f"http://localhost:{self.dashboard.dashboard_port}"
                print(f"📊 SOLLOL dashboard: {url}")
            else:
                print("⚠ SOLLOL dashboard integration unavailable (install sollol package).")
        except Exception as exc:
            print(f"⚠ Could not initialize SOLLOL dashboard integration: {exc}")
            self.dashboard = None

    def _switch_to_mock(self, reason: str) -> bool:
        """Switch to the mock LLM client if not already active."""
        if isinstance(self.llm, MockLLMClient):
            return False

        print(f"\n⚠ {reason}")
        print("  Falling back to mock responses. Start Ollama for real answers.")
        self.llm = MockLLMClient()
        return True

    def _show_voice_menu(self) -> None:
        """Show voice selection menu and update TTS voice."""
        voices = {
            # American Female
            "1": ("af_bella", "American Female - Bella (default)"),
            "2": ("af_sarah", "American Female - Sarah"),
            "3": ("af_nicole", "American Female - Nicole"),
            "4": ("af_sky", "American Female - Sky"),
            # American Male
            "5": ("am_adam", "American Male - Adam"),
            "6": ("am_michael", "American Male - Michael"),
            "7": ("am_eric", "American Male - Eric"),
            # British
            "8": ("bf_emma", "British Female - Emma"),
            "9": ("bm_george", "British Male - George"),
            # Other
            "10": ("jf_alpha", "Japanese Female - Alpha"),
            "11": ("zf_xiaoni", "Mandarin Female - Xiaoni"),
        }

        print("\n\033[1;33m🎤 Available Voices:\033[0m")
        for key, (voice_id, description) in voices.items():
            current = " (current)" if voice_id == self.tts.voice else ""
            print(f"  {key}. {description}{current}")

        try:
            choice = input("\n\033[1;36mSelect voice (1-11):\033[0m ").strip()
            if choice in voices:
                voice_id, description = voices[choice]
                self.tts.voice = voice_id
                print(f"\n✓ Voice changed to: {description}")
                # Test the new voice
                self.tts.speak(f"Hello, this is {description.split(' - ')[1]}")
            else:
                print("  Invalid selection.")
        except Exception as e:
            print(f"  Error changing voice: {e}")

    async def ask(self, question: str) -> str:
        """Ask NERVA a question and get a response."""
        ctx = RunContext(mode="voice", voice_text=question)
        dag = build_voice_dag(llm=self.llm, memory=self.memory)

        try:
            ctx = await dag.run(ctx)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # Lost connection to Ollama – fall back to mock responses and retry once.
            switched = self._switch_to_mock(f"Ollama request failed: {e}")
            if not switched:
                raise
            dag = build_voice_dag(llm=self.llm, memory=self.memory)
            ctx = RunContext(mode="voice", voice_text=question)
            ctx = await dag.run(ctx)

        return ctx.llm_raw_response or "No response"

    async def _run_screen_analysis(self) -> None:
        """Capture the current screen and run the screen DAG."""
        print("\n📸 Capturing screen...")
        screenshot = capture_screen()
        if not screenshot:
            print("   Unable to capture screen. Check mss/Pillow installation or permissions.")
            return

        ctx = RunContext(mode="screen", screenshot_bytes=screenshot)
        dag = build_screen_dag(llm=self.llm, memory=self.memory)
        print("   Running screen analysis...")
        try:
            ctx = await dag.run(ctx)
        except Exception as exc:
            print(f"   Screen analysis failed: {exc}")
            return

        analysis = ctx.screen_analysis or {}
        print("\n\033[1;32mScreen Analysis:\033[0m")
        for key, value in analysis.items():
            print(f"  - {key}: {value}")

    async def chat(self, voice_mode: bool = False) -> None:
        """Interactive chat loop."""
        if voice_mode:
            await self.voice_chat_loop()
            return

        print("\n" + "="*60)
        print("NERVA Chat - Interactive Mode")
        print("="*60)
        tts_status = "enabled" if self.use_tts else "disabled"
        print(f"\n🔊 Voice output: {tts_status}")
        if self.use_tts:
            print(f"🎤 Current voice: {self.tts.voice}")
        print("\nType your questions. Commands:")
        print("  /quit, /exit - Exit chat")
        print("  /memory - Show recent conversations")
        print("  /clear - Clear screen")
        print("  /voice  - Change TTS voice")
        print("  /screen - Capture screen and analyze")
        print("  /nodes  - Show SOLLOL dashboard status")
        print()

        while True:
            try:
                # Get user input
                user_input = input("\n\033[1;36mYou:\033[0m ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() in ['/quit', '/exit']:
                    print("\nGoodbye! 👋")
                    break

                if user_input.lower() == '/memory':
                    items = self.memory.all()
                    print(f"\n\033[1;33m📝 Recent conversations ({len(items)}):\033[0m")
                    for item in items[-5:]:
                        if item.type == MemoryType.Q_AND_A:
                            lines = item.text.split('\n')
                            for line in lines[:2]:  # Show Q and A
                                print(f"  {line}")
                    continue

                if user_input.lower() == '/clear':
                    print("\033[2J\033[H")  # Clear screen
                    continue

                if user_input.lower() == '/voice':
                    if not self.use_tts:
                        print("  TTS is disabled. Run without --no-tts to enable voice.")
                        continue

                    self._show_voice_menu()
                    continue

                if user_input.lower() == '/screen':
                    await self._run_screen_analysis()
                    continue

                if user_input.lower() == '/nodes':
                    self._show_sollol_status()
                    continue

                # Get response from NERVA
                print("\n\033[1;32mNERVA:\033[0m ", end="", flush=True)
                response = await self.ask(user_input)
                print(response)

                # Speak response if TTS is enabled
                if self.use_tts and response and response != "No response":
                    self.tts.speak(response)

            except KeyboardInterrupt:
                print("\n\nUse /quit to exit.")
            except Exception as e:
                print(f"\n\033[1;31mError:\033[0m {e}")

    async def voice_chat_loop(self) -> None:
        """Hands-free voice loop with wake word trigger."""
        try:
            self.asr = WhisperASR(model_path=self.config.whisper_model)
        except Exception as exc:
            print(f"\n❌ Voice input unavailable: {exc}")
            print("Install faster-whisper (or openai-whisper) plus sounddevice/soundfile.")
            return

        print("\n" + "=" * 60)
        print("NERVA Voice Mode (chat.py)")
        print("=" * 60)
        print("\nSay 'NERVA ...' to trigger. Press Ctrl+C or say 'NERVA exit' to stop.")
        print()

        while True:
            try:
                print("\n🎤 Listening...")
                loop = asyncio.get_running_loop()
                text = await loop.run_in_executor(
                    None,
                    functools.partial(self.asr.transcribe_once, duration=5),
                )

                if not text or len(text) < 3:
                    print("   (No speech detected)")
                    continue

                lower = text.lower()
                if self.wake_word not in lower:
                    print(f"   (Waiting for wake word '{self.wake_word}')")
                    continue

                cleaned = lower.split(self.wake_word, 1)[-1].strip() or text
                print(f"\n👤 You: {text}")

                if any(word in cleaned for word in ["exit", "quit", "goodbye"]):
                    print("\n👋 Exiting voice mode.")
                    self.tts.speak("Goodbye!") if self.use_tts else None
                    break

                ctx = RunContext(mode="voice", voice_text=cleaned)
                dag = build_voice_dag(llm=self.llm, memory=self.memory)
                ctx = await dag.run(ctx)

                response = ctx.llm_raw_response or "I didn't catch that."
                print(f"\n🤖 NERVA: {response}")

                if self.use_tts and response:
                    self.tts.speak(response)

            except KeyboardInterrupt:
                print("\n\nStopping voice mode...")
                if self.use_tts:
                    self.tts.speak("Goodbye!")
                break
            except Exception as exc:
                print(f"\nError: {exc}")

    def _show_sollol_status(self) -> None:
        """Display SOLLOL dashboard status without mutating it."""
        status = collect_sollol_status()
        if not status.get("reachable"):
            print("\n⚠ SOLLOL dashboard not reachable. Is it running?")
            print(f"   Expected URL: {status.get('dashboard_url')}")
            return

        print(f"\n\033[1;33mSOLLOL Dashboard ({status.get('dashboard_url')})\033[0m")
        metrics = status.get("metrics") or {}
        node_summary = status.get("node_summary") or {}
        backend_summary = status.get("backend_summary") or {}
        print(f"  Nodes: {node_summary.get('available', 0)}/{node_summary.get('total', 0)} available")
        print(f"  Backends: {backend_summary.get('available', 0)}/{backend_summary.get('total', 0)} healthy")
        if metrics:
            total_requests = metrics.get("total_requests")
            avg_latency = metrics.get("avg_latency")
            if total_requests is not None:
                print(f"  Total requests: {total_requests}")
            if avg_latency is not None:
                print(f"  Avg latency: {avg_latency} ms")

        apps = status.get("applications") or []
        if apps:
            print("\n  Active Applications:")
            for app in apps:
                name = app.get("name", "unknown")
                router_type = app.get("router_type", "unknown")
                uptime = app.get("uptime_seconds", 0)
                print(f"    - {name} ({router_type}) – {uptime}s uptime")
        else:
            print("\n  No registered applications reported.")

async def main():
    use_mock = "--mock" in sys.argv
    use_tts = "--no-tts" not in sys.argv  # TTS on by default, can disable with --no-tts
    voice_mode = "--voice" in sys.argv

    # Get question from command line (filtering out flags)
    question_parts = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

    chat = NervaChat(use_mock=use_mock, use_tts=use_tts)

    # Single question mode
    if question_parts:
        question = " ".join(question_parts)
        print(f"\033[1;36mYou:\033[0m {question}")
        print(f"\n\033[1;32mNERVA:\033[0m ", end="", flush=True)
        response = await chat.ask(question)
        print(response)

        # Speak response if TTS is enabled
        if use_tts and response and response != "No response":
            chat.tts.speak(response)

        print()  # Extra newline for clean exit
    else:
        # Interactive mode
        await chat.chat(voice_mode=voice_mode)


if __name__ == "__main__":
    asyncio.run(main())
