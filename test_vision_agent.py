#!/usr/bin/env python3
"""
Test the VisionActionAgent with a simple browser task.

This demonstrates the vision → reasoning → action loop:
1. Take screenshot of browser
2. Vision model analyzes and determines action
3. Execute action
4. Repeat until task complete
"""
import asyncio
import sys
import logging

sys.path.insert(0, '/home/joker/NERVA')

from nerva.agents.vision_action_agent import VisionActionAgent
from nerva.vision.qwen_vision import QwenVision
from nerva.tools.browser_automation import BrowserAutomation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_simple_task():
    """Test VisionActionAgent with a simple Google search task."""
    print("="*60)
    print("VISION ACTION AGENT TEST")
    print("="*60)
    print("\nThis will:")
    print("1. Open Google in a browser")
    print("2. Use vision to find and click the search box")
    print("3. Type a query")
    print("4. Submit the search")
    print("\nThe browser will open in non-headless mode so you can watch!\n")

    # Create agent
    vision = QwenVision(model="qwen3-vl:4b")
    browser = BrowserAutomation(headless=False)  # Non-headless to watch
    agent = VisionActionAgent(
        vision=vision,
        browser=browser,
        max_steps=10,
    )

    # Define task
    task = "Search for 'Python asyncio tutorial' on Google"
    starting_url = "https://google.com"

    print(f"📋 Task: {task}")
    print(f"🌐 Starting URL: {starting_url}\n")

    try:
        # Execute task
        result = await agent.execute_task(
            task=task,
            starting_url=starting_url,
        )

        # Print results
        print("\n" + "="*60)
        print("TASK RESULT")
        print("="*60)
        print(f"Status: {result['status']}")
        print(f"Reason: {result['reason']}")
        print(f"Steps taken: {result['steps']}")

        # Print action history
        print("\n" + "="*60)
        print("ACTION HISTORY")
        print("="*60)
        for entry in result['history']:
            print(f"\nStep {entry['step']}:")
            print(f"  Action: {entry['action'].action_type}")
            print(f"  Target: {entry['action'].target}")
            if entry['action'].value:
                print(f"  Value: {entry['action'].value}")
            print(f"  Reason: {entry['action'].reason}")
            print(f"  Confidence: {entry['action'].confidence}")
            if 'error' in entry:
                print(f"  ⚠️  Error: {entry['error']}")

        print("\n" + "="*60)
        print("Screenshots saved to: /tmp/nerva_screenshots/")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def test_screenshot_analysis():
    """Test just the vision analysis on a screenshot."""
    print("="*60)
    print("VISION SCREENSHOT ANALYSIS TEST")
    print("="*60)

    # Create vision model
    vision = QwenVision(model="qwen3-vl:4b")

    # Test with a screenshot if it exists
    import os
    screenshot_dir = "/tmp/nerva_screenshots"

    if os.path.exists(screenshot_dir) and os.listdir(screenshot_dir):
        # Use most recent screenshot
        screenshots = sorted(os.listdir(screenshot_dir))
        latest = os.path.join(screenshot_dir, screenshots[-1])

        print(f"\n📸 Analyzing screenshot: {latest}\n")

        # Analyze
        analysis = await vision.analyze_screenshot(
            latest,
            prompt="Describe what you see in this screenshot in detail."
        )

        print("Vision Analysis:")
        print(analysis)

        # Extract UI elements
        print("\n" + "="*60)
        print("UI ELEMENTS")
        print("="*60)

        elements = await vision.extract_ui_elements(latest)
        print(elements)

    else:
        print("\n⚠️  No screenshots found. Run test_simple_task() first.\n")


async def main():
    """Main test runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Test VisionActionAgent")
    parser.add_argument(
        "--mode",
        choices=["task", "analyze"],
        default="task",
        help="Test mode: 'task' for full agent test, 'analyze' for screenshot analysis only"
    )

    args = parser.parse_args()

    if args.mode == "task":
        await test_simple_task()
    else:
        await test_screenshot_analysis()


if __name__ == "__main__":
    asyncio.run(main())
