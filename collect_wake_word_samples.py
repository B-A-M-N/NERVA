#!/usr/bin/env python3
"""
Collect audio samples for training a custom "NERVA" wake word model.

Usage:
    python collect_wake_word_samples.py --output samples/

This will guide you through recording multiple samples of saying "NERVA"
with variations in volume, speed, and tone.
"""
import subprocess
import os
import time
import argparse
from pathlib import Path


class SampleCollector:
    """Collect wake word audio samples."""

    def __init__(self, output_dir: str, sample_rate: int = 16000):
        self.output_dir = Path(output_dir)
        self.sample_rate = sample_rate
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for different sample types
        (self.output_dir / "positive").mkdir(exist_ok=True)  # "NERVA" samples
        (self.output_dir / "negative").mkdir(exist_ok=True)  # Background/other words

    def record_sample(self, filename: str, duration: float = 2.0) -> bool:
        """Record a single audio sample."""
        raw_file = filename + ".raw"
        wav_file = filename + ".wav"

        try:
            # Record with parec
            print(f"🔴 Recording for {duration} seconds...")
            process = subprocess.Popen(
                [
                    "parec",
                    "--format=s16le",
                    f"--rate={self.sample_rate}",
                    "--channels=1",
                    raw_file
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            time.sleep(duration)
            process.terminate()
            process.wait(timeout=2)

            # Convert to WAV
            subprocess.run(
                [
                    "ffmpeg",
                    "-f", "s16le",
                    "-ar", str(self.sample_rate),
                    "-ac", "1",
                    "-i", raw_file,
                    "-y",
                    wav_file
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )

            # Clean up raw file
            os.unlink(raw_file)

            print(f"✅ Saved: {wav_file}")
            return True

        except Exception as e:
            print(f"❌ Recording failed: {e}")
            return False

    def collect_positive_samples(self, count: int = 100):
        """Collect positive samples (saying "NERVA")."""
        print("\n" + "="*60)
        print("COLLECTING POSITIVE SAMPLES")
        print("="*60)
        print(f"\nWe need {count} samples of you saying 'NERVA'")
        print("\nTips for good samples:")
        print("  • Say it clearly and naturally")
        print("  • Vary your tone (normal, excited, quiet)")
        print("  • Vary your speed (slow, normal, fast)")
        print("  • Try different distances from mic")
        print("  • Include some background noise variation")
        print("\nPress Enter to start each recording, or 'q' to quit early\n")

        successful = 0
        for i in range(count):
            print(f"\n[{i+1}/{count}] ", end="")

            # Provide guidance on what variation to use
            if i % 10 == 0:
                print("(Normal volume and speed)")
            elif i % 10 == 1:
                print("(Louder)")
            elif i % 10 == 2:
                print("(Quieter)")
            elif i % 10 == 3:
                print("(Faster)")
            elif i % 10 == 4:
                print("(Slower)")
            elif i % 10 == 5:
                print("(Further from mic)")
            elif i % 10 == 6:
                print("(Closer to mic)")
            elif i % 10 == 7:
                print("(Excited tone)")
            elif i % 10 == 8:
                print("(Calm tone)")
            else:
                print("(Natural)")

            response = input("Ready? Press Enter to record 'NERVA' (or 'q' to quit): ")
            if response.lower() == 'q':
                break

            filename = self.output_dir / "positive" / f"nerva_{i:04d}"
            if self.record_sample(str(filename), duration=2.0):
                successful += 1

        print(f"\n✅ Collected {successful} positive samples!")
        return successful

    def collect_negative_samples(self, count: int = 50):
        """Collect negative samples (background noise, other words)."""
        print("\n" + "="*60)
        print("COLLECTING NEGATIVE SAMPLES")
        print("="*60)
        print(f"\nWe need {count} samples of background noise and other words")
        print("\nThese help the model learn what's NOT 'NERVA':")
        print("  • Silence / background noise")
        print("  • Other similar words (never, nerve, servo, etc.)")
        print("  • Common phrases you might say")
        print("  • Music, TV, other sounds")
        print("\nPress Enter to start each recording, or 'q' to quit early\n")

        successful = 0
        for i in range(count):
            if i % 5 == 0:
                suggestion = "(Just background noise - don't speak)"
            elif i % 5 == 1:
                suggestion = "(Say a similar word like 'never' or 'nerve')"
            elif i % 5 == 2:
                suggestion = "(Say a random phrase)"
            elif i % 5 == 3:
                suggestion = "(Play some music or TV)"
            else:
                suggestion = "(Cough, sneeze, or other sound)"

            print(f"\n[{i+1}/{count}] {suggestion}")
            response = input("Ready? Press Enter to record (or 'q' to quit): ")
            if response.lower() == 'q':
                break

            filename = self.output_dir / "negative" / f"negative_{i:04d}"
            if self.record_sample(str(filename), duration=2.0):
                successful += 1

        print(f"\n✅ Collected {successful} negative samples!")
        return successful

    def show_summary(self):
        """Show collection summary."""
        positive_count = len(list((self.output_dir / "positive").glob("*.wav")))
        negative_count = len(list((self.output_dir / "negative").glob("*.wav")))

        print("\n" + "="*60)
        print("COLLECTION SUMMARY")
        print("="*60)
        print(f"\n📊 Positive samples (NERVA): {positive_count}")
        print(f"📊 Negative samples (other): {negative_count}")
        print(f"📁 Output directory: {self.output_dir}")

        if positive_count >= 100:
            print("\n✅ Good! You have enough samples to start training.")
            print("\nNext steps:")
            print("1. Review samples - listen to ensure quality")
            print("2. Optionally collect more for better accuracy")
            print("3. Use openWakeWord training tools to create model")
            print("4. See WAKE_WORD_IMPLEMENTATION.md for training guide")
        else:
            print(f"\n⚠️  Recommended: Collect {100 - positive_count} more positive samples")
            print("   More samples = better accuracy")

        print("\n")


def main():
    parser = argparse.ArgumentParser(description="Collect NERVA wake word training samples")
    parser.add_argument(
        "--output",
        type=str,
        default="wake_word_samples",
        help="Output directory for samples (default: wake_word_samples)"
    )
    parser.add_argument(
        "--positive",
        type=int,
        default=100,
        help="Number of positive samples to collect (default: 100)"
    )
    parser.add_argument(
        "--negative",
        type=int,
        default=50,
        help="Number of negative samples to collect (default: 50)"
    )
    parser.add_argument(
        "--skip-negative",
        action="store_true",
        help="Skip collecting negative samples"
    )
    args = parser.parse_args()

    print("\n" + "="*60)
    print("NERVA WAKE WORD SAMPLE COLLECTION")
    print("="*60)
    print("\nThis script will help you collect audio samples for training")
    print("a custom 'NERVA' wake word model.")
    print(f"\nSamples will be saved to: {args.output}/")
    print("\n⚠️  Make sure your microphone is working!")
    print("   Test it first with: python test_voice.py --mode live\n")

    input("Press Enter to begin...")

    collector = SampleCollector(args.output)

    # Collect positive samples
    collector.collect_positive_samples(args.positive)

    # Collect negative samples
    if not args.skip_negative:
        print("\n")
        input("Press Enter to continue with negative samples...")
        collector.collect_negative_samples(args.negative)

    # Show summary
    collector.show_summary()


if __name__ == "__main__":
    main()
