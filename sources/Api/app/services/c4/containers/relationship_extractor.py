"""Relationship extraction from environment variables and config files."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from .utils import (
    flatten_dict,
    infer_direction_from_env_name,
    infer_protocol_from_port,
    parse_connection_string,
)

logger = logging.getLogger(__name__)

# Env-var names that carry connection info (heuristic: must contain one of these)
_CONNECTION_KEY_PATTERNS = re.compile(
    r"(URL|URI|HOST|ADDR|ADDRESS|ENDPOINT|DSN|CONNECTION|CONN|SERVER|BROKER|"
    r"TOPIC|QUEUE|EXCHANGE|BOOTSTRAP|DATASOURCE|DATABASE|DB_HOST)",
    re.IGNORECASE,
)

# Noise: env vars that clearly don't carry external service references
_NOISE_KEY_PATTERNS = re.compile(
    r"^(HOME|PATH|USER|PWD|SHELL|TERM|LANG|LC_|TZ|HOSTNAME|UID|GID|"
    r"LOG_LEVEL|LOG_FORMAT|DEBUG|VERBOSE|ENV|ENVIRONMENT|STAGE|REGION|"
    r"SECRET|PASSWORD|PASSWD|TOKEN|KEY|CERT|CA_BUNDLE)\b",
    re.IGNORECASE,
)


def _is_noise(key: str, value: str) -> bool:
    """True when a key/value pair is unlikely to reference an external service."""
    if _NOISE_KEY_PATTERNS.match(key):
        return True
    # Values that are clearly local/no-op
    if not value or value.strip() in ("", "true", "false", "0", "1", "null", "none"):
        return True
    return False


def _extract_topic_or_queue(var_name: str) -> dict:
    """Return metadata dict with topic/queue/exchange captured from var name."""
    meta: dict = {}
    upper = var_name.upper()
    if "TOPIC" in upper:
        meta["topic"] = var_name
    if "QUEUE" in upper:
        meta["queue"] = var_name
    if "EXCHANGE" in upper:
        meta["exchange"] = var_name
    return meta


class EnvVarRelationshipExtractor:
    """Extract inter-container relationships from environment variable lists/dicts.

    Works with:
    - K8s-style env lists: [{"name": "DB_URL", "value": "postgresql://db:5432/app"}]
    - Compose-style env dicts: {"DB_URL": "postgresql://db:5432/app"}
    """

    def __init__(self, source_container_name: str, source_label: str = "env"):
        self.source = source_container_name
        self.source_label = source_label

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, env_vars: list[dict]) -> list[dict]:
        """Process K8s-style env list ([{"name": ..., "value": ...}])."""
        pairs: list[tuple[str, str]] = []
        for item in env_vars or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or ""
            value = str(item.get("value") or "")
            pairs.append((name, value))
        return self._process_pairs(pairs)

    def extract_from_dict(self, env_dict: dict) -> list[dict]:
        """Process compose-style env dict ({KEY: VALUE})."""
        pairs: list[tuple[str, str]] = [
            (str(k), str(v) if v is not None else "")
            for k, v in (env_dict or {}).items()
        ]
        return self._process_pairs(pairs)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _process_pairs(self, pairs: list[tuple[str, str]]) -> list[dict]:
        relationships: list[dict] = []
        for key, value in pairs:
            rel = self._pair_to_relationship(key, value)
            if rel is not None:
                relationships.append(rel)
        return relationships

    def _pair_to_relationship(self, key: str, value: str) -> Optional[dict]:
        if _is_noise(key, value):
            return None

        parsed = parse_connection_string(value)

        if parsed is None:
            # Fallback: check if value contains a well-known port pattern (host:port)
            parsed = self._fallback_host_port(key, value)

        if parsed is None:
            return None

        protocol = parsed.get("protocol") or "TCP"
        host = parsed.get("host") or ""
        port = parsed.get("port")

        # If no protocol inferred from scheme, try port-based inference
        if protocol in ("TCP",) and port:
            protocol = infer_protocol_from_port(str(port))

        direction = infer_direction_from_env_name(key)
        metadata = _extract_topic_or_queue(key)
        if parsed.get("database"):
            metadata["database"] = parsed["database"]

        return {
            "from": self.source,
            "to": host,
            "type": direction,
            "protocol": protocol,
            "port": port,
            "source": self.source_label,
            "description": f"{self.source} uses {host} via {key}",
            "_unresolved": True,
            "metadata": metadata,
        }

    @staticmethod
    def _fallback_host_port(key: str, value: str) -> Optional[dict]:
        """Try to extract host:port from value when no URL scheme is present."""
        if not _CONNECTION_KEY_PATTERNS.search(key):
            return None
        # Match host:port or just a hostname with a known port mapping
        m = re.search(r"\b([a-zA-Z][a-zA-Z0-9._-]*):(\d{2,5})\b", value)
        if m:
            return {"protocol": "TCP", "host": m.group(1), "port": m.group(2), "database": None}
        return None


class ConfigRelationshipExtractor:
    """Extract relationships from config files inside a service directory.

    Supports:
    - appsettings.json / appsettings.*.json  (.NET)
    - application.properties / application.yml / application-*.yml  (Spring Boot)
    - .env / .env.*
    - config.json / config.yaml / config.yml  (generic)
    """

    def __init__(self, source_container_name: str):
        self.source = source_container_name
        self._env_extractor = EnvVarRelationshipExtractor(source_container_name, source_label="config")

    def extract_from_directory(self, project_dir: Path) -> list[dict]:
        relationships: list[dict] = []
        project_dir = Path(project_dir)

        for config_file in self._iter_config_files(project_dir):
            try:
                rels = self._extract_from_file(config_file)
                relationships.extend(rels)
            except Exception as e:
                logger.debug("ConfigRelationshipExtractor: failed to parse %s: %s", config_file, e)

        # Deduplicate: env-specific config variants (e.g., appsettings.json +
        # appsettings.Development.json) often contain the same connection strings.
        seen: set[tuple] = set()
        unique: list[dict] = []
        for r in relationships:
            key = (r.get("to"), r.get("type"), r.get("protocol"))
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _iter_config_files(self, project_dir: Path):
        patterns = [
            "appsettings.json",
            "appsettings.*.json",
            "application.properties",
            "application.yml",
            "application.yaml",
            "application-*.yml",
            "application-*.yaml",
            ".env",
            ".env.*",
            "config.json",
            "config.yaml",
            "config.yml",
        ]
        for pattern in patterns:
            yield from project_dir.glob(pattern)

    def _extract_from_file(self, path: Path) -> list[dict]:
        name = path.name
        suffix = path.suffix.lower()

        if suffix == ".json":
            return self._from_json(path)
        if suffix in (".yml", ".yaml"):
            return self._from_yaml(path)
        if suffix == ".properties":
            return self._from_properties(path)
        if name.startswith(".env"):
            return self._from_dotenv(path)
        return []

    def _from_json(self, path: Path) -> list[dict]:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        if not isinstance(data, dict):
            return []
        pairs = flatten_dict(data)
        env_dict = {k: str(v) for k, v in pairs if v is not None}
        return self._env_extractor.extract_from_dict(env_dict)

    def _from_yaml(self, path: Path) -> list[dict]:
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="ignore"))
        if not isinstance(data, dict):
            return []
        pairs = flatten_dict(data)
        env_dict = {k: str(v) for k, v in pairs if v is not None}
        return self._env_extractor.extract_from_dict(env_dict)

    def _from_properties(self, path: Path) -> list[dict]:
        env_dict: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env_dict[key.strip()] = value.strip()
        return self._env_extractor.extract_from_dict(env_dict)

    def _from_dotenv(self, path: Path) -> list[dict]:
        env_dict: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env_dict[key] = value
        return self._env_extractor.extract_from_dict(env_dict)
