# Vision-Browser Agent Implementation

## Phase 1: Core Foundation ✅ COMPLETE

### What We Built

1. **Vision Integration** (`nerva/vision/qwen_vision.py`)
   - QwenVision class for screenshot analysis
   - Uses qwen3-vl:4b via Ollama
   - Methods:
     - `analyze_screenshot()` - General screenshot description
     - `extract_ui_elements()` - Identify buttons, fields, links
     - `find_element()` - Locate specific UI elements
     - `extract_browser_action()` - Determine next action for a task
     - `verify_action_result()` - Compare before/after screenshots

2. **VisionActionAgent** (`nerva/agents/vision_action_agent.py`)
   - Autonomous vision → reasoning → action loop
   - Takes a task description (e.g., "Search for Python tutorials on Google")
   - Executes:
     1. Screenshot current browser state
     2. Vision model analyzes and determines next action
     3. Parses action (click, type, scroll, navigate, wait)
     4. Executes action via Playwright
     5. Repeats until task complete
   - Configurable max_steps (default: 20)
   - Optional action verification

3. **Browser Automation** (`nerva/tools/browser_automation.py`)
   - Already existed - Playwright-based browser control
   - Supports persistent contexts (stay logged in)
   - Non-headless mode for watching agent work

### Test Results

Vision model successfully:
- Analyzed test UI screenshot
- Identified all elements (blue button, gray input field, green submit button)
- Described layout and positioning

**Response time:** ~20-30 seconds per vision analysis (qwen3-vl:4b)

### Usage Example

```python
from nerva.agents.vision_action_agent import VisionActionAgent

# Create agent
agent = VisionActionAgent(headless=False, max_steps=10)

# Execute task
result = await agent.execute_task(
    task="Search for 'Python asyncio tutorial' on Google",
    starting_url="https://google.com"
)

# Result contains:
# - status: "success" or "incomplete"
# - reason: what happened
# - steps: number of actions taken
# - history: full action history with screenshots
```

### Architecture

```
Task → VisionActionAgent → Loop:
                             1. Screenshot (Playwright)
                             2. Vision Analysis (Qwen3-VL)
                             3. Action Parsing
                             4. Action Execution (Playwright)
                             5. Verify (optional)
                             → Complete or Repeat
```

### Supported Actions

- **click**: Click element by description
- **type**: Type text into focused element
- **scroll**: Scroll page up/down
- **navigate**: Go to URL
- **wait**: Pause for duration
- **complete**: Task finished

### Files Created

```
nerva/
├── vision/
│   ├── __init__.py
│   └── qwen_vision.py          # Vision-language model interface
├── agents/
│   ├── __init__.py
│   └── vision_action_agent.py  # Vision → Action loop
└── llm/
    └── qwen_client.py          # Already existed (Ollama client)

test_vision_agent.py            # Full agent test with Google search
test_vision_quick.py            # Quick vision model test
```

## Phase 2: Google Services ✅ COMPLETE

### Google Workspace Skills (`nerva/agents/google_skills.py`)

1. **Shared Base (`GoogleSkillBase`)**
   - Wraps `BrowserAutomation` (persistent Chrome profile friendly)
   - Handles screenshots + vision prompts (structured JSON extraction)
   - Async context manager so each skill can reuse authenticated sessions
   - Forces QwenVision to use **qwen3-vl:4b** for consistent reasoning speed/accuracy

2. **Google Calendar**
   - `summarize_day(day="today", limit=6)` → opens Google Calendar Day view, uses Qwen-VL to output JSON agenda
   - `create_event(CalendarEvent)` → fills the event editor (title/date/time/location/description) and saves

3. **Gmail**
   - `summarize_inbox(unread_only=True, limit=5)` → captures inbox + extracts sender/subject/snippet/time in JSON
   - `send_email(EmailDraft)` → clicks Compose, fills recipients, subject, body, then sends (optional CC/BCC)

4. **Google Drive**
   - `list_recent_files(limit=8)` → screenshots My Drive and returns vision-derived file metadata
   - `search(query)` → performs Drive search, waits for results, and summarizes top hits via vision

### Manual Harness (`test_google_skills.py`)

Command-line runner for quick validation (expects logged-in Chrome profile):

