from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from sollol.client import SOLLOLClient, SOLLOLConfig
import httpx

from .client_base import BaseLLMClient


logger = logging.getLogger(__name__)


class SolLolLLMClient(BaseLLMClient):
    """
    SOLLOL-backed LLM client.

    Routes chat completions through SOLLOL's intelligent router while delegating
    image/vision requests to a fallback client (Qwen/Ollama) because the SOLLOL
    API currently exposes text-only endpoints.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        priority: int = 5,
        vision_client: Optional[BaseLLMClient] = None,
        text_fallback: Optional[BaseLLMClient] = None,
    ) -> None:
        config = SOLLOLConfig(base_url=base_url, default_model=model, default_priority=priority)
        self._client = SOLLOLClient(config)
        self._default_model = model
        self._default_priority = priority
        self._vision_client = vision_client
        self._text_fallback = text_fallback
        logger.info("[SOLLOL] Client initialized (base_url=%s, model=%s)", base_url, model)

    async def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Send chat completion through SOLLOL."""
        if not messages:
            raise ValueError("SOLLOL chat requires at least one message")

        system_prompt = self._extract_system_prompt(messages)
        history, latest_user = self._extract_history(messages)

        if latest_user is None:
            raise ValueError("SOLLOL chat requires a user message")

        model = kwargs.get("model") or self._default_model
        priority = kwargs.get("priority") or self._default_priority

        logger.debug("[SOLLOL] Routing chat request (model=%s, priority=%s)", model, priority)
        try:
            response = await self._client.chat_async(
                message=latest_user,
                model=model,
                priority=priority,
                system_prompt=system_prompt,
                conversation_history=history or None,
            )
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("[SOLLOL] Chat failed (%s) - falling back to local client", exc)
            if self._text_fallback:
                return await self._text_fallback.chat(messages, **kwargs)
            raise

        # Check for error response from SOLLOL
        if isinstance(response, dict) and "error" in response:
            error_msg = response.get("error", "Unknown error")
            logger.warning("[SOLLOL] Error response: %s - falling back to local client", error_msg)
            if self._text_fallback:
                return await self._text_fallback.chat(messages, **kwargs)
            raise ValueError(f"SOLLOL error: {error_msg}")

        try:
            return response["message"]["content"]
        except KeyError as exc:  # pragma: no cover - depends on SOLLOL response schema
            logger.error("[SOLLOL] Unexpected response: %s", response)
            # Fall back to local client if available
            if self._text_fallback:
                logger.warning("[SOLLOL] Invalid response format - falling back to local client")
                return await self._text_fallback.chat(messages, **kwargs)
            raise ValueError("Invalid SOLLOL response payload") from exc

    async def vision_chat(
        self,
        messages: List[Dict[str, str]],
        images: List[bytes],
        **kwargs: Any,
    ) -> str:
        """
        Forward vision chat to fallback client.

        SOLLOL does not expose a multi-modal endpoint yet, so we keep vision
        features functioning by delegating to the injected client.
        """
        if not self._vision_client:
            raise RuntimeError("SOLLOL client has no vision fallback configured")
        return await self._vision_client.vision_chat(messages, images, **kwargs)

    @staticmethod
    def _extract_system_prompt(messages: List[Dict[str, str]]) -> Optional[str]:
        """Return the first system prompt if available."""
        for msg in messages:
            if msg.get("role") == "system":
                return msg.get("content")
        return None

    @staticmethod
    def _extract_history(messages: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], Optional[str]]:
        """
        Split incoming messages into history and the latest user prompt.

        Returns:
            (history_without_latest_user, latest_user_content)
        """
        non_system: List[Dict[str, str]] = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                continue
            non_system.append({"role": role, "content": msg.get("content", "")})

        if not non_system:
            return [], None

        latest_user = None
        for idx in range(len(non_system) - 1, -1, -1):
            if non_system[idx]["role"] == "user":
                latest_user = non_system[idx]["content"]
                history = non_system[:idx]
                break
        else:
            # No trailing user; treat the final message as the user prompt anyway.
            history = non_system[:-1]
            latest_user = non_system[-1]["content"] if non_system else None

        return history, latest_user
