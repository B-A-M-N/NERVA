#!/usr/bin/env python3
"""Quick test of vision model with a simple screenshot."""
import asyncio
import sys
sys.path.insert(0, '/home/joker/NERVA')

from nerva.vision.qwen_vision import QwenVision
from PIL import Image, ImageDraw, ImageFont
import io


async def test_vision():
    """Test vision model with a generated test image."""
    print("Testing QwenVision with qwen3-vl:4b...")

    # Create a simple test image with text
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)

    # Draw some UI elements
    draw.rectangle([50, 50, 300, 100], fill='blue', outline='black', width=2)
    draw.text((75, 65), "Search Button", fill='white')

    draw.rectangle([50, 150, 500, 200], fill='lightgray', outline='black', width=2)
    draw.text((75, 165), "Enter search query here...", fill='gray')

    draw.rectangle([50, 250, 200, 300], fill='green', outline='black', width=2)
    draw.text((75, 265), "Submit", fill='white')

    # Save test image
    test_path = "/tmp/test_vision.png"
    img.save(test_path)
    print(f"Created test image: {test_path}")

    # Initialize vision model
    vision = QwenVision(model="qwen3-vl:4b")

    # Test 1: Basic analysis
    print("\n" + "="*60)
    print("TEST 1: Basic Screenshot Analysis")
    print("="*60)
    response = await vision.analyze_screenshot(
        test_path,
        prompt="Describe what you see in this image."
    )
    print(response)

    # Test 2: Extract UI elements
    print("\n" + "="*60)
    print("TEST 2: UI Element Extraction")
    print("="*60)
    response = await vision.extract_ui_elements(test_path)
    print(response)

    # Test 3: Extract browser action
    print("\n" + "="*60)
    print("TEST 3: Browser Action Extraction")
    print("="*60)
    response = await vision.extract_browser_action(
        test_path,
        task="Click the search button and enter 'test query'"
    )
    print(response)

    print("\n✅ Vision model is working!")


if __name__ == "__main__":
    asyncio.run(test_vision())
