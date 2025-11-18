from __future__ import annotations

from typing import Optional, List, Set
import logging

import httpx
from sollol import discover_ollama_nodes

from ..config import NervaConfig
from .client_base import BaseLLMClient
from .mock_client import MockLLMClient
from .qwen_client import QwenOllamaClient
from .sollol_client import SolLolLLMClient


logger = logging.getLogger(__name__)


def create_llm_client(config: NervaConfig, *, use_mock: bool = False) -> BaseLLMClient:
    """
    Construct the appropriate LLM client for the current configuration.

    Args:
        config: Global NERVA configuration
        use_mock: Force mock client (testing/demo)
    """
    if use_mock:
        return MockLLMClient()

    if config.use_sollol:
        detected_base = _detect_sollol_gateway(config)
        logger.info(
            "[LLMFactory] Using SOLLOL router (%s, model=%s)",
            detected_base,
            config.sollol_model,
        )
        fallback = QwenOllamaClient(
            base_url=config.ollama_base_url,
            model=config.qwen_model,
        )
        return SolLolLLMClient(
            base_url=detected_base,
            model=config.sollol_model,
            priority=config.sollol_priority,
            vision_client=fallback,
            text_fallback=fallback,
        )

    logger.info(
        "[LLMFactory] Using direct Ollama connection (%s, model=%s)",
        config.ollama_base_url,
        config.qwen_model,
    )
    return QwenOllamaClient(
        base_url=config.ollama_base_url,
        model=config.qwen_model,
    )


def _detect_sollol_gateway(config: NervaConfig) -> str:
    """
    Heuristically detect the reachable SOLLOL gateway without requiring env vars.

    Tries the configured URL first, then localhost variants, followed by
    discovered Ollama hosts (assuming SOLLOL gateway typically runs alongside).
    """
    preferred = _normalize_url(config.sollol_base_url)
    if _probe_gateway(preferred):
        return preferred

    logger.warning(
        "[LLMFactory] Unable to reach SOLLOL gateway at %s - attempting auto-discovery",
        preferred,
    )

    candidate_hosts: Set[str] = {
        "localhost",
        "127.0.0.1",
        "host.docker.internal",
    }

    # Include hosts from SOLLOL discovery (ignoring localhost duplicates)
    try:
        for node in discover_ollama_nodes(exclude_localhost=False):
            candidate_hosts.add(node.get("host", "").strip())
    except Exception as exc:  # pragma: no cover - discovery edge cases
        logger.debug("SOLLOL discovery failed: %s", exc)

    ports = {8000, 23000}
    candidates: List[str] = []

    for host in candidate_hosts:
        if not host:
            continue
        for port in ports:
            url = f"http://{host}:{port}"
            candidates.append(url)

    # Deduplicate while preserving order and skip the preferred value already tested
    seen = {preferred}
    for url in candidates:
        normalized = _normalize_url(url)
        if normalized in seen:
            continue
        seen.add(normalized)
        if _probe_gateway(normalized):
            logger.info("[LLMFactory] Detected SOLLOL gateway at %s", normalized)
            return normalized

    logger.warning(
        "[LLMFactory] Falling back to %s (gateway unreachable) - local Ollama will be used when needed",
        preferred,
    )
    return preferred


def _probe_gateway(base_url: str, timeout: float = 0.8) -> bool:
    """Return True if /api/health responds successfully."""
    health_url = f"{base_url.rstrip('/')}/api/health"
    try:
        response = httpx.get(health_url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("status"):
            return True
    except Exception:
        return False
    return False


def _normalize_url(url: str) -> str:
    """Ensure consistent scheme/host casing and strip trailing slash."""
    normalized = (url or "").strip()
    if not normalized:
        normalized = "http://localhost:8000"
    if not normalized.startswith("http"):
        normalized = f"http://{normalized}"
    return normalized.rstrip("/")