```bash
# Summarize calendar & optionally create an event
python test_google_skills.py calendar --profile ~/.config/google-chrome/Default --create --title "Vision Sync" --date 2025-01-20 --start "10:00 AM" --end "11:00 AM"

# List unread Gmail messages and send a test email
python test_google_skills.py gmail --profile ~/.config/google-chrome/Default --send --to you@example.com --subject "Hello" --body "Sent from NERVA"

# List Drive files and search for "roadmap"
python test_google_skills.py drive --profile ~/.config/google-chrome/Default --query roadmap
```

Each command prints structured dictionaries containing the raw vision response, parsed JSON, and screenshot path for debugging.

---

## Phase 3: Unified Agent Loop ✅ COMPLETE

`nerva/agents/task_dispatcher.py` wires everything together:

1. **TaskDispatcher / TaskContext / TaskResult**
   - Heuristic + LLM routing between Calendar, Gmail, Drive, and the VisionActionAgent
   - Every command/result is persisted to the MemoryStore for future recall

2. **VoiceControlAgent**
   - Wake-word ("NERVA") listener using Whisper ASR + optional Kokoro TTS feedback
   - Routes spoken commands through TaskDispatcher and SafetyManager

3. **Sample Usage**

```python
from nerva.agents import (
    TaskDispatcher, TaskContext, VoiceControlAgent,
    VisionActionAgent, GoogleCalendarSkill, GmailSkill, GoogleDriveSkill,
)
from nerva.llm.qwen_client import QwenOllamaClient
from nerva.memory.store import MemoryStore

llm = QwenOllamaClient(model="qwen3:4b")
memory = MemoryStore()
vision = VisionActionAgent()
calendar = GoogleCalendarSkill(user_data_dir="~/.config/google-chrome/Default")
gmail = GmailSkill(user_data_dir="~/.config/google-chrome/Default")
drive = GoogleDriveSkill(user_data_dir="~/.config/google-chrome/Default")

dispatcher = TaskDispatcher(
    llm=llm,
    memory=memory,
    vision_agent=vision,
    calendar_skill=calendar,
    gmail_skill=gmail,
    drive_skill=drive,
)

result = asyncio.run(dispatcher.dispatch("Check tomorrow's meetings"))
print(result.summary)

# Hands-free mode
voice = VoiceControlAgent(dispatcher, wake_word="nerva")
asyncio.run(voice.run())
```

**New in this phase**

- VisionActionAgent now returns an `"answer"` field by running the final screenshot through a Qwen-VL question-answer prompt, so tasks like “Find the phone number for Target in Tinley Park” capture the result instead of just clicking links.
- The dispatcher asks clarifying questions (via LLM + user prompt) when a request is ambiguous before it routes to a skill.

---

## Phase 4: Supervisor & Safety ✅ COMPLETE

Also part of `nerva/agents/task_dispatcher.py`:

1. **SafetyManager** – detects risky commands ("delete", "send", etc.) and prompts for confirmation.
2. **HotkeyManager + `create_default_hotkeys`** – registers the numpad asterisk (`*`) macro so a single press runs all three summaries (calendar, Gmail, Drive) in sequence. You can still add custom handlers for other shortcuts.
3. **AmbientMonitor** – background task runner (e.g., summarize calendar every 30 minutes) feeding results back into memory.

```python
hotkeys = create_default_hotkeys(dispatcher)  # '*' macro now active
asyncio.create_task(hotkeys.start())

ambient = AmbientMonitor(dispatcher, interval=1800, task="Check my Gmail inbox")
asyncio.create_task(ambient.start())
```

## Current Status

- ✅ Phase 1 Complete
- ✅ Phase 2 Complete
- ✅ Phase 3 Complete
- ✅ Phase 4 Complete
- Voice control: Implemented via `VoiceControlAgent` (wake word “NERVA”)
- Safety/ambient layers: SafetyManager + HotkeyManager + AmbientMonitor
- Vision model: qwen3-vl:4b (local via Ollama)

## Performance Notes

- Vision analysis: 20-30 seconds per screenshot
- For faster iteration, could use qwen3-vl:8b (better accuracy) or smaller models (faster but less accurate)
- Browser automation: Near-instant
- Overall task completion: Depends on task complexity, typically 2-5 minutes for simple tasks

## Integration with NERVA

The VisionActionAgent can be integrated into NERVA's workflow system:

1. User says: "Alexa, check my calendar"
2. Wake word detector activates
3. Whisper transcribes command
4. LLM understands intent
5. VisionActionAgent opens browser and navigates to Google Calendar
6. Vision model reads calendar
7. TTS speaks upcoming events

This creates a complete hands-free assistant with visual understanding!
