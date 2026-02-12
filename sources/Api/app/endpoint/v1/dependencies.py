"""Centralized FastAPI dependency injection functions.

Single source of truth for all shared `get_*` factory functions used across
route files via FastAPI `Depends()`. Import these instead of defining local
copies in each router module.
"""

import logging
import os
from typing import Optional

from app.infrastructure.graph.neo4j_manager import Neo4jGraphManager
from app.infrastructure.llm.llm_manager import LLMManager
from app.infrastructure.storage.metadata_store import (
    PostgreSQLMetadataStore as MetadataStore,
)
from utils.config import get_config

logger = logging.getLogger(__name__)


def get_neo4j_manager() -> Neo4jGraphManager:
    """Create and connect a Neo4j manager for the current request."""
    config = get_config()
    manager = Neo4jGraphManager(
        uri=config.neo4j.uri,
        username=config.neo4j.username,
        password=config.neo4j.password,
        database=config.neo4j.database,
        encrypted=config.neo4j.encrypted,
        max_connection_pool_size=getattr(config.neo4j, "max_connection_pool_size", 50),
        connection_timeout=getattr(config.neo4j, "connection_timeout", 30),
    )
    manager.connect()
    return manager


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
