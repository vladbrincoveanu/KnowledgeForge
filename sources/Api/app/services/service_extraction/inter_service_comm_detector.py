"""Inter-Service Communication Detection.

Detects how services communicate:
- HTTP clients, gRPC clients, queue producers/consumers, event bus
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def detect_inter_service_comms(repo_path: Path) -> list[dict[str, Any]]:
    """Detect inter-service communication patterns.

    Args:
        repo_path: Path to the repository

    Returns:
        List of communication patterns with target, protocol, direction, evidence
    """
    repo_path = Path(repo_path)
    if not repo_path.exists():
        return []

    comms = []

    # HTTP clients
    comms.extend(_detect_http_clients(repo_path))

    # gRPC clients
    comms.extend(_detect_grpc_clients(repo_path))

    # Queue producers/consumers
    comms.extend(_detect_queue_comms(repo_path))

    # Event bus
    comms.extend(_detect_event_bus(repo_path))

    return comms


def _detect_http_clients(repo_path: Path) -> list[dict[str, Any]]:
    """Detect HTTP client usage."""
    comms = []
    http_patterns = {
        "requests": r"import requests|from requests import",
        "httpx": r"import httpx|from httpx import",
        "aiohttp": r"import aiohttp|from aiohttp import",
        "urllib": r"from urllib\.request import",
        "fetch": r"fetch\(|axios\(",
        "got": r"import got|from got import",
    }

    for client, pattern in http_patterns.items():
        matches = list(repo_path.rglob("*.py"))
        for f in matches:
            try:
                content = f.read_text(errors="ignore")
                if re.search(pattern, content):
                    comms.append({
                        "target": "unknown",
                        "protocol": "HTTP",
                        "direction": "outgoing",
                        "confidence": 0.7,
                        "evidence": [{"type": "http_client", "source": str(f.relative_to(repo_path)), "snippet": client}]
                    })
                    break
            except Exception:
                continue

    return comms


def _detect_grpc_clients(repo_path: Path) -> list[dict[str, Any]]:
    """Detect gRPC client usage."""
    comms = []

    # Check for grpc imports
    matches = list(repo_path.rglob("*.py"))
    for f in matches:
        try:
            content = f.read_text(errors="ignore")
            if re.search(r"import grpc|from grpc", content):
                # Look for channel/stub creation
                if re.search(r"channel\(|stub = ", content):
                    comms.append({
                        "target": "unknown",
                        "protocol": "gRPC",
                        "direction": "outgoing",
                        "confidence": 0.8,
                        "evidence": [{"type": "grpc_client", "source": str(f.relative_to(repo_path)), "snippet": "grpc"}]
                    })
                    break
        except Exception:
            continue

    return comms


def _detect_queue_comms(repo_path: Path) -> list[dict[str, Any]]:
    """Detect message queue producers/consumers."""
    comms = []

    queue_patterns = {
        "kafka": (r"from kafka|import kafka", ["KafkaConsumer", "KafkaProducer"]),
        "pika": (r"import pika|from pika", ["channel.basic_publish", "basic_consume"]),
        "pulsar": (r"import pulsar|from pulsar", ["Producer", "Consumer"]),
        "redis": (r"import redis|from redis", ["redis.Redis", "r.push", "r.publish"]),
    }

    matches = list(repo_path.rglob("*.py"))
    for queue, (import_pattern, usage_patterns) in queue_patterns.items():
        for f in matches:
            try:
                content = f.read_text(errors="ignore")
                if re.search(import_pattern, content):
                    # Determine if producer or consumer
                    for usage in usage_patterns:
                        if usage in content:
                            direction = "incoming" if "consume" in usage.lower() or "consumer" in usage.lower() else "outgoing"
                            comms.append({
                                "target": "unknown",
                                "protocol": queue.capitalize(),
                                "direction": direction,
                                "confidence": 0.7,
                                "evidence": [{"type": "queue_client", "source": str(f.relative_to(repo_path)), "snippet": usage}]
                            })
                            break
            except Exception:
                continue

    return comms


def _detect_event_bus(repo_path: Path) -> list[dict[str, Any]]:
    """Detect event bus patterns."""
    comms = []

    event_patterns = {
        "redis-pubsub": (r"publish|subscribe", "Redis Pub/Sub"),
        "event-bus": (r"EventBus|event_bus|EventEmitter", "Event Bus"),
    }

    matches = list(repo_path.rglob("*.py"))
    for pattern_name, (pattern, protocol) in event_patterns.items():
        for f in matches:
            try:
                content = f.read_text(errors="ignore")
                if re.search(pattern, content, re.IGNORECASE):
                    comms.append({
                        "target": "unknown",
                        "protocol": protocol,
                        "direction": "bidirectional",
                        "confidence": 0.6,
                        "evidence": [{"type": "event_bus", "source": str(f.relative_to(repo_path)), "snippet": pattern_name}]
                    })
                    break
            except Exception:
                continue

    return comms
