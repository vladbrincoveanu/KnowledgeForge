"""Protocol detection from source code fingerprints.

Detects inter-container communication protocols by scanning source files
for characteristic imports, class instantiations, and URL patterns.
This implements the C4 book insight: "The protocol field on L2 relationships
is high-value and usually detectable via tree-sitter fingerprints."
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# (protocol_name, [regex_patterns_that_fingerprint_it])
_FINGERPRINTS: list[tuple[str, list[str]]] = [
    ("Kafka", [
        r"\bKafkaProducer\b",
        r"\bKafkaConsumer\b",
        r"@KafkaListener",
        r"confluent_kafka",
        r"from kafka import",
        r"kafka-python",
        r"KafkaJS",
    ]),
    ("gRPC", [
        r"\bimport grpc\b",
        r"grpc\.insecure_channel",
        r"grpc\.secure_channel",
        r"_pb2\.py",
        r"from .+_pb2",
        r"\.proto\b",
    ]),
    ("JDBC", [
        r"\bpsycopg2\b",
        r"\bpymysql\b",
        r"\bcx_Oracle\b",
        r"jdbc:",
        r"SQLAlchemy",
        r"from sqlalchemy",
        r"pg\.Pool",
        r"mysql2",
        r"asyncpg",
    ]),
    ("AMQP", [
        r"\bimport pika\b",
        r"amqplib",
        r"amqp://",
        r"channel\.basic_publish",
        r"@RabbitListener",
        r"amqp\.connect",
    ]),
    ("WebSocket", [
        r"\bwebsockets\b",
        r"ws://",
        r"wss://",
        r"socket\.io",
        r"\bWebSocket\(",
        r"@ServerEndpoint",
        r"useWebSocket",
    ]),
    ("GraphQL", [
        r"\bfrom gql\b",
        r"\bApollo\b",
        r"@GraphQLQuery",
        r"\bgraphene\b",
        r"\.graphql\b",
        r"gql`",
        r"graphql-request",
    ]),
    ("REST/HTTPS", [
        r"requests\.(get|post|put|delete|patch)\(",
        r"axios\.(get|post|put|delete|patch)\(",
        r"\bfetch\(",
        r"HttpClient",
        r"urllib\.request",
        r"@RestController",
        r"@GetMapping",
        r"@PostMapping",
        r"http\.get\(",
        r"http\.post\(",
    ]),
    ("SMTP", [
        r"\bsmtplib\b",
        r"\bnodemailer\b",
        r"JavaMailSender",
        r"\bsendgrid\b",
        r"smtp://",
        r"MAIL_HOST",
    ]),
]

# Name-based heuristics for detect_for_relationship()
_NAME_PROTOCOL_HINTS: list[tuple[list[str], str]] = [
    (["kafka", "broker", "topic", "msk"], "Kafka"),
    (["postgres", "postgresql", "mysql", "mariadb", "rds", "aurora", "sqlite"], "JDBC"),
    (["rabbit", "amqp", "exchange", "queue"], "AMQP"),
    (["redis", "memcached", "elasticache"], "Redis Protocol"),
    (["s3", "minio", "blob", "gcs", "storage", "bucket"], "S3 API"),
    (["mongo", "dynamodb", "dynamo", "cosmos", "cassandra", "couchdb"], "MongoDB Wire Protocol"),
    (["grpc", "proto"], "gRPC"),
    (["graphql"], "GraphQL"),
    (["smtp", "mail", "ses", "sendgrid", "mailgun"], "SMTP"),
]

_SKIP_DIRS = frozenset({
    "node_modules", ".git", "vendor", "dist", "build",
    "__pycache__", ".venv", "venv", ".tox", "target",
})
_SOURCE_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".java", ".cs", ".go", ".rb", ".kt",
})


@dataclass
class ProtocolMatch:
    """A detected protocol with supporting evidence."""

    protocol: str
    confidence: float
    evidence: str  # "relative/path/file.py: pattern matched"


class ProtocolDetector:
    """Scan source files for inter-service communication protocol fingerprints."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = Path(repo_path).resolve()

    def detect_protocols(self) -> list[ProtocolMatch]:
        """Scan all source files and return one ProtocolMatch per detected protocol."""
        found: dict[str, ProtocolMatch] = {}

        for src_file in self._iter_source_files():
            try:
                content = src_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            rel = str(src_file.relative_to(self.repo_path))
            for protocol, patterns in _FINGERPRINTS:
                if protocol in found:
                    continue
                for pattern in patterns:
                    if re.search(pattern, content):
                        found[protocol] = ProtocolMatch(
                            protocol=protocol,
                            confidence=0.85,
                            evidence=f"{rel}: matched `{pattern}`",
                        )
                        break

        return list(found.values())

    def detect_for_relationship(
        self, source_container: str, target_container: str
    ) -> str | None:
        """Return the most likely protocol for a source→target relationship.

        First checks target name against known heuristics; falls back to a
        full source scan if no heuristic matches.
        """
        target_lower = target_container.lower()

        for keywords, protocol in _NAME_PROTOCOL_HINTS:
            if any(kw in target_lower for kw in keywords):
                logger.debug("Protocol hint for '%s': %s", target_container, protocol)
                return protocol

        matches = self.detect_protocols()
        if matches:
            return matches[0].protocol

        return "HTTPS"

    def _iter_source_files(self):
        for path in self.repo_path.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in _SOURCE_EXTENSIONS:
                yield path