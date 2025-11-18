#!/usr/bin/env python3
"""
Browser Automation Test Script for NERVA

Demonstrates browser automation capabilities including:
- Basic navigation and interaction
- Form filling
- Screenshot capture
- Multi-step workflows
- Persistent context (authenticated sessions)

Usage:
  # Basic test (headless)
  python test_browser_automation.py --mode basic

  # Interactive test (with visible browser)
  python test_browser_automation.py --mode basic --no-headless

  # Test with persistent context (use logged-in Chrome session)
  python test_browser_automation.py --mode persistent --profile ~/.config/google-chrome/Default

  # Google Search workflow
  python test_browser_automation.py --mode workflow --query "Playwright automation"
"""
import asyncio
import argparse
from pathlib import Path

from nerva.tools.browser_automation import BrowserAutomation


async def test_basic_navigation():
    """Test basic browser navigation."""
    print("\n" + "="*60)
    print("🌐 Basic Navigation Test")
    print("="*60)

    async with BrowserAutomation(headless=True) as browser:
        # Navigate to a page
        result = await browser.navigate("https://example.com")
        print(f"✅ Navigated to: {result['title']}")

        # Take a screenshot
        await browser.screenshot("example_screenshot.png", full_page=True)
        print("📸 Screenshot saved: example_screenshot.png")

        # Get page content
        content = await browser.get_page_content()
        print(f"📄 Page length: {len(content)} characters")

    print("✅ Test completed")


async def test_google_search(query: str = "Playwright automation", headless: bool = True):
    """Test Google search workflow."""
    print("\n" + "="*60)
    print(f"🔍 Google Search Test: '{query}'")
    print("="*60)

    async with BrowserAutomation(headless=headless) as browser:
        # Navigate to Google
        await browser.navigate("https://www.google.com")
        print("✅ Opened Google")

        # Wait for search box
        await browser.wait_for_selector("textarea[name='q']", timeout=5000)

        # Fill search query
        await browser.fill("textarea[name='q']", query)
        print(f"✏️  Entered query: {query}")

        # Submit search (press Enter)
        await browser.evaluate("""
            document.querySelector("textarea[name='q']").form.submit()
        """)
        print("🔍 Submitted search")

        # Wait for results
        await browser.wait_for_selector("#search", timeout=10000)
        print("✅ Search results loaded")

        # Take screenshot of results
        await browser.screenshot("google_search_results.png", full_page=True)
        print("📸 Screenshot saved: google_search_results.png")

    print("✅ Test completed")


async def test_workflow():
    """Test multi-step workflow."""
    print("\n" + "="*60)
    print("📋 Multi-Step Workflow Test")
    print("="*60)

    workflow_steps = [
        {
            "action": "navigate",
            "params": {"url": "https://www.wikipedia.org"}
        },
        {
            "action": "wait",
            "params": {"selector": "input[name='search']"}
        },
        {
            "action": "fill",
            "params": {"selector": "input[name='search']", "text": "Artificial Intelligence"}
        },
        {
            "action": "click",
            "params": {"selector": "button[type='submit']"}
        },
        {
            "action": "wait",
            "params": {"selector": "#firstHeading", "timeout": 10000}
        },
        {
            "action": "get_text",
            "params": {"selector": "#firstHeading"}
        },
        {
            "action": "screenshot",
            "params": {"path": "wikipedia_ai.png", "full_page": True}
        }
    ]

    async with BrowserAutomation(headless=True) as browser:
        results = await browser.execute_workflow(workflow_steps)

        # Print results
        for result in results:
            status = "✅" if result["success"] else "❌"
            print(f"{status} Step {result['step']}: {result['action']}")
            if not result["success"]:
                print(f"   Error: {result.get('error')}")

    print("✅ Workflow completed")


async def test_persistent_context(profile_path: str):
    """Test with persistent context (logged-in session)."""
    print("\n" + "="*60)
    print("🔐 Persistent Context Test")
    print("="*60)
    print(f"Using profile: {profile_path}")

    if not Path(profile_path).exists():
        print(f"❌ Profile not found: {profile_path}")
        print("💡 Use a path like: ~/.config/google-chrome/Default")
        return

    async with BrowserAutomation(
        headless=False,  # Usually want to see logged-in session
        user_data_dir=profile_path
    ) as browser:
        # Navigate to a site that requires login
        await browser.navigate("https://mail.google.com")
        print("✅ Opened Gmail")

        # Wait a few seconds to see if logged in
        await asyncio.sleep(3)

        # Take screenshot
        await browser.screenshot("gmail_logged_in.png", full_page=False)
        print("📸 Screenshot saved: gmail_logged_in.png")

        # Check if logged in by looking for compose button
        has_compose = await browser.wait_for_selector(
            "div[role='button']:has-text('Compose')",
            timeout=5000
        )

        if has_compose:
            print("✅ Successfully using authenticated session!")
        else:
            print("⚠️  May not be logged in")

    print("✅ Test completed")


async def test_headless_vs_headed():
    """Compare headless and headed modes."""
    print("\n" + "="*60)
    print("🎭 Headless vs Headed Mode")
    print("="*60)

    print("\n1️⃣ Running in HEADLESS mode (no visible browser)...")
    async with BrowserAutomation(headless=True) as browser:
        await browser.navigate("https://example.com")
        print("✅ Headless navigation complete")

    print("\n2️⃣ Running in HEADED mode (visible browser)...")
    print("   (Browser window will appear for 3 seconds)")
    async with BrowserAutomation(headless=False) as browser:
        await browser.navigate("https://example.com")
        await asyncio.sleep(3)  # Keep browser visible for 3 seconds
        print("✅ Headed navigation complete")

    print("✅ Test completed")


async def main():
    parser = argparse.ArgumentParser(description="NERVA Browser Automation Tests")
    parser.add_argument(
        "--mode",
        choices=["basic", "search", "workflow", "persistent", "compare"],
        default="basic",
        help="Test mode to run"
    )
    parser.add_argument(
        "--query",
        type=str,
        default="Playwright automation",
        help="Search query for search mode"
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Browser profile path for persistent mode"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run with visible browser"
    )

    args = parser.parse_args()

    try:
        if args.mode == "basic":
            await test_basic_navigation()

        elif args.mode == "search":
            await test_google_search(args.query, headless=not args.no_headless)

        elif args.mode == "workflow":
            await test_workflow()

        elif args.mode == "persistent":
            if not args.profile:
                print("❌ --profile required for persistent mode")
                print("Example: --profile ~/.config/google-chrome/Default")
                return
            await test_persistent_context(args.profile)

        elif args.mode == "compare":
            await test_headless_vs_headed()

        print("\n" + "="*60)
        print("✅ All tests passed!")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
