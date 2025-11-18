# nerva/llm/client_base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseLLMClient(ABC):
    """
    Abstract interface for LLM clients.
    Supports both text-only and vision-capable models.
    """

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """
        Standard chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Model-specific parameters (temperature, max_tokens, etc.)

        Returns:
            String response from the model
        """
        ...

    @abstractmethod
    async def vision_chat(
        self,
        messages: List[Dict[str, str]],
        images: List[bytes],
        **kwargs: Any,
    ) -> str:
        """
        Chat completion with image inputs.

        Args:
            messages: List of message dicts with 'role' and 'content'
            images: List of image bytes (PNG, JPEG, etc.)
            **kwargs: Model-specific parameters

        Returns:
            String response from the model
        """
        ...
