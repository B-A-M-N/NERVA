# Browser Automation for NERVA

NERVA's browser automation module provides programmatic browser control for complex web tasks, enabling your AI agent to interact with websites, fill forms, extract data, and work with authenticated sessions.

## Features

- **Web Navigation**: Automated browsing and page interaction
- **Form Automation**: Fill forms, click buttons, submit data
- **Authenticated Sessions**: Use existing logged-in browser profiles
- **Data Extraction**: Scrape content, capture screenshots
- **Multi-Step Workflows**: Execute complex task sequences
- **Headless/Headed Modes**: Run invisibly or with visible browser

---

## Installation

```bash
# Install Playwright
pip install playwright

# Download browser binaries
playwright install chromium
```

---

## Quick Start

### Basic Usage

```python
import asyncio
from nerva.tools.browser_automation import BrowserAutomation

async def simple_navigation():
    # Create browser instance (headless by default)
    async with BrowserAutomation() as browser:
        # Navigate to a page
        result = await browser.navigate("https://example.com")
        print(f"Page title: {result['title']}")

        # Take screenshot
        await browser.screenshot("page.png", full_page=True)

asyncio.run(simple_navigation())
```

### Form Automation

```python
async def google_search():
    async with BrowserAutomation(headless=False) as browser:
        # Navigate to Google
        await browser.navigate("https://www.google.com")

        # Fill search box
        await browser.fill("textarea[name='q']", "Playwright automation")

        # Submit form
        await browser.evaluate("document.querySelector('textarea[name=q]').form.submit()")

        # Wait for results
        await browser.wait_for_selector("#search", timeout=10000)

        # Capture results
        await browser.screenshot("search_results.png")

asyncio.run(google_search())
```

### Multi-Step Workflows

```python
async def wikipedia_workflow():
    workflow = [
        {"action": "navigate", "params": {"url": "https://wikipedia.org"}},
        {"action": "fill", "params": {"selector": "input[name='search']", "text": "AI"}},
        {"action": "click", "params": {"selector": "button[type='submit']"}},
        {"action": "wait", "params": {"selector": "#firstHeading"}},
        {"action": "screenshot", "params": {"path": "article.png"}}
    ]

    async with BrowserAutomation() as browser:
        results = await browser.execute_workflow(workflow)

        for result in results:
            print(f"Step {result['step']}: {result['action']} - {'✅' if result['success'] else '❌'}")

asyncio.run(wikipedia_workflow())
```

---

## Authenticated Sessions (Persistent Context)

Use existing logged-in browser sessions to automate tasks in Google, Facebook, or other authenticated services.

### Finding Your Chrome Profile Path

**Linux:**
```bash
ls ~/.config/google-chrome/
# Usually: ~/.config/google-chrome/Default
```

**macOS:**
```bash
ls ~/Library/Application Support/Google/Chrome/
# Usually: ~/Library/Application Support/Google/Chrome/Default
```

**Windows:**
```
C:\Users\<YourName>\AppData\Local\Google\Chrome\User Data\Default
```

### Using Persistent Context

```python
async def gmail_automation():
    # Use existing Chrome profile with logged-in session
    async with BrowserAutomation(
        headless=False,  # Usually want to see authenticated sessions
        user_data_dir="~/.config/google-chrome/Default"
    ) as browser:
        # Navigate to Gmail (already logged in!)
        await browser.navigate("https://mail.google.com")

        # Wait for inbox to load
        await browser.wait_for_selector("div[role='main']", timeout=10000)

        # Take screenshot of inbox
        await browser.screenshot("gmail_inbox.png")

        print("✅ Accessed Gmail with authenticated session")

asyncio.run(gmail_automation())
```

---

## API Reference

### BrowserAutomation Class

#### Constructor

```python
BrowserAutomation(
    headless: bool = True,           # Run without visible browser
    browser_type: str = "chromium",  # "chromium", "firefox", or "webkit"
    user_data_dir: Optional[str] = None  # Path to browser profile
)
```

#### Methods

**navigate(url, wait_until="domcontentloaded")**
Navigate to a URL.

**click(selector, timeout=30000)**
Click an element by CSS selector.

**fill(selector, text, timeout=30000)**
Fill a form field with text.

**get_text(selector, timeout=30000)**
Get text content of an element.

**screenshot(path=None, full_page=False)**
Take a screenshot. Returns bytes if path not provided.

**wait_for_selector(selector, timeout=30000, state="visible")**
Wait for an element to appear.

**evaluate(script)**
Execute JavaScript on the page.

**execute_workflow(steps)**
Execute a multi-step workflow.

---

## Testing

Run the test suite to verify browser automation:

