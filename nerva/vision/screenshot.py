# nerva/vision/screenshot.py
from __future__ import annotations
from typing import Optional
import io
import logging


logger = logging.getLogger(__name__)

try:
    import mss
    from mss import tools as mss_tools

    MSS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    MSS_AVAILABLE = False

try:
    from PIL import ImageGrab  # type: ignore

    PIL_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    PIL_AVAILABLE = False


def capture_screen() -> Optional[bytes]:
    """
    Capture a screenshot and return as PNG bytes.

    Uses `mss` when available. Falls back to clipboard capture so
    workflows can still obtain an image even on platforms that block
    automated screen grabs (e.g. macOS with missing permissions).

    Returns:
        PNG image bytes, or None if capture fails
    """
    if not MSS_AVAILABLE:
        logger.warning("mss not installed - attempting clipboard capture instead")
        return read_clipboard_image()

    try:
        with mss.mss() as sct:
            # Monitor 1 is a special entry for the virtual bounding box that
            # contains all displays. Prefer physical monitor if present.
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            screenshot = sct.grab(monitor)
            png_bytes = mss_tools.to_png(screenshot.rgb, screenshot.size)
            logger.debug(
                "[Screenshot] Captured %sx%s region at %s",
                screenshot.width,
                screenshot.height,
                monitor.get("left", 0),
            )
            return png_bytes
    except Exception as exc:
        logger.error(f"[Screenshot] Capture failed: {exc}")
        # Fallback to clipboard snapshot
        return read_clipboard_image()


def read_clipboard_image() -> Optional[bytes]:
    """
    Read image from system clipboard if available.

    Uses Pillow's ImageGrab which works on macOS/Windows and X11 (with xclip/xsel).
    Returns:
        Image bytes, or None if no image in clipboard
    """
    if not PIL_AVAILABLE:
        logger.debug("[Screenshot] Pillow not installed; clipboard capture unavailable")
        return None

    try:
        img = ImageGrab.grabclipboard()
        if img is None:
            logger.debug("[Screenshot] No clipboard image detected")
            return None

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        logger.debug("[Screenshot] Clipboard image captured")
        return buffer.getvalue()
    except Exception as exc:
        logger.error(f"[Screenshot] Clipboard capture failed: {exc}")
        return None
