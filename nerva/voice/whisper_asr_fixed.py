# nerva/voice/whisper_asr_fixed.py
"""
Fixed Whisper ASR using parec for PulseAudio/PipeWire compatibility
"""
from __future__ import annotations
from typing import Optional
import logging
import os
import tempfile
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except Exception:
    WhisperModel = None
    FASTER_WHISPER_AVAILABLE = False

try:
    import whisper as openai_whisper
    OPENAI_WHISPER_AVAILABLE = True
except Exception:
    openai_whisper = None
    OPENAI_WHISPER_AVAILABLE = False


class WhisperASRFixed:
    """
    Whisper ASR with fixed microphone recording using parec (PulseAudio/PipeWire).

    Uses parec instead of sounddevice for better compatibility with modern audio systems.
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
                temp_path = Path(self._record_microphone_parec(duration, sample_rate))
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

    def _record_microphone_parec(self, duration: float, sample_rate: int) -> str:
        """
        Record audio from microphone using parec (PulseAudio/PipeWire).

        More compatible with modern Linux audio systems than sounddevice.
        """
        logger.info("[WhisperASR] Recording audio for %.1f seconds via parec", duration)

        # Create temp WAV file
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_file.close()

        try:
            # Use parec to record raw audio, then convert to WAV with ffmpeg
            raw_file = temp_file.name + ".raw"

            # Record with parec
            parec_cmd = [
                "parec",
                "--format=s16le",
                f"--rate={sample_rate}",
                "--channels=1",
                raw_file
            ]

            print(f"🔴 Recording for {duration} seconds - SPEAK NOW!")
            process = subprocess.Popen(
                parec_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Let it record for the specified duration
            import time
            time.sleep(duration)

            # Stop recording
            process.terminate()
            process.wait(timeout=2)

            # Convert raw to WAV using ffmpeg
            ffmpeg_cmd = [
                "ffmpeg",
                "-f", "s16le",
                "-ar", str(sample_rate),
                "-ac", "1",
                "-i", raw_file,
                "-y",  # Overwrite output
                temp_file.name
            ]

            subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )

            # Clean up raw file
            try:
                os.unlink(raw_file)
            except:
                pass

            return temp_file.name

        except Exception as e:
            logger.error(f"Recording failed: {e}")
            raise RuntimeError(f"Failed to record from microphone: {e}")
