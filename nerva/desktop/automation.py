"""Full desktop automation helpers (mouse/keyboard)."""
from __future__ import annotations

import logging
import time
from typing import Optional

try:
    import pyautogui

    PYAUTOGUI_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    pyautogui = None
    PYAUTOGUI_AVAILABLE = False


logger = logging.getLogger(__name__)


class DesktopAutomation:
    """
    Minimal wrapper around pyautogui for native desktop control.

    Methods are guarded so that the module still loads even if pyautogui isn't installed.
    """

    def __init__(self, fail_silent: bool = False) -> None:
        self.fail_silent = fail_silent
        if not PYAUTOGUI_AVAILABLE:
            logger.warning("pyautogui not installed; DesktopAutomation will no-op.")

    def _ensure_available(self) -> bool:
        if not PYAUTOGUI_AVAILABLE:
            if not self.fail_silent:
                raise RuntimeError("pyautogui is required for desktop automation (pip install pyautogui).")
            return False
        return True

    def move(self, x: int, y: int, duration: float = 0.2) -> None:
        if not self._ensure_available():
            return
        pyautogui.moveTo(x, y, duration=duration)

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> None:
        if not self._ensure_available():
            return
        pyautogui.click(x=x, y=y, button=button)

    def type_text(self, text: str, interval: float = 0.05) -> None:
        if not self._ensure_available():
            return
        pyautogui.typewrite(text, interval=interval)

    def hotkey(self, *keys: str) -> None:
        if not self._ensure_available():
            return
        pyautogui.hotkey(*keys)

    def screenshot(self, path: str) -> None:
        if not self._ensure_available():
            return
        image = pyautogui.screenshot()
        image.save(path)

    def wait(self, seconds: float) -> None:
        time.sleep(seconds)
