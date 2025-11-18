# nerva/llm/qwen_client.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
import base64
import logging
import aiohttp

from .client_base import BaseLLMClient


logger = logging.getLogger(__name__)


class QwenOllamaClient(BaseLLMClient):
    """
    Qwen3-VL client via Ollama/SOLLOL.

    Uses Ollama's native API endpoints:
    - /api/chat for text chat
    - /api/generate for vision chat
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3-vl:4b",
        timeout: int = 300,  # Increased to 5 minutes for slow vision models
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        # Set explicit timeouts: sock_connect, sock_read, and total
        # qwen3-vl can take 20-60s to respond, so we need very generous timeouts
        self.timeout = aiohttp.ClientTimeout(
            total=timeout,
            connect=30,  # Connection timeout
            sock_connect=30,  # Socket connection timeout
            sock_read=timeout  # Socket read timeout
        )

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Text-only chat via Ollama's native /api/chat endpoint."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **kwargs,
        }

        logger.debug(f"[QwenClient] Sending chat request: {len(messages)} messages")

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
            except aiohttp.ClientError as e:
                logger.error(f"[QwenClient] HTTP error: {e}")
                raise

        # Extract response from Ollama /api/chat schema
        try:
            content = data["message"]["content"]
            return content
        except (KeyError, IndexError) as e:
            logger.error(f"[QwenClient] Unexpected response format: {data}")
            raise ValueError(f"Invalid response structure: {e}")

    async def vision_chat(
        self,
        messages: List[Dict[str, str]],
        images: List[bytes],
        **kwargs: Any,
    ) -> str:
        """
        Vision chat via Ollama's /api/generate endpoint with base64 images.

        Ollama expects 'images' as an array of base64-encoded strings.
        """
        # Encode images to base64
        b64_images = [base64.b64encode(img).decode("utf-8") for img in images]

        # Concatenate all message content into a single prompt (Ollama /api/generate style)
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role}: {content}")
        prompt = "\n".join(prompt_parts)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": b64_images,
            "stream": False,
            **kwargs,
        }

        logger.debug(f"[QwenClient] Sending vision request: {len(images)} images")

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
            except aiohttp.ClientError as e:
                logger.error(f"[QwenClient] HTTP error: {e}")
                raise

        # Extract response from Ollama /api/generate schema
        try:
            response_text = data["response"]
            return response_text
        except KeyError as e:
            logger.error(f"[QwenClient] Unexpected response format: {data}")
            raise ValueError(f"Invalid response structure: {e}")
