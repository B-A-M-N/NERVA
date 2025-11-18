# nerva/voice/kokoro_tts.py
from __future__ import annotations
from typing import Optional
import logging

# Try to import Kokoro ONNX
try:
    from kokoro_onnx import Kokoro
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False

# Try to import sounddevice (needs PortAudio installed)
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except (ImportError, OSError):  # OSError if PortAudio not installed
    SOUNDDEVICE_AVAILABLE = False

# Check for alternative TTS engines
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

logger = logging.getLogger(__name__)


class KokoroTTS:
    """
    Text-to-speech engine with multiple backend support.

    Tries to use (in order):
    1. Kokoro-82M (if installed)
    2. pyttsx3 (cross-platform fallback)
    3. System TTS (espeak/say)
    4. Print fallback

    To install Kokoro-82M:
        pip install git+https://github.com/remsky/Kokoro-82M.git
        # or from local path

    To use pyttsx3:
        pip install pyttsx3

    See KOKORO_SETUP.md for detailed instructions.
    """

    def __init__(self, model_path: str = "kokoro-82m", voice: str = "af_bella") -> None:
        self.model_path = model_path
        self.voice = voice  # Default voice: "af_bella" (American Female - Bella)
        self.backend = None

        # Try Kokoro ONNX first
        if KOKORO_AVAILABLE:
            try:
                # Download Kokoro models if needed
                model_dir = self._ensure_kokoro_models()
                if model_dir:
                    model_path = model_dir / "kokoro-v1.0.onnx"
                    voices_path = model_dir / "voices-v1.0.bin"

                    self.model = Kokoro(str(model_path), str(voices_path))
                    self.backend = "kokoro"
                    logger.info(f"[KokoroTTS] Using Kokoro-82M ONNX backend (voice={voice})")
                else:
                    logger.debug("[KokoroTTS] Kokoro models not available")
            except Exception as e:
                logger.debug(f"[KokoroTTS] Kokoro init failed: {e}")

        # Try pyttsx3 if Kokoro failed
        if self.backend is None and PYTTSX3_AVAILABLE:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', 150)
                self.engine.setProperty('volume', 0.9)
                self.backend = "pyttsx3"
                logger.info("[KokoroTTS] Using pyttsx3 backend")
            except Exception as e:
                logger.debug(f"[KokoroTTS] pyttsx3 init failed: {e}")

        # Try system TTS
        if self.backend is None:
            import shutil
            if shutil.which("say"):  # macOS
                self.backend = "say"
                logger.info("[KokoroTTS] Using macOS 'say' backend")
            elif shutil.which("espeak"):  # Linux
                self.backend = "espeak"
                logger.info("[KokoroTTS] Using espeak backend")

        # Fallback to print
        if self.backend is None:
            self.backend = "print"
            logger.warning(
                "[KokoroTTS] No TTS engine available, using print fallback. "
                "Install Kokoro or pyttsx3 for real speech. See KOKORO_SETUP.md"
            )

    def speak(self, text: str, blocking: bool = True) -> None:
        """
        Convert text to speech and play it.

        Args:
            text: Text to synthesize
            blocking: If True, waits for playback to complete
        """
        if self.backend == "kokoro":
            self._speak_kokoro(text, blocking)
        elif self.backend == "pyttsx3":
            self._speak_pyttsx3(text, blocking)
        elif self.backend in ["say", "espeak"]:
            self._speak_system(text, blocking)
        else:
            print(f"[TTS] {text}")

    def _speak_kokoro(self, text: str, blocking: bool) -> None:
        """Kokoro-82M ONNX synthesis."""
        try:
            # Generate audio using Kokoro ONNX
            # The create() method requires: text and voice
            samples, sample_rate = self.model.create(text, voice=self.voice)

            if SOUNDDEVICE_AVAILABLE:
                # Play audio
                sd.play(samples, samplerate=sample_rate)
                if blocking:
                    sd.wait()
                logger.debug(f"[KokoroTTS] Synthesized {len(text)} chars at {sample_rate}Hz")
            else:
                logger.warning("[KokoroTTS] sounddevice not available (install portaudio19-dev)")
                print(f"[TTS] {text}")
                print("  (To hear audio: sudo apt-get install portaudio19-dev)")

        except Exception as e:
            logger.error(f"[KokoroTTS] Synthesis error: {e}")
            print(f"[TTS] {text}")

    def _speak_pyttsx3(self, text: str, blocking: bool) -> None:
        """pyttsx3 synthesis."""
        try:
            if blocking:
                self.engine.say(text)
                self.engine.runAndWait()
            else:
                self.engine.say(text)
        except Exception as e:
            logger.error(f"[KokoroTTS] pyttsx3 error: {e}")
            print(f"[TTS] {text}")

    def _speak_system(self, text: str, blocking: bool) -> None:
        """System TTS (say/espeak)."""
        import subprocess
        try:
            if self.backend == "say":
                subprocess.run(["say", text], check=True)
            elif self.backend == "espeak":
                subprocess.run(["espeak", text], check=True)
        except Exception as e:
            logger.error(f"[KokoroTTS] System TTS error: {e}")
            print(f"[TTS] {text}")

    def _ensure_kokoro_models(self) -> Optional["Path"]:
        """
        Ensure Kokoro models are downloaded.

        Downloads from GitHub releases if not present.
        Returns path to model directory or None if download fails.
        """
        from pathlib import Path
        import urllib.request

        model_dir = Path.home() / ".nerva" / "models" / "kokoro"
        model_file = model_dir / "kokoro-v1.0.onnx"
        voices_file = model_dir / "voices-v1.0.bin"

        # Check if already downloaded
        if model_file.exists() and voices_file.exists():
            return model_dir

        # Create directory
        model_dir.mkdir(parents=True, exist_ok=True)

        logger.info("[KokoroTTS] Downloading Kokoro models from GitHub...")
        logger.info("  This may take a few minutes on first run (~300MB)...")

        base_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"

        try:
            # Download model file (~300MB)
            if not model_file.exists():
                logger.info(f"  Downloading ONNX model file...")
                urllib.request.urlretrieve(
                    base_url + "kokoro-v1.0.onnx",
                    model_file,
                )
                logger.info(f"    ✓ Model downloaded")

            # Download voices file
            if not voices_file.exists():
                logger.info(f"  Downloading voices file...")
                urllib.request.urlretrieve(
                    base_url + "voices-v1.0.bin",
                    voices_file,
                )
                logger.info(f"    ✓ Voices downloaded")

            logger.info("✓ Kokoro models downloaded successfully!")
            return model_dir

        except Exception as e:
            logger.error(f"[KokoroTTS] Model download failed: {e}")
            return None

    def synthesize_to_file(self, text: str, output_path: str) -> None:
        """
        Synthesize text and save to audio file.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file (WAV)
        """
        if self.backend != "kokoro":
            raise NotImplementedError(f"File synthesis not supported for backend: {self.backend}")

        try:
            import soundfile as sf

            # Generate audio
            samples, sample_rate = self.model.create(text, voice=self.voice)

            # Save to file
            sf.write(output_path, samples, sample_rate)
            logger.info(f"[KokoroTTS] Saved audio to: {output_path}")
        except Exception as e:
            logger.error(f"[KokoroTTS] File synthesis error: {e}")
            raise
