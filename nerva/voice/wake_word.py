#!/usr/bin/env python3
"""
Wake word detector using openWakeWord.
Lightweight continuous listening for trigger words like "NERVA".
"""
import subprocess
import tempfile
import os
import time
import logging
from typing import Optional, Callable
import numpy as np

logger = logging.getLogger(__name__)

try:
    from openwakeword import Model
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False
    logger.warning("openWakeWord not available - install with: pip install openwakeword")


class WakeWordDetector:
    """
    Lightweight wake word detector using openWakeWord.

    Continuously listens to audio in small chunks and detects wake words
    with minimal CPU usage compared to running Whisper constantly.
    """

    def __init__(
        self,
        wake_word: str = "hey_mycroft",
        threshold: float = 0.5,
        chunk_duration: float = 1.0,  # Process 1 second at a time
        sample_rate: int = 16000,
    ):
        """
        Args:
            wake_word: Name of wake word model (or path to custom model)
            threshold: Detection confidence threshold (0.0 to 1.0)
            chunk_duration: Audio chunk size in seconds
            sample_rate: Audio sample rate in Hz
        """
        if not OPENWAKEWORD_AVAILABLE:
            raise RuntimeError("openWakeWord not installed")

        self.wake_word = wake_word
        self.threshold = threshold
        self.chunk_duration = chunk_duration
        self.sample_rate = sample_rate
        self.chunk_samples = int(sample_rate * chunk_duration)

        # Load wake word model
        logger.info(f"Loading wake word model: {wake_word}")

        # Initialize model with specific wake word models that have ONNX versions
        # Use ONNX backend for NumPy 2.x compatibility (tflite requires NumPy 1.x)
        # Available ONNX models: alexa, hey_jarvis, hey_rhasspy
        wakeword_models = [wake_word]
        self.model = Model(wakeword_models=wakeword_models, inference_framework="onnx")

        # Find the actual model name from loaded models
        self.model_name = None
        for name in self.model.models.keys():
            if wake_word.lower() in name.lower():
                self.model_name = name
                break

        if not self.model_name and self.model.models:
            # Just use the first available model
            self.model_name = list(self.model.models.keys())[0]
            logger.warning(f"Wake word '{wake_word}' not found, using '{self.model_name}'")

        logger.info(f"✅ Wake word detector ready: {self.model_name} (threshold={threshold})")

    def listen_continuous(
        self,
        on_wake_word: Callable[[], None],
        stop_event: Optional[object] = None,
    ):
        """
        Continuously listen for wake word and call callback when detected.

        Args:
            on_wake_word: Callback function to call when wake word detected
            stop_event: Optional threading.Event to signal stop
        """
        logger.info(f"🎤 Listening for wake word '{self.wake_word}'...")

        # Start audio stream with parec
        process = subprocess.Popen(
            [
                "parec",
                "--format=s16le",
                f"--rate={self.sample_rate}",
                "--channels=1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        try:
            bytes_per_chunk = self.chunk_samples * 2  # 2 bytes per sample (s16le)

            while True:
                # Check stop signal
                if stop_event and stop_event.is_set():
                    break

                # Read audio chunk
                audio_bytes = process.stdout.read(bytes_per_chunk)
                if not audio_bytes:
                    break

                # Convert to numpy array (int16)
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16)

                # Run wake word detection
                predictions = self.model.predict(audio_data)

                # Check if wake word detected
                if self.model_name in predictions:
                    score = predictions[self.model_name]
                    if score >= self.threshold:
                        logger.info(f"✅ Wake word detected! (confidence={score:.2f})")
                        process.terminate()
                        on_wake_word()
                        return

        finally:
            process.terminate()
            process.wait(timeout=2)

    def listen_once(self, timeout: float = 30.0) -> bool:
        """
        Listen for wake word with timeout.

        Args:
            timeout: Maximum time to listen in seconds

        Returns:
            True if wake word detected, False if timeout
        """
        logger.info(f"🎤 Listening for wake word (timeout={timeout}s)...")

        # Start audio stream
        process = subprocess.Popen(
            [
                "parec",
                "--format=s16le",
                f"--rate={self.sample_rate}",
                "--channels=1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        try:
            bytes_per_chunk = self.chunk_samples * 2
            start_time = time.time()

            while time.time() - start_time < timeout:
                # Read audio chunk
                audio_bytes = process.stdout.read(bytes_per_chunk)
                if not audio_bytes:
                    break

                # Convert to numpy array
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16)

                # Run detection
                predictions = self.model.predict(audio_data)

                # Check for wake word
                if self.model_name in predictions:
                    score = predictions[self.model_name]
                    if score >= self.threshold:
                        logger.info(f"✅ Wake word detected! (confidence={score:.2f})")
                        return True

            logger.info("⏱️ Timeout - no wake word detected")
            return False

        finally:
            process.terminate()
            process.wait(timeout=2)


def test_wake_word():
    """Test wake word detection."""
    print("="*60)
    print("Wake Word Detection Test")
    print("="*60)
    print(f"\n📋 Say 'Hey Mycroft' to test")
    print("   (We'll train a custom 'NERVA' model later)\n")

    detector = WakeWordDetector(wake_word="hey_mycroft", threshold=0.5)

    detected = detector.listen_once(timeout=10.0)

    if detected:
        print("\n✅ SUCCESS! Wake word detected!")
    else:
        print("\n❌ No wake word detected in 10 seconds")

    print("\n" + "="*60)


if __name__ == "__main__":
    test_wake_word()
