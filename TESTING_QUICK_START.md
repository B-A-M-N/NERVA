# NERVA Testing Quick Start

This guide covers the new testing capabilities for voice commands and browser automation.

---

## Voice Testing

Test NERVA's voice capabilities without requiring a microphone or audio files.

### Quick Test Commands

```bash
# Test with mock transcription (no microphone needed)
python test_voice.py --mode mock --text "what is 2+2"

# Test with audio file
python test_voice.py --mode file --audio recording.wav

# Test with live microphone
python test_voice.py --mode live --duration 5

# Batch test multiple scenarios
python test_voice.py --mode batch

# Enable TTS output
python test_voice.py --mode mock --text "hello world" --tts
```

### Voice Testing Modes

1. **Mock Mode** (Recommended for automated testing)
   - No microphone required
   - Simulates transcription with predefined text
   - Fast and reliable
   - Great for CI/CD pipelines

2. **File Mode** (Test with recordings)
   - Uses pre-recorded audio files
   - Tests actual ASR (Whisper) transcription
   - Good for regression testing

3. **Live Mode** (Real microphone)
   - Tests complete voice pipeline
   - Records from your microphone
   - Best for manual testing

4. **Batch Mode** (Multiple scenarios)
   - Runs predefined test suite
   - Tests various voice commands
   - Shows pass/fail summary

### Example Output

```
============================================================
🎭 Testing Mock Voice: 'what is 2+2'
============================================================

🤖 NERVA: 2 + 2 = 4.

============================================================
✅ Test completed successfully
============================================================
```

---

## Browser Automation

Control web browsers programmatically for web scraping, form automation, and testing.

### Quick Test Commands

```bash
# Basic navigation test
python test_browser_automation.py --mode basic

# Google search test (visible browser)
python test_browser_automation.py --mode search --no-headless --query "AI news"

# Multi-step workflow
python test_browser_automation.py --mode workflow

# Test with logged-in Chrome session
python test_browser_automation.py --mode persistent --profile ~/.config/google-chrome/Default

# Compare headless vs headed modes
python test_browser_automation.py --mode compare
```

### Browser Automation Modes

1. **Basic Mode**
   - Simple navigation test
   - Takes screenshot
   - Verifies core functionality

2. **Search Mode**
   - Demonstrates form filling
   - Submits search query
   - Captures results

3. **Workflow Mode**
   - Multi-step task execution
   - Wikipedia search example
   - Shows error handling

4. **Persistent Mode**
   - Uses existing browser profile
   - Accesses authenticated sessions
   - **Great for Gmail, Calendar, etc.**

### Example: Using with Google Services

```python
from nerva.tools.browser_automation import BrowserAutomation
import asyncio

async def check_gmail():
    # Use your logged-in Chrome profile
    async with BrowserAutomation(
        headless=False,
        user_data_dir="~/.config/google-chrome/Default"
    ) as browser:
        # Navigate to Gmail - already logged in!
        await browser.navigate("https://mail.google.com")

        # Wait for inbox
        await browser.wait_for_selector("div[role='main']", timeout=10000)

        # Take screenshot
        await browser.screenshot("gmail.png")

asyncio.run(check_gmail())
```

---

## Integration Examples

### Voice + LLM Integration

```python
# Test voice input with NERVA's LLM
python test_voice.py --mode mock --text "explain quantum computing"
```

### Browser + Agent Integration

```python
from nerva.tools.browser_automation import BrowserAutomation
from nerva.llm.factory import create_llm_client
from nerva.config import NervaConfig

async def agent_browse():
    config = NervaConfig()
    llm = create_llm_client(config)

    async with BrowserAutomation() as browser:
        # Navigate and extract data
        await browser.navigate("https://news.ycombinator.com")
        titles = await browser.evaluate("""
            Array.from(document.querySelectorAll('.titleline > a'))
                .slice(0, 5)
                .map(a => a.textContent)
        """)

        # Ask LLM to summarize
        prompt = f"Summarize these top HN stories: {titles}"
        summary = await llm.chat([{"role": "user", "content": prompt}])
        print(summary)
```

---

## Answer to Your Questions

### 1. Testing Vocal Commands

**You can now test voice commands without a microphone:**
```bash
python test_voice.py --mode mock --text "what is the weather"
python test_voice.py --mode batch  # Test multiple commands
```

**Or test the complete voice pipeline:**
```bash
python test_voice.py --mode live  # Use real microphone
```

### 2. Browser Automation for Google Services

**For Google Calendar/Gmail (Approach 1: Browser Automation)**
```python
# ✅ Use persistent context with logged-in session
async with BrowserAutomation(
    user_data_dir="~/.config/google-chrome/Default",
    headless=False
) as browser:
    await browser.navigate("https://calendar.google.com")
    await browser.click('button[aria-label="Create"]')
    await browser.fill('input[aria-label="Add title"]', "Meeting")
    await browser.click('button[aria-label="Save"]')
```

**For Google Services (Approach 2: Google APIs - Recommended)**
```bash
pip install google-auth google-api-python-client
# Then use Google Calendar API for more reliable automation
```

**Key Point:** You **don't need to create events** in the browser if you use Google APIs. Browser automation is best for:
- Sites without APIs
- Complex interactions requiring visual feedback
- Testing web interfaces
- Scraping data from authenticated sites

---

## Files Created

- `test_voice.py` - Voice testing framework
- `test_browser_automation.py` - Browser automation tests
- `nerva/tools/browser_automation.py` - Browser automation module
- `BROWSER_AUTOMATION.md` - Full browser automation documentation

---

## Next Steps

1. **Test voice commands:**
   ```bash
   python test_voice.py --mode batch
   ```

2. **Test browser automation:**
   ```bash
   python test_browser_automation.py --mode basic
   ```

3. **Try with authenticated sessions:**
   ```bash
   # Replace with your Chrome profile path
   python test_browser_automation.py --mode persistent --profile ~/.config/google-chrome/Default
   ```

4. **Build custom automations:**
   - See examples in `BROWSER_AUTOMATION.md`
   - Integrate with NERVA workflows
   - Create agent-controlled browser tasks
