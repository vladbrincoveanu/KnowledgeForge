"""Inter-service communication detector.

Scans service source code for patterns that indicate runtime dependencies
on other services.  Results populate Service.inter_service_comms.

Each discovered comm entry looks like:
  {"target": "<hostname-or-service-name>", "protocol": "<HTTP|gRPC|AMQP|…>", "direction": "OUTBOUND"}

Detection sources:
  1. HTTP client calls (requests, httpx, axios, fetch, urllib)
  2. gRPC stubs / channel creation
  3. Message queue producers/consumers (Kafka, RabbitMQ, SQS, Redis)
  4. Service mesh / environment-variable URLs (SERVICE_URL, *_HOST env refs in code)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from app.utils.fs_utils import limited_rglob

logger = logging.getLogger(__name__)

_READ_LIMIT = 10_000  # bytes per file

# ── HTTP client patterns ──────────────────────────────────────────────────────
# We capture the URL/hostname argument.
_HTTP_PATTERNS: list[tuple[str, str]] = [
    # requests / httpx
    (r'requests\.\w+\(\s*["\']([^"\']+)["\']', "HTTP"),
    (r'httpx\.\w+\(\s*["\']([^"\']+)["\']', "HTTP"),
    # aiohttp
    (r'session\.\w+\(\s*["\']([^"\']+)["\']', "HTTP"),
    # urllib
    (r'urllib\.request\.urlopen\(\s*["\']([^"\']+)["\']', "HTTP"),
    # JavaScript/TypeScript fetch / axios
    (r'fetch\(\s*["\']([^"\']+)["\']', "HTTP"),
    (r'axios\.\w+\(\s*["\']([^"\']+)["\']', "HTTP"),
    (r'axios\(\s*\{[^}]*url\s*:\s*["\']([^"\']+)["\']', "HTTP"),
    # Go http client
    (r'http\.Get\(\s*["\']([^"\']+)["\']', "HTTP"),
    (r'http\.Post\(\s*["\']([^"\']+)["\']', "HTTP"),
    # Java RestTemplate / WebClient
    (r'restTemplate\.\w+\(\s*["\']([^"\']+)["\']', "HTTP"),
    (r'webClient\.\w+\(\)[^"\']*["\']([^"\']+)["\']', "HTTP"),
]

# ── gRPC patterns ─────────────────────────────────────────────────────────────
_GRPC_PATTERNS: list[tuple[str, str]] = [
    (r'grpc\.insecure_channel\(\s*["\']([^"\']+)["\']', "gRPC"),
    (r'grpc\.secure_channel\(\s*["\']([^"\']+)["\']', "gRPC"),
    (r'grpc\.dial\(\s*["\']([^"\']+)["\']', "gRPC"),  # Go
]

# ── Queue / event-bus patterns ────────────────────────────────────────────────
_QUEUE_PATTERNS: list[tuple[str, str]] = [
    # Kafka
    (r'KafkaProducer\([^)]*bootstrap_servers\s*=\s*["\']([^"\']+)["\']', "Kafka"),
    (r'KafkaConsumer\([^)]*bootstrap_servers\s*=\s*["\']([^"\']+)["\']', "Kafka"),
    (r'KafkaProducer\([^)]*bootstrap_servers\s*=\s*\[?\s*["\']([^"\']+)["\']', "Kafka"),
    # RabbitMQ / AMQP
    (r'pika\.ConnectionParameters\(\s*["\']([^"\']+)["\']', "AMQP"),
    (r'amqp://[^@]+@([^/\s"\']+)', "AMQP"),
    # AWS SQS / SNS
    (r'sqs\.send_message\([^)]*QueueUrl\s*=\s*["\']([^"\']+)["\']', "SQS"),
    (r'sns\.publish\([^)]*TopicArn\s*=\s*["\']([^"\']+)["\']', "SNS"),
    # Redis pub/sub
    (r'redis\.StrictRedis\([^)]*host\s*=\s*["\']([^"\']+)["\']', "Redis"),
    (r'redis\.from_url\(\s*["\']([^"\']+)["\']', "Redis"),
]

# ── Environment-variable URL references ──────────────────────────────────────
# Catches patterns like os.getenv("USER_SERVICE_URL") or process.env.PAYMENT_SERVICE_HOST
_ENV_URL_PATTERNS = [
    r'os\.getenv\(\s*["\']([A-Z][A-Z0-9_]*(?:_URL|_HOST|_BASE_URL|_ENDPOINT))["\']',
    r'os\.environ\[\s*["\']([A-Z][A-Z0-9_]*(?:_URL|_HOST|_BASE_URL|_ENDPOINT))["\']',
    r'process\.env\.([A-Z][A-Z0-9_]*(?:_URL|_HOST|_BASE_URL|_ENDPOINT))',
    r'getenv\(\s*["\']([A-Z][A-Z0-9_]*(?:_URL|_HOST|_BASE_URL|_ENDPOINT))["\']',
]

# Noise-filter: ignore local/self references
_SELF_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal",
    "/", "#", "",
}


def _is_external_host(url_or_host: str) -> bool:
    """Return True if the value looks like a real remote dependency."""
    val = url_or_host.strip().strip("'\"")
    # Strip protocol
    for prefix in ("http://", "https://", "grpc://", "amqp://", "redis://"):
        if val.startswith(prefix):
            val = val[len(prefix):]
            break
    host = val.split("/")[0].split(":")[0]
    if not host or host in _SELF_HOSTS:
        return False
    # Skip template variables like {BASE_URL}
    if "{" in host or "$" in host:
        return False
    # Skip obvious placeholders
    if host.lower() in ("example.com", "your-service", "service-name"):
        return False
    return True


def _extract_host(raw: str) -> str:
    """Extract hostname from a URL or return the raw value if already a host."""
    val = raw.strip().strip("'\"")
    for prefix in ("http://", "https://", "grpc://", "amqp://", "redis://"):
        if val.startswith(prefix):
            val = val[len(prefix):]
            break
    return val.split("/")[0].split(":")[0].lower()


class InterServiceCommDetector:
    """Scan a service directory for runtime dependencies on other services."""

    def __init__(self, service_path: Path):
        self.service_path = Path(service_path).resolve()

    def detect(self) -> list[dict]:
        """Return a list of inter-service comm entries (deduped)."""
        seen: set[tuple[str, str]] = set()
        results: list[dict] = []

        for entry in self._scan_all():
            key = (entry["target"], entry["protocol"])
            if key not in seen:
                seen.add(key)
                results.append(entry)

        return results

    # ─────────────────────────────────────────────────────────────────────────

    def _scan_all(self):
        code_exts = {".py", ".js", ".ts", ".go", ".java", ".rb"}
        for ext in code_exts:
            for fpath in limited_rglob(self.service_path, f"*{ext}"):
                # Skip test files – they often contain dummy URLs
                parts = fpath.parts
                if any(p in parts for p in ("test", "tests", "__tests__", "spec")):
                    continue
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")[:_READ_LIMIT]
                except OSError:
                    continue

                yield from self._scan_content(content)

    def _scan_content(self, content: str):
        all_patterns = _HTTP_PATTERNS + _GRPC_PATTERNS + _QUEUE_PATTERNS

        for pattern, protocol in all_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                raw = match.group(1)
                if not _is_external_host(raw):
                    continue
                target = _extract_host(raw)
                if target:
                    yield {"target": target, "protocol": protocol, "direction": "OUTBOUND"}

        # Environment variable URL references (no literal target known)
        for pattern in _ENV_URL_PATTERNS:
            for match in re.finditer(pattern, content):
                env_var = match.group(1)
                # Convert ENV_VAR_URL → env-var-service as readable target
                target = env_var.lower().replace("_url", "").replace("_host", "").replace(
                    "_base", ""
                ).replace("_endpoint", "").replace("_", "-")
                if target:
                    yield {"target": target, "protocol": "HTTP", "direction": "OUTBOUND"}


def detect_inter_service_comms(service_path: Path) -> list[dict]:
    """Convenience wrapper. Returns [] if path doesn't exist."""
    if not service_path or not Path(service_path).exists():
        return []
    return InterServiceCommDetector(service_path).detect()
