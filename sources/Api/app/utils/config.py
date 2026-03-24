"""Compatibility shim for configuration loading.

This file provides get_config() under the `app.utils.config` module path by
re-using the existing configuration logic. It adjusts the relative path so the
same config.yaml (mounted to /app/config.yaml) is used when running inside the
API container where the package root is `/app/app`.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml


class ConfigNamespace(SimpleNamespace):
    def dict(self) -> dict[str, Any]:
        return _to_dict(self)


def _to_namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return ConfigNamespace(**{k: _to_namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_to_namespace(v) for v in value]
    return value


def _to_dict(value: Any) -> Any:
    if isinstance(value, ConfigNamespace):
        return {k: _to_dict(v) for k, v in value.__dict__.items()}
    if isinstance(value, list):
        return [_to_dict(v) for v in value]
    return value


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for key, val in updates.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], val)
        else:
            base[key] = val
    return base


_CONFIG: ConfigNamespace | None = None


def get_config() -> ConfigNamespace:
    """Load configuration from config.yaml with environment overrides.

    This shim locates config.yaml at the repository root (two levels up from
    this file) which maps to /app/config.yaml inside the container.
    """
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    defaults: dict[str, Any] = {
        "environment": "development",
        "debug": True,
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "knowledgeforge",
            "username": "knowledgeforge",
            "password": "",
        },
        "neo4j": {
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "",
            "database": "neo4j",
            "encrypted": False,
            "max_connection_pool_size": 50,
            "connection_timeout": 30,
        },
        "lmstudio": {
            "base_url": "http://localhost:1234/v1",
            "model_name": "local-model",
            "max_retries": 3,
            "use_embeddings": False,
        },
        "llm": {
            "provider": "lmstudio",
            "base_url": "http://localhost:1234/v1",
            "model_name": "local-model",
            "api_key": "",
            "max_retries": 3,
            "use_embeddings": False,
        },
        "extraction": {
            "confidence_threshold": 0.7,
            "relationship_threshold": 0.6,
            "max_entities_per_column": 100,
        },
        "metadata_storage": {
            "cache_enabled": True,
        },
        "integrations": {
            "pagerduty": {
                "base_url": "https://api.pagerduty.com",
                "api_key": "",
            },
            "jira": {
                "base_url": "",
                "api_token": "",
                "user_email": "",
            },
            "aws_cost_explorer": {
                "enabled": False,
                "region": "us-east-1",
            },
        },
    }

    # Go up two levels to reach the mounted /app where config.yaml resides
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    data: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
            if isinstance(loaded, dict):
                data = loaded

    merged = _deep_merge(defaults, data)

    neo4j = merged.get("neo4j", {})
    neo4j["password"] = os.getenv("NEO4J_PASSWORD") or os.getenv("KF_NEO4J__PASSWORD") or neo4j.get("password", "")
    neo4j["uri"] = os.getenv("NEO4J_URI") or os.getenv("KF_NEO4J__URI") or neo4j.get("uri", "")
    neo4j["username"] = os.getenv("NEO4J_USERNAME") or os.getenv("KF_NEO4J__USERNAME") or neo4j.get("username", "")
    encrypted_env = os.getenv("NEO4J_ENCRYPTED") or os.getenv("KF_NEO4J__ENCRYPTED")
    if encrypted_env is not None:
        neo4j["encrypted"] = encrypted_env.lower() in ("true", "1", "yes")
    merged["neo4j"] = neo4j

    database = merged.get("database", {})
    database["password"] = os.getenv("POSTGRES_PASSWORD", database.get("password", ""))
    database["host"] = os.getenv("POSTGRES_HOST", database.get("host", ""))
    database["username"] = os.getenv("POSTGRES_USERNAME", database.get("username", ""))
    merged["database"] = database

    lmstudio = merged.get("lmstudio", {})
    lmstudio["base_url"] = os.getenv("LMSTUDIO_BASE_URL", lmstudio.get("base_url", ""))
    lmstudio["model_name"] = os.getenv("LMSTUDIO_MODEL", lmstudio.get("model_name", ""))
    merged["lmstudio"] = lmstudio

    llm = merged.get("llm", {})
    llm["provider"] = os.getenv("LLM_PROVIDER", llm.get("provider", "lmstudio"))
    llm["base_url"] = os.getenv("LLM_BASE_URL", llm.get("base_url", "http://localhost:1234/v1"))
    llm["model_name"] = os.getenv("LLM_MODEL", llm.get("model_name", "local-model"))
    llm["api_key"] = os.getenv("LLM_API_KEY", llm.get("api_key", ""))
    merged["llm"] = llm

    _CONFIG = _to_namespace(merged)
    assert _CONFIG is not None
    return _CONFIG
