#!/usr/bin/env python3
"""
Generate synthetic NERVA wake word samples using Kokoro TTS.

This creates thousands of variations of "NERVA" with different:
- Speeds (slow, normal, fast)
- Voice styles (available Kokoro voices)
- Added noise and audio augmentations

Usage:
    python generate_synthetic_nerva.py --count 2000
"""
import argparse
import os
import numpy as np
import soundfile as sf
from pathlib import Path
from tqdm import tqdm
import sys

# Add NERVA to path
sys.path.insert(0, '/home/joker/NERVA')

from nerva.voice.kokoro_tts import KokoroTTS
from nerva.config import NervaConfig


def add_noise(audio, noise_level=0.005):
    """Add random noise to audio."""
    noise = np.random.randn(len(audio)) * noise_level
    return audio + noise


def change_speed(audio, rate, sample_rate=24000):
    """Change audio speed using resampling."""
    import scipy.signal

    # Calculate new length
    new_length = int(len(audio) * rate)

    # Resample
    resampled = scipy.signal.resample(audio, new_length)

    return resampled


def generate_synthetic_samples(output_dir: str, count: int = 2000):
    """Generate synthetic NERVA samples using Kokoro TTS."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("SYNTHETIC NERVA SAMPLE GENERATION")
    print("="*60)
    print(f"\nGenerating {count} synthetic samples...")
    print(f"Output directory: {output_path}\n")

    # Initialize Kokoro TTS
    config = NervaConfig()
    tts = KokoroTTS(model_path=config.kokoro_model)

    # Variations to generate
    texts = [
        "nerva",
        "NERVA",
        "Nerva",
        "nerva.",
        "nerva!",
        "nerva?",
        "hey nerva",
        "ok nerva",
    ]

    speeds = [0.8, 0.9, 1.0, 1.1, 1.2]  # Different speaking speeds
    noise_levels = [0.0, 0.002, 0.005, 0.01]  # Different noise levels

    sample_idx = 0

    with tqdm(total=count, desc="Generating samples") as pbar:
        while sample_idx < count:
            # Cycle through variations
            text = texts[sample_idx % len(texts)]
            speed = speeds[(sample_idx // len(texts)) % len(speeds)]
            noise_level = noise_levels[(sample_idx // (len(texts) * len(speeds))) % len(noise_levels)]

            try:
                # Generate audio with Kokoro
                temp_file = f"/tmp/nerva_temp_{sample_idx}.wav"

                # Generate speech and save to file
                tts.synthesize_to_file(text, temp_file)

                # Load the generated audio
                audio, sr = sf.read(temp_file)

                # Apply speed variation if not 1.0
                if speed != 1.0:
                    audio = change_speed(audio, speed, sr)

                # Add noise if specified
                if noise_level > 0:
                    audio = add_noise(audio, noise_level)

                # Normalize audio
                audio = audio / np.max(np.abs(audio)) if np.max(np.abs(audio)) > 0 else audio

                # Save to output directory
                output_file = output_path / f"nerva_synthetic_{sample_idx:05d}.wav"

                # Resample to 16kHz (standard for wake word detection)
                if sr != 16000:
                    import scipy.signal
                    num_samples = int(len(audio) * 16000 / sr)
                    audio = scipy.signal.resample(audio, num_samples)
                    sr = 16000

                sf.write(output_file, audio, sr)

                # Clean up temp file
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

                sample_idx += 1
                pbar.update(1)

            except Exception as e:
                print(f"\n⚠️  Error generating sample {sample_idx}: {e}")
                sample_idx += 1
                pbar.update(1)
                continue

    print(f"\n✅ Generated {sample_idx} synthetic samples!")
    print(f"📁 Saved to: {output_path}")

    # Show statistics
    files = list(output_path.glob("*.wav"))
    total_duration = 0
    for f in files[:10]:  # Sample first 10 for stats
        audio, sr = sf.read(f)
        total_duration += len(audio) / sr

    avg_duration = (total_duration / min(10, len(files))) if files else 0
    estimated_total = avg_duration * len(files)

    print(f"\n📊 Statistics:")
    print(f"   Total samples: {len(files)}")
    print(f"   Average duration: {avg_duration:.2f}s")
    print(f"   Estimated total audio: {estimated_total:.1f}s ({estimated_total/60:.1f} minutes)")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic NERVA wake word samples")
    parser.add_argument(
        "--output",
        type=str,
        default="wake_word_samples/synthetic_positive",
        help="Output directory for synthetic samples"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=2000,
        help="Number of samples to generate (default: 2000)"
    )
    args = parser.parse_args()

    generate_synthetic_samples(args.output, args.count)

    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("\n1. Combine with your manual samples:")
    print("   cp wake_word_samples/positive/*.wav wake_word_samples/synthetic_positive/")
    print("\n2. Use openWakeWord training notebook:")
    print("   https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb")
    print("\n3. Or train locally with the samples")
    print("")


if __name__ == "__main__":
    main()
