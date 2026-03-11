"""API Surface Type Detection.

Detects what kind of API surface a service exposes:
- REST, GraphQL, gRPC, CLI, WebSocket, Event-Driven
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def detect_api_surface_types(repo_path: Path) -> list[str]:
    """Detect API surface types exposed by the service.

    Args:
        repo_path: Path to the repository

    Returns:
        List of detected API types (e.g., ["REST", "gRPC"])
    """
    repo_path = Path(repo_path)
    if not repo_path.exists():
        return []

    surface_types = set()

    # Check for REST (FastAPI, Flask, Express, Django, etc.)
    if _detect_rest(repo_path):
        surface_types.add("REST")

    # Check for GraphQL
    if _detect_graphql(repo_path):
        surface_types.add("GraphQL")

    # Check for gRPC
    if _detect_grpc(repo_path):
        surface_types.add("gRPC")

    # Check for CLI
    if _detect_cli(repo_path):
        surface_types.add("CLI")

    # Check for WebSocket
    if _detect_websocket(repo_path):
        surface_types.add("WebSocket")

    # Check for Event-Driven
    if _detect_event_driven(repo_path):
        surface_types.add("Event-Driven")

    return sorted(surface_types)


def _detect_rest(repo_path: Path) -> bool:
    """Detect REST API frameworks."""
    # Check for FastAPI
    if _has_file_with_content(repo_path, ["main.py", "app.py"], ["from fastapi import", "FastAPI()"]):
        return True

    # Check for Flask
    if _has_file_with_content(repo_path, ["app.py", "application.py"], ["from flask import", "Flask()"]):
        return True

    # Check for Express.js
    if _has_file_with_content(repo_path, ["index.js", "app.js", "server.js"], ["express()", "require('express')"]):
        return True

    # Check for Django
    if (repo_path / "urls.py").exists() or (repo_path / "wsgi.py").exists():
        return True

    # Check for Spring Boot
    if _has_file_with_content(repo_path, ["*Controller.java", "*RestController.java"], ["@RestController", "@RequestMapping"]):
        return True

    # Check for .NET Web API
    if _has_file_with_content(repo_path, ["*Controller.cs"], ["[ApiController]", "[Route("]):
        return True

    # Check for OpenAPI/Swagger
    openapi_files = list(repo_path.rglob("openapi*.json")) + list(repo_path.rglob("swagger*.json"))
    if openapi_files:
        return True

    return False


def _detect_graphql(repo_path: Path) -> bool:
    """Detect GraphQL APIs."""
    # Check for GraphQL dependencies in package files
    package_files = [
        repo_path / "package.json",
        repo_path / "requirements.txt",
        repo_path / "pyproject.toml",
    ]

    for pf in package_files:
        if pf.exists():
            content = pf.read_text(errors="ignore").lower()
            if "graphql" in content or "apollo" in content or "graphene" in content:
                return True

    # Check for GraphQL schema files
    schema_files = list(repo_path.rglob("schema.graphql")) + list(repo_path.rglob("*.graphqls"))
    if schema_files:
        return True

    # Check for GraphQL type definitions in code
    if _has_file_with_content(repo_path, ["*.ts", "*.js", "*.py"], ["type Query", "type Mutation", "gql`"]):
        return True

    return False


def _detect_grpc(repo_path: Path) -> bool:
    """Detect gRPC services."""
    # Check for proto files
    proto_files = list(repo_path.rglob("*.proto"))
    if proto_files:
        return True

    # Check for gRPC dependencies
    package_files = [
        repo_path / "requirements.txt",
        repo_path / "package.json",
        repo_path / "go.mod",
    ]

    for pf in package_files:
        if pf.exists():
            content = pf.read_text(errors="ignore").lower()
            if "grpc" in content:
                return True

    # Check for gRPC imports in code
    if _has_file_with_content(repo_path, ["*.py"], ["import grpc", "from grpc"]):
        return True

    if _has_file_with_content(repo_path, ["*.go"], ["google.golang.org/grpc", "grpclib"]):
        return True

    return False


def _detect_cli(repo_path: Path) -> bool:
    """Detect CLI tools."""
    # Check for CLI frameworks
    cli_indicators = [
        ("requirements.txt", ["click", "typer", "argparse"]),
        ("pyproject.toml", ["click", "typer"]),
        ("package.json", ["commander", "yargs", "cli", "@oclif"]),
    ]

    for file_pattern, indicators in cli_indicators:
        if file_pattern == "requirements.txt":
            rf = repo_path / file_pattern
        elif file_pattern == "pyproject.toml":
            rf = repo_path / file_pattern
        elif file_pattern == "package.json":
            rf = repo_path / file_pattern
        else:
            continue

        if rf.exists():
            content = rf.read_text(errors="ignore").lower()
            if any(ind.lower() in content for ind in indicators):
                return True

    # Check for CLI entry points
    cli_files = list(repo_path.rglob("cli.py")) + list(repo_path.rglob("__main__.py"))
    if cli_files:
        return True

    # Check for Makefile with install scripts
    makefile = repo_path / "Makefile"
    if makefile.exists():
        content = makefile.read_text(errors="ignore").lower()
        if "install" in content and "cli" in content:
            return True

    return False


def _detect_websocket(repo_path: Path) -> bool:
    """Detect WebSocket usage."""
    # Check for WebSocket dependencies
    ws_indicators = [
        ("requirements.txt", ["websockets", "socket.io", "ws"]),
        ("package.json", ["socket.io", "ws", "websocket"]),
    ]

    for file_pattern, indicators in ws_indicators:
        if file_pattern == "requirements.txt":
            rf = repo_path / file_pattern
        else:
            rf = repo_path / file_pattern

        if rf.exists():
            content = rf.read_text(errors="ignore").lower()
            if any(ind.lower() in content for ind in indicators):
                return True

    # Check for WebSocket code
    if _has_file_with_content(repo_path, ["*.py"], ["WebSocket", "websocket"]):
        return True

    if _has_file_with_content(repo_path, ["*.ts", "*.js"], ["WebSocket", "socket.io"]):
        return True

    return False


def _detect_event_driven(repo_path: Path) -> bool:
    """Detect event-driven architecture (Kafka, RabbitMQ, etc.)."""
    # Check for message queue dependencies
    event_indicators = [
        ("requirements.txt", ["kafka", "pika", "rabbitmq", "pulsar", "redis"]),
        ("package.json", ["kafka", "amqp", "rabbitmq", "pulsar"]),
        ("go.mod", ["kafka", "amqp", "rabbitmq"]),
    ]

    for file_pattern, indicators in event_indicators:
        if file_pattern in ["requirements.txt", "go.mod"]:
            rf = repo_path / file_pattern
        else:
            rf = repo_path / file_pattern

        if rf.exists():
            content = rf.read_text(errors="ignore").lower()
            if any(ind.lower() in content for ind in indicators):
                return True

    # Check for event-related code patterns
    if _has_file_with_content(repo_path, ["*.py"], ["@consumer", "@producer", "KafkaConsumer", "KafkaProducer"]):
        return True

    if _has_file_with_content(repo_path, ["*.ts", "*.js"], ["kafka", "amqp", "rabbitmq"]):
        return True

    return False


def _has_file_with_content(repo_path: Path, patterns: list[str], keywords: list[str]) -> bool:
    """Check if any file matching pattern contains any of the keywords."""
    for pattern in patterns:
        # Handle glob patterns
        if "*" in pattern:
            files = list(repo_path.rglob(pattern))
        else:
            # Single file
            f = repo_path / pattern
            files = [f] if f.exists() else []

        for file_path in files:
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(errors="ignore")
                if any(kw in content for kw in keywords):
                    return True
            except Exception:
                continue
    return False