```bash
# Basic navigation test
python test_browser_automation.py --mode basic

# Google search test (with visible browser)
python test_browser_automation.py --mode search --no-headless

# Multi-step workflow
python test_browser_automation.py --mode workflow

# Test with authenticated session
python test_browser_automation.py --mode persistent --profile ~/.config/google-chrome/Default
```

---

## Integration with NERVA Agent

### Example: Agent-Controlled Web Search

```python
from nerva.tools.browser_automation import BrowserAutomation
from nerva.llm.factory import create_llm_client
from nerva.config import NervaConfig

async def agent_web_search(query: str):
    """Agent performs web search and summarizes results."""

    # Get LLM client
    config = NervaConfig()
    llm = create_llm_client(config)

    # Perform search
    async with BrowserAutomation(headless=True) as browser:
        await browser.navigate("https://www.google.com")
        await browser.fill("textarea[name='q']", query)
        await browser.evaluate("document.querySelector('textarea[name=q]').form.submit()")
        await browser.wait_for_selector("#search")

        # Extract search results
        results_html = await browser.evaluate("""
            Array.from(document.querySelectorAll('#search .g')).slice(0, 5).map(el => ({
                title: el.querySelector('h3')?.textContent || '',
                snippet: el.querySelector('.VwiC3b')?.textContent || ''
            }))
        """)

        # Ask LLM to summarize
        prompt = f"Summarize these search results for '{query}':\n{results_html}"
        messages = [{"role": "user", "content": prompt}]
        summary = await llm.chat(messages)

        return summary

# Usage
result = asyncio.run(agent_web_search("latest AI research"))
print(result)
```

### Example: Agent Creates Google Calendar Event

```python
async def agent_create_calendar_event(event_details: dict):
    """Agent creates calendar event via browser automation."""

    async with BrowserAutomation(
        headless=False,
        user_data_dir="~/.config/google-chrome/Default"
    ) as browser:
        # Navigate to Google Calendar
        await browser.navigate("https://calendar.google.com")

        # Click create button
        await browser.click('button[aria-label="Create"]')

        # Fill event details
        await browser.fill('input[aria-label="Add title"]', event_details['title'])
        await browser.fill('input[aria-label="Date"]', event_details['date'])

        # Save event
        await browser.click('button[aria-label="Save"]')

        print(f"✅ Created event: {event_details['title']}")

# Usage
asyncio.run(agent_create_calendar_event({
    'title': 'Team Meeting',
    'date': '2025-11-20'
}))
```

---

## Headless vs Headed Mode

**Headless (default):**
- No visible browser window
- Faster execution
- Lower resource usage
- Best for automated scripts

**Headed:**
- Visible browser window
- Easier debugging
- Required for some authenticated workflows
- Better for development/testing

```python
# Headless (invisible)
BrowserAutomation(headless=True)

# Headed (visible)
BrowserAutomation(headless=False)
```

---

## Common Patterns

### Waiting for Dynamic Content

```python
# Wait for element to appear
await browser.wait_for_selector("#dynamic-content", timeout=10000)

# Wait for network to be idle
await browser.navigate("https://example.com", wait_until="networkidle")
```

### Error Handling

```python
try:
    await browser.click("button#submit")
except Exception as e:
    print(f"Button not found: {e}")
    # Fallback strategy
    await browser.screenshot("error_state.png")
```

### JavaScript Execution

```python
# Get page data
data = await browser.evaluate("""
    ({
        title: document.title,
        links: Array.from(document.querySelectorAll('a')).map(a => a.href)
    })
""")
```

---

## Security Considerations

1. **Persistent Context**: When using `user_data_dir`, the automation has access to all logged-in accounts. Use carefully.

2. **Credentials**: Never hardcode passwords. Use environment variables or secure credential storage.

3. **Rate Limiting**: Add delays between actions to avoid triggering anti-bot measures:
   ```python
   await asyncio.sleep(1)  # 1 second delay
   ```

4. **Headless Detection**: Some sites detect headless browsers. The module includes anti-detection measures, but always respect site terms of service.

---

## Troubleshooting

**Browser not installed:**
```bash
playwright install chromium
```

**Profile path not found:**
- Check the exact path with `ls ~/.config/google-chrome/`
- Ensure Chrome is closed when using persistent context

**Element not found:**
- Use `browser.screenshot()` to debug
- Increase timeout values
- Check selector with browser DevTools

**Automation detected:**
- Use headed mode instead of headless
- Add realistic delays between actions
- Use persistent context with real browser profile

---

## Next Steps

- Explore the test suite: `test_browser_automation.py`
- Review API examples in this document
- Integrate with NERVA workflows for agent-controlled browsing
- Build custom automation tasks for your use case
