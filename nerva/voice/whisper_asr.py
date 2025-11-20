# nerva/voice/whisper_asr_fixed.py
"""
Fixed Whisper ASR using parec for PulseAudio/PipeWire compatibility.
Adds silence-aware recording for natural utterances.
"""
from __future__ import annotations
from typing import Optional, List
import logging
import os
import tempfile
import subprocess
from pathlib import Path
import time
import audioop

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


class WhisperASR:
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

    def transcribe_until_silence(
        self,
        min_duration: float = 1.0,
        silence_duration: float = 3.0,
        max_duration: float = 30.0,
        sample_rate: int = 16000,
        silence_threshold: int = 300,
        wait_for_voice: bool = False,
        voice_activation: float = 0.4,
    ) -> Optional[str]:
        """
        Record audio until a period of silence is observed, then transcribe.

        Args:
            min_duration: Minimum time to record before listening for silence.
            silence_duration: Stop after this many seconds of silence.
            max_duration: Hard cap on recording length.
            sample_rate: Recording sample rate.
            silence_threshold: RMS threshold (0-32767) to treat as silence.
            wait_for_voice: If True, waits for speech before starting min_duration timer.
            voice_activation: Seconds of speech required to trigger recording when wait_for_voice is True.
        """
        try:
            temp_path = Path(
                self._record_until_silence_parec(
                    min_duration=min_duration,
                    silence_duration=silence_duration,
                    max_duration=max_duration,
                    sample_rate=sample_rate,
                    silence_threshold=silence_threshold,
                    wait_for_voice=wait_for_voice,
                    voice_activation=voice_activation,
                )
            )
        except RuntimeError as exc:
            logger.error(f"[WhisperASR] {exc}")
            return None

        try:
            return self.transcribe_once(audio_path=str(temp_path))
        finally:
            if temp_path.exists():
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

    def _record_until_silence_parec(
        self,
        min_duration: float,
        silence_duration: float,
        max_duration: float,
        sample_rate: int,
        silence_threshold: int,
        wait_for_voice: bool = False,
        voice_activation: float = 0.5,
    ) -> str:
        """Record audio until silence using parec streaming."""
        logger.info(
                "[WhisperASR] Recording until %.1fs silence (max %.1fs, baseline=%.0f)",
                silence_duration,
                max_duration,
                silence_threshold,
            )

        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_file.close()
        raw_file = temp_file.name + ".raw"

        chunk_duration = 0.1  # seconds
        bytes_per_chunk = int(sample_rate * chunk_duration * 2)  # s16le

        try:
            parec_cmd = [
                "parec",
                "--format=s16le",
                f"--rate={sample_rate}",
                "--channels=1",
            ]
            process = subprocess.Popen(
                parec_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            recorded = 0.0
            silence_time = 0.0
            noise_floor = None
            padding = 250  # dynamic boost over noise floor (increased for noisy environments)
            voice_detected = not wait_for_voice
            voice_time = 0.0
            pre_buffer: List[bytes] = []
            max_pre_buffer = int(1.0 / chunk_duration)  # keep up to 1 second pre-voice

            with open(raw_file, "wb") as raw_fp:
                print("🎙️ Speak now (recording stops after silence)...")
                while recorded < max_duration:
                    chunk = process.stdout.read(bytes_per_chunk)
                    if not chunk:
                        break

                    if not voice_detected:
                        pre_buffer.append(chunk)
                        if len(pre_buffer) > max_pre_buffer:
                            pre_buffer.pop(0)
                    else:
                        raw_fp.write(chunk)
                        recorded += chunk_duration

                    rms = audioop.rms(chunk, 2)
                    if noise_floor is None:
                        noise_floor = rms
                    else:
                        if rms < noise_floor:
                            noise_floor = rms * 0.6 + noise_floor * 0.4
                        else:
                            noise_floor = noise_floor * 0.97 + rms * 0.03

                    dynamic_threshold = max(silence_threshold, (noise_floor or 0) + padding)

                    if not voice_detected:
                        if rms > dynamic_threshold:
                            voice_time += chunk_duration
                            if voice_time >= voice_activation:
                                voice_detected = True
                                silence_time = 0.0
                                # write pre-buffer
                                for buf in pre_buffer:
                                    raw_fp.write(buf)
                                    recorded += chunk_duration
                                pre_buffer.clear()
                        else:
                            voice_time = max(0.0, voice_time - chunk_duration)
                        continue

                    if rms <= dynamic_threshold:
                        silence_time += chunk_duration
                        # Show progress on silence detection
                        if silence_time >= 0.5 and int(silence_time * 10) % 5 == 0:
                            print(f"   Silence: {silence_time:.1f}s / {silence_duration:.1f}s (RMS={rms} threshold={int(dynamic_threshold)})", end='\r')
                    else:
                        if silence_time > 0:
                            print(" " * 80, end='\r')  # Clear silence indicator
                        silence_time = 0.0
                        # Show voice activity
                        if int(recorded * 4) % 2 == 0:  # Update every 0.5s
                            print(f"   🔴 Recording... {recorded:.1f}s (RMS={rms} threshold={int(dynamic_threshold)})", end='\r')

                    if recorded >= min_duration and silence_time >= silence_duration:
                        print(" " * 80, end='\r')  # Clear before break
                        print(f"✅ Recording stopped after {silence_time:.1f}s silence")
                        break

            process.terminate()
            process.wait(timeout=2)

            if recorded == 0:
                raise RuntimeError("No audio captured from microphone.")

            ffmpeg_cmd = [
                "ffmpeg",
                "-f",
                "s16le",
                "-ar",
                str(sample_rate),
                "-ac",
                "1",
                "-i",
                raw_file,
                "-y",
                temp_file.name,
            ]
            subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )

            try:
                os.unlink(raw_file)
            except OSError:
                pass

            return temp_file.name

        except Exception as exc:
            logger.error(f"Recording failed: {exc}")
            raise RuntimeError(f"Failed to record from microphone: {exc}")
        finally:
            if "process" in locals():
                process.terminate()
                try:
                    process.wait(timeout=2)
                except Exception:
                    pass
