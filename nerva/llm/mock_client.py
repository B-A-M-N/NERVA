# nerva/llm/mock_client.py
"""
Mock LLM client for testing when Ollama/SOLLOL is not running.
"""
from __future__ import annotations
from typing import Any, Dict, List
import logging

from .client_base import BaseLLMClient


logger = logging.getLogger(__name__)


class MockLLMClient(BaseLLMClient):
    """
    Mock LLM client that returns canned responses.
    Useful for testing the TUI without requiring Ollama/SOLLOL.
    """

    def __init__(self) -> None:
        logger.warning("[MockLLM] Using mock LLM client - responses will be simulated")

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Return a mock chat response."""
        user_msg = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")

        logger.info(f"[MockLLM] Mock chat request: {user_msg[:50]}...")

        # Generate mock response based on keywords
        lower = user_msg.lower()
        if "nerva" in lower:
            return "NERVA is a local cognitive exoskeleton for AI infrastructure engineers. It uses DAG-based workflows to provide screen understanding, voice commands, daily ops, and repo-aware assistance."
        elif "dag" in lower or "workflow" in lower:
            return "The DAG execution engine runs workflows as directed acyclic graphs. Each node is an async function that reads/writes to a shared RunContext. This ensures predictable, composable execution."
        elif "sollol" in lower:
            return "SOLLOL integration is pending. You'll need to create a SolLolClient adapter in llm/sollol_client.py to wire NERVA into your LLM routing layer."
        elif "hydra" in lower:
            return "HydraContext integration is stubbed in hydra_adapter/context_builder.py. Implement build_context_for_repo() to get structured code understanding."
        else:
            return f"[Mock Response] I received: '{user_msg[:100]}'. Note: This is a mock LLM client. Start Ollama/SOLLOL for real responses."

    async def vision_chat(
        self,
        messages: List[Dict[str, str]],
        images: List[bytes],
        **kwargs: Any,
    ) -> str:
        """Return a mock vision response."""
        logger.info(f"[MockLLM] Mock vision chat request with {len(images)} image(s)")

        return """[Mock Vision Response]
{
  "repo": "NERVA",
  "file": "nerva/console.py",
  "error_summary": "No errors visible",
  "intent_guess": "Testing screen understanding workflow",
  "next_actions": [
    "Implement real screenshot capture in vision/screenshot.py",
    "Wire Qwen3-VL for actual analysis"
  ]
}"""
