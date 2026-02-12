"""API Surface Type detection.

Scans a service directory for code patterns that indicate how the service
exposes itself to callers.  Results populate Service.api_surface_types.

Supported surface types (from APISurfaceType enum):
  REST         – HTTP route decorators, OpenAPI specs
  GraphQL      – .graphql/.gql files, schema/resolver patterns
  gRPC         – .proto files, grpc stubs
  CLI          – argparse/click/typer/fire entry points, bin in package.json
  WebSocket    – websocket decorators, socket.io, ws handlers
  Event-Driven – Kafka/RabbitMQ/SQS consumers, event-bus patterns
"""

import json
import logging
from pathlib import Path
from typing import Optional

from app.utils.fs_utils import limited_rglob

logger = logging.getLogger(__name__)

# Maximum bytes to read per file (keeps it fast)
_READ_LIMIT = 8_000

# ── REST ─────────────────────────────────────────────────────────────────────
_REST_FILE_SIGNALS = [
    "openapi.yaml", "openapi.yml", "swagger.yaml", "swagger.yml",
    "swagger.json", "openapi.json",
]
_REST_CODE_PATTERNS = [
    # Python – FastAPI / Flask / Django / Starlette
    "@app.get(", "@app.post(", "@app.put(", "@app.delete(", "@app.patch(",
    "@router.get(", "@router.post(", "@router.put(", "@router.delete(",
    "@api_view", "@action(", "path(", "re_path(",  # Django
    # JavaScript / TypeScript – Express / Hapi / Fastify / Koa
    "app.get(", "app.post(", "router.get(", "router.post(",
    "fastify.get(", "fastify.post(", "server.route(",
    # Java – Spring Boot
    "@RestController", "@RequestMapping", "@GetMapping", "@PostMapping",
    # Go – Gin / Echo
    'r.GET("', 'r.POST("', 'e.GET("', 'e.POST("',
    # Ruby on Rails
    "resources :", "get '", "post '",
]

# ── GraphQL ───────────────────────────────────────────────────────────────────
_GRAPHQL_FILE_EXTS = {".graphql", ".gql"}
_GRAPHQL_CODE_PATTERNS = [
    "graphql", "apollo", "strawberry.type", "type Query", "type Mutation",
    "graphene", "ariadne", "schema = Schema(", "makeExecutableSchema",
    "buildSchema(", "@graphql_schema",
]

# ── gRPC ─────────────────────────────────────────────────────────────────────
_GRPC_FILE_EXTS = {".proto"}
_GRPC_CODE_PATTERNS = [
    "import grpc", "grpc.Server(", "grpc.insecure_channel(",
    "pb2_grpc", "ServicerContext", "grpc.server(",
    "grpcio", "@grpc.unary_unary",
]

# ── CLI ───────────────────────────────────────────────────────────────────────
_CLI_CODE_PATTERNS = [
    # Python
    "import argparse", "ArgumentParser(", "add_argument(",
    "@click.command", "@click.group", "import click",
    "@app.command", "typer.Typer(", "import typer",
    "import fire", "fire.Fire(",
    # Node.js
    "commander", "yargs", "meow(", "oclif",
]
_CLI_SHEBANG = "#!/usr/bin/env"

# ── WebSocket ────────────────────────────────────────────────────────────────
_WS_CODE_PATTERNS = [
    # Python
    "@app.websocket(", "@router.websocket(", "WebSocket(", "websockets.",
    "websocket.accept(", "websocket.send_",
    # JavaScript / Node.js
    "socket.io", "ws.Server(", "new WebSocket(", "io.on('connection'",
    "socket.on(", "wss.on(",
    # Django Channels
    "WebsocketConsumer", "AsyncWebsocketConsumer", "JsonWebsocketConsumer",
]

# ── Event-Driven ─────────────────────────────────────────────────────────────
_EVENT_CODE_PATTERNS = [
    # Kafka
    "KafkaConsumer(", "KafkaProducer(", "@kafka_consumer", "confluent_kafka",
    "aiokafka", "kafka-python",
    # RabbitMQ / AMQP
    "pika.connect", "aio_pika", "kombu", "celery",
    "channel.basic_consume", "channel.queue_declare",
    # AWS SQS / SNS
    "boto3.client('sqs')", "boto3.client(\"sqs\")", "sqs.receive_message",
    "boto3.client('sns')",
    # Redis Streams / Pub-Sub
    "redis.pubsub()", "r.subscribe(",
    # Generic event patterns
    "@event_handler", "@on_event", "EventBus", "MessageBus",
    "subscribe(", "publish(",
]


