# nerva/voice/whisper_asr.py
from __future__ import annotations
from typing import Optional, AsyncGenerator
import asyncio
import functools
import logging
import os
import tempfile
from pathlib import Path


logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel

    FASTER_WHISPER_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    WhisperModel = None
    FASTER_WHISPER_AVAILABLE = False

try:
    import whisper as openai_whisper

    OPENAI_WHISPER_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    openai_whisper = None
    OPENAI_WHISPER_AVAILABLE = False

try:
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    sd = None
    SOUNDDEVICE_AVAILABLE = False

try:
    import soundfile as sf

    SOUNDFILE_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    sf = None
    SOUNDFILE_AVAILABLE = False


class WhisperASR:
    """
    Whisper-based automatic speech recognition.

    Prefers `faster-whisper` for performance but falls back to `openai-whisper`.
    When no pre-recorded audio is provided it records via sounddevice.
    """

    def __init__(
        self,
        model_path: str = "tiny",
        device: Optional[str] = None,
        compute_type: str = "int8",
    ) -> None:
        self.model_path = model_path
        self.device = device or os.getenv("WHISPER_DEVICE", "cpu")
        self.compute_type = compute_type
        self.backend: Optional[str] = None
        self.model = None

        if FASTER_WHISPER_AVAILABLE:
            try:
                logger.info(
                    "[WhisperASR] Loading faster-whisper model=%s device=%s",
                    model_path,
                    self.device,
                )
                self.model = WhisperModel(
                    model_path,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                self.backend = "faster-whisper"
            except Exception as exc:
                logger.warning(f"[WhisperASR] Failed to load faster-whisper: {exc}")
                self.model = None

        if self.model is None and OPENAI_WHISPER_AVAILABLE:
            try:
                logger.info("[WhisperASR] Loading openai-whisper model=%s", model_path)
                self.model = openai_whisper.load_model(model_path)
                self.backend = "openai-whisper"
            except Exception as exc:
                logger.error(f"[WhisperASR] Could not load openai-whisper: {exc}")
                self.model = None

        if self.model is None:
            raise RuntimeError(
                "No Whisper backend available. Install `faster-whisper` or `openai-whisper`."
            )

    def transcribe_once(
        self,
        audio_path: Optional[str] = None,
        duration: float = 5.0,
        sample_rate: int = 16000,
    ) -> Optional[str]:
        """
        Record from microphone and transcribe, OR transcribe from file.

        Args:
            audio_path: Optional path to audio file. If None, records from mic.
            duration: Recording duration in seconds when using microphone.
            sample_rate: Sample rate for microphone recordings.

        Returns:
            Transcribed text, or None if error
        """
        temp_path: Optional[Path] = None
        if audio_path is None:
            try:
                temp_path = Path(self._record_microphone(duration, sample_rate))
                audio_path = str(temp_path)
            except RuntimeError as exc:
                logger.error(f"[WhisperASR] {exc}")
                return None

        if not audio_path:
            return None

        try:
            if self.backend == "faster-whisper":
                segments, _info = self.model.transcribe(audio_path, beam_size=1)
                text = " ".join(segment.text.strip() for segment in segments).strip()
                return text or None
            elif self.backend == "openai-whisper":
                result = self.model.transcribe(audio_path)
                text = (result.get("text") or "").strip()
                return text or None
            else:
                logger.error("[WhisperASR] No backend initialized")
                return None
        except Exception as exc:
            logger.error(f"[WhisperASR] Transcription failed: {exc}")
            return None
        finally:
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    async def transcribe_stream(
        self,
        chunk_seconds: float = 5.0,
        sample_rate: int = 16000,
    ) -> AsyncGenerator[str, None]:
        """
        Stream audio from microphone and yield transcriptions.

        Args:
            chunk_seconds: Recording window for each chunk.
            sample_rate: Sample rate for microphone recordings.
        """
        if not SOUNDDEVICE_AVAILABLE or not SOUNDFILE_AVAILABLE:
            raise RuntimeError("sounddevice and soundfile required for streaming ASR")

        loop = asyncio.get_running_loop()
        while True:
            text = await loop.run_in_executor(
                None,
                functools.partial(
                    self.transcribe_once,
                    None,
                    chunk_seconds,
                    sample_rate,
                ),
            )
            if text:
                yield text

    def _record_microphone(self, duration: float, sample_rate: int) -> str:
        """Record audio from microphone and save to a temporary WAV file."""
        if not SOUNDDEVICE_AVAILABLE or not SOUNDFILE_AVAILABLE:
            raise RuntimeError("sounddevice and soundfile must be installed for microphone capture")

        logger.info("[WhisperASR] Recording audio for %.1f seconds", duration)
        frames = int(duration * sample_rate)
        audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()

        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_file.close()
        sf.write(temp_file.name, audio, sample_rate)
        return temp_file.name
