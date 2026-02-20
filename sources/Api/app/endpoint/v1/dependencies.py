"""Centralized FastAPI dependency injection functions.

Single source of truth for all shared `get_*` factory functions used across
route files via FastAPI `Depends()`. Import these instead of defining local
copies in each router module.
"""

import logging
import os
from typing import Optional

from app.infrastructure.llm.llm_manager import LLMManager
from app.infrastructure.storage.metadata_store import (
    PostgreSQLMetadataStore as MetadataStore,
)
from app.services.c4.context.level1_context_service import Level1ContextService
from utils.config import get_config

logger = logging.getLogger(__name__)

_level1_context_service_singleton: Optional[Level1ContextService] = None


def get_llm_manager() -> Optional[LLMManager]:
    """Create an LLM manager, returning None if LLM is unavailable."""
    try:
        config = get_config()
        base_url = os.getenv(
            "LMSTUDIO_BASE_URL",
            getattr(config.lmstudio, "base_url", "http://localhost:1234/v1")
            if hasattr(config, "lmstudio")
            else "http://localhost:1234/v1",
        )
        model = os.getenv(
            "LMSTUDIO_MODEL_NAME",
            getattr(config.lmstudio, "model_name", "qwen/qwen2.5-vl-7b")
            if hasattr(config, "lmstudio")
            else "qwen/qwen2.5-vl-7b",
        )
        max_retries = (
            getattr(config.lmstudio, "max_retries", 3)
            if hasattr(config, "lmstudio")
            else 3
        )
        return LLMManager(
            lmstudio_url=base_url,
            default_model=model,
            max_retries=max_retries,
        )
    except (ConnectionError, RuntimeError) as e:
        logger.warning("LLM manager not available: %s", e)
        return None


def get_metadata_store() -> MetadataStore:
    """Create a metadata store for the current request."""
    config = get_config()
    return MetadataStore(config=config)


def get_level1_context_service() -> Level1ContextService:
    """Return singleton context service to preserve in-memory state in dev/tests."""
    global _level1_context_service_singleton
    if _level1_context_service_singleton is None:
        _level1_context_service_singleton = Level1ContextService()
    return _level1_context_service_singleton


def reset_level1_context_service_for_tests() -> None:
    """Reset singleton for test isolation."""
    global _level1_context_service_singleton
    _level1_context_service_singleton = None