class APISurfaceDetector:
    """Detects which API surface types a service exposes."""

    def __init__(self, service_path: Path):
        self.service_path = Path(service_path).resolve()

    def detect(self) -> list[str]:
        """Return a deduplicated list of detected APISurfaceType values."""
        detected: list[str] = []

        if self._has_rest():
            detected.append("REST")
        if self._has_graphql():
            detected.append("GraphQL")
        if self._has_grpc():
            detected.append("gRPC")
        if self._has_cli():
            detected.append("CLI")
        if self._has_websocket():
            detected.append("WebSocket")
        if self._has_event_driven():
            detected.append("Event-Driven")

        return detected

    # ─────────────────────────────────────────────────────────────────────────
    # Per-type detectors
    # ─────────────────────────────────────────────────────────────────────────

    def _has_rest(self) -> bool:
        # Fast path: OpenAPI spec file present
        for name in _REST_FILE_SIGNALS:
            if (self.service_path / name).exists():
                return True
        return self._scan_code(_REST_CODE_PATTERNS, exts={".py", ".js", ".ts", ".java", ".go", ".rb"})

    def _has_graphql(self) -> bool:
        # .graphql / .gql files
        for ext in _GRAPHQL_FILE_EXTS:
            for _ in limited_rglob(self.service_path, f"*{ext}"):
                return True
        return self._scan_code(_GRAPHQL_CODE_PATTERNS, exts={".py", ".js", ".ts"})

    def _has_grpc(self) -> bool:
        # .proto files are definitive
        for _ in limited_rglob(self.service_path, "*.proto"):
            return True
        return self._scan_code(_GRPC_CODE_PATTERNS, exts={".py", ".go", ".java", ".js", ".ts"})

    def _has_cli(self) -> bool:
        # bin field in package.json
        pkg = self.service_path / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
                if data.get("bin"):
                    return True
            except (OSError, json.JSONDecodeError, ValueError):
                pass

        # __main__.py with CLI patterns
        for main_file in limited_rglob(self.service_path, "__main__.py"):
            try:
                content = main_file.read_text(encoding="utf-8", errors="ignore")[:_READ_LIMIT]
                if any(p in content for p in _CLI_CODE_PATTERNS):
                    return True
            except OSError:
                pass

        return self._scan_code(_CLI_CODE_PATTERNS, exts={".py", ".js", ".ts"}, max_files=20)

    def _has_websocket(self) -> bool:
        return self._scan_code(_WS_CODE_PATTERNS, exts={".py", ".js", ".ts"})

    def _has_event_driven(self) -> bool:
        # Also check dependency files for queue libraries
        if self._has_queue_dependency():
            return True
        return self._scan_code(_EVENT_CODE_PATTERNS, exts={".py", ".js", ".ts", ".java", ".go"})

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _scan_code(
        self,
        patterns: list[str],
        exts: set[str],
        max_files: int = 60,
    ) -> bool:
        """Return True if any pattern appears in any source file with the given extensions."""
        count = 0
        for ext in exts:
            for fpath in limited_rglob(self.service_path, f"*{ext}"):
                if count >= max_files:
                    return False
                count += 1
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")[:_READ_LIMIT]
                    if any(p in content for p in patterns):
                        return True
                except OSError:
                    pass
        return False

    def _has_queue_dependency(self) -> bool:
        """Check manifest files for known event/queue library dependencies."""
        queue_libs = {
            "kafka-python", "confluent-kafka", "aiokafka",
            "pika", "aio-pika", "kombu", "celery",
            "boto3",           # SQS/SNS
            "redis",
        }

        # requirements.txt / requirements*.txt
        for req_file in limited_rglob(self.service_path, "requirements*.txt"):
            try:
                content = req_file.read_text(encoding="utf-8", errors="ignore").lower()
                if any(lib in content for lib in queue_libs):
                    return True
            except OSError:
                pass

        # package.json
        pkg = self.service_path / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
                all_deps = {
                    **data.get("dependencies", {}),
                    **data.get("devDependencies", {}),
                }
                node_queue_libs = {"kafkajs", "amqplib", "bull", "bullmq", "sqs-consumer", "ioredis"}
                if any(lib in all_deps for lib in node_queue_libs):
                    return True
            except (OSError, json.JSONDecodeError, ValueError):
                pass

        return False


def detect_api_surface_types(service_path: Path) -> list[str]:
    """Convenience wrapper returning surface types for a service directory."""
    if not service_path or not Path(service_path).exists():
        return []
    return APISurfaceDetector(service_path).detect()
