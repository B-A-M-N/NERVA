"""Qwen-VL integration for screenshot analysis and UI understanding."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, Union
from PIL import Image
import io

from nerva.llm.qwen_client import QwenOllamaClient
from nerva.config import NervaConfig

logger = logging.getLogger(__name__)


class QwenVision:
    """
    Vision-language model for screenshot analysis and UI understanding.

    Uses Qwen3-VL via Ollama/SOLLOL for:
    - Screenshot analysis
    - UI element detection
    - Action extraction from visual context
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        config: Optional[NervaConfig] = None,
    ):
        """
        Initialize QwenVision.

        Args:
            base_url: API base URL (defaults to SOLLOL if use_sollol=True, else Ollama)
            model: Qwen-VL model to use (defaults to config.qwen_vision_model)
            timeout: Request timeout in seconds (defaults to config.vision_timeout)
            config: NervaConfig instance (created if not provided)
        """
        if config is None:
            config = NervaConfig()

        # Use SOLLOL for intelligent routing (routes to nodes with the vision model)
        if base_url is None:
            base_url = config.sollol_base_url if config.use_sollol else config.ollama_base_url

        if model is None:
            model = config.qwen_vision_model

        if timeout is None:
            timeout = config.vision_timeout

        self.client = QwenOllamaClient(
            base_url=base_url,
            model=model,
            timeout=timeout,
        )
        self.config = config
        logger.info(f"[QwenVision] Initialized with model: {model} via {base_url}")

    async def analyze_screenshot(
        self,
        image_path: Union[str, Path],
        prompt: str = "Describe what you see in this screenshot in detail.",
    ) -> str:
        """
        Analyze a screenshot and return a description.

        Args:
            image_path: Path to screenshot image
            prompt: Analysis prompt

        Returns:
            Vision model's analysis of the screenshot
        """
        # Load image
        image_bytes = self._load_image(image_path)

        # Analyze with vision model
        messages = [
            {"role": "user", "content": prompt}
        ]

        logger.debug(f"[QwenVision] Analyzing screenshot: {image_path}")
        response = await self.client.vision_chat(
            messages=messages,
            images=[image_bytes],
        )

        return response

    async def extract_ui_elements(
        self,
        image_path: Union[str, Path],
    ) -> str:
        """
        Extract UI elements and their locations from a screenshot.

        Args:
            image_path: Path to screenshot image

        Returns:
            Description of UI elements and their positions
        """
        prompt = """Analyze this screenshot and list all visible UI elements.
For each element, describe:
1. Type (button, link, text field, etc.)
2. Label or text content
3. Approximate position (top-left, center, bottom-right, etc.)
4. State (enabled/disabled, selected/unselected)

Format your response as a structured list."""

        return await self.analyze_screenshot(image_path, prompt)

    async def find_element(
        self,
        image_path: Union[str, Path],
        element_description: str,
    ) -> str:
        """
        Find a specific UI element in a screenshot.

        Args:
            image_path: Path to screenshot image
            element_description: Description of element to find

        Returns:
            Location and details of the element
        """
        prompt = f"""Look for the following UI element in this screenshot:
"{element_description}"

If found, describe:
1. Exact location (coordinates if possible, or relative position)
2. Current state
3. How to interact with it
4. Any relevant context around it

If not found, say "NOT FOUND" and suggest similar elements."""

        return await self.analyze_screenshot(image_path, prompt)

    async def extract_browser_action(
        self,
        image_path: Union[str, Path],
        task: str,
    ) -> str:
        """
        Analyze screenshot and determine next browser action for a task.

        Args:
            image_path: Path to browser screenshot
            task: Task to accomplish (e.g., "Find the search button")

        Returns:
            Recommended action in structured format
        """
        prompt = f"""You are a browser automation assistant. Analyze this screenshot and determine the next action.

TASK: {task}

Provide your response in this exact format:
ACTION: [click|type|scroll|navigate|wait]
TARGET: [description of element or URL]
VALUE: [text to type, or N/A]
REASON: [why this action accomplishes the task]
CONFIDENCE: [high|medium|low]

If the task is already complete, respond:
ACTION: complete
REASON: [what was accomplished]"""

        return await self.analyze_screenshot(image_path, prompt)

    async def verify_action_result(
        self,
        before_image: Union[str, Path],
        after_image: Union[str, Path],
        expected_result: str,
    ) -> str:
        """
        Verify that an action had the expected result by comparing screenshots.

        Args:
            before_image: Screenshot before action
            after_image: Screenshot after action
            expected_result: What should have changed

        Returns:
            Verification result
        """
        # Analyze after image with context
        prompt = f"""Compare this screenshot to the expected result of an action.

EXPECTED RESULT: {expected_result}

Did the expected change occur? Respond with:
VERIFIED: [yes|no|partial]
OBSERVED CHANGES: [what actually changed]
NEXT ACTION: [what to do next, or "task complete"]"""

        return await self.analyze_screenshot(after_image, prompt)

    async def answer_question(
        self,
        image_path: Union[str, Path],
        question: str,
    ) -> str:
        """
        Answer a question about a screenshot (for extracting specific data).

        Args:
            image_path: Path to screenshot image
            question: Question to answer (e.g., "What is the phone number?")

        Returns:
            Textual answer (or NOT_FOUND if unavailable)
        """
        prompt = f"""You are looking at a web page screenshot.
Answer the following question using ONLY visible information:
QUESTION: {question}

If the answer is visible, respond with:
ANSWER: <answer>
CONFIDENCE: <high|medium|low>
EVIDENCE: <brief explanation>

If it is not visible, respond:
ANSWER: NOT_FOUND
CONFIDENCE: low
EVIDENCE: explain why."""

        return await self.analyze_screenshot(image_path, prompt)

    def _load_image(self, image_path: Union[str, Path]) -> bytes:
        """
        Load image file as bytes.

        Args:
            image_path: Path to image file

        Returns:
            Image as bytes
        """
        path = Path(image_path)

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        # Load with PIL to ensure format compatibility
        img = Image.open(path)

        # Convert to RGB if necessary (remove alpha channel)
        if img.mode in ("RGBA", "LA", "P"):
            # Create white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
