"""Centralized FastAPI dependency injection functions.

Single source of truth for all shared `get_*` factory functions used across
route files via FastAPI `Depends()`. Import these instead of defining local
copies in each router module.
"""

import logging
import os
from typing import Optional

from app.infrastructure.llm.llm_manager import LLMManager
from utils.config import get_config

logger = logging.getLogger(__name__)


def get_llm_manager() -> Optional[LLMManager]:
    """Create an LLM manager, returning None if LLM is unavailable."""
    try:
        config = get_config()
        provider = os.getenv(
            "LLM_PROVIDER",
            getattr(config.llm, "provider", "lmstudio")
            if hasattr(config, "llm")
            else "lmstudio",
        )
        base_url = os.getenv(
            "LLM_BASE_URL",
            getattr(config.llm, "base_url", "http://localhost:1234/v1")
            if hasattr(config, "llm")
            else "http://localhost:1234/v1",
        )
        model = os.getenv(
            "LLM_MODEL",
            getattr(config.llm, "model_name", "qwen/qwen2.5-vl-7b")
            if hasattr(config, "llm")
            else "qwen/qwen2.5-vl-7b",
        )
        api_key = os.getenv(
            "LLM_API_KEY",
            getattr(config.llm, "api_key", "")
            if hasattr(config, "llm")
            else "",
        )
        max_retries = (
            getattr(config.llm, "max_retries", 3)
            if hasattr(config, "llm")
            else 3
        )
        manager = LLMManager(
            provider=provider,
            base_url=base_url,
            default_model=model,
            api_key=api_key,
            max_retries=max_retries,
        )
        if not getattr(manager, "is_available", True):
            logger.warning("LLM manager initialized but provider is unreachable")
            return None
        return manager
    except (ConnectionError, RuntimeError) as e:
        logger.warning("LLM manager not available: %s", e)
        return None
