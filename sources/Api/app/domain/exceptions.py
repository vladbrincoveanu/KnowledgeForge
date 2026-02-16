"""Domain-specific exceptions for KnowledgeForge.

Replaces bare `except Exception` with typed exceptions that can be
caught selectively or allowed to propagate.
"""


class KnowledgeForgeError(Exception):
    """Base exception for all KnowledgeForge errors."""


# ── File & Parsing ──────────────────────────────────────────────────────────

class FileReadError(KnowledgeForgeError):
    """Failed to read a file (I/O error, permission denied, encoding issue)."""


class ConfigParseError(KnowledgeForgeError):
    """Failed to parse a configuration file (YAML, JSON, TOML, etc.)."""


class ManifestParseError(ConfigParseError):
    """Failed to parse a package manifest (package.json, pyproject.toml, etc.)."""


# ── External Process ────────────────────────────────────────────────────────

class GitCommandError(KnowledgeForgeError):
    """A git subprocess command failed."""


class SubprocessError(KnowledgeForgeError):
    """A subprocess command failed."""


# ── LLM ─────────────────────────────────────────────────────────────────────

class LLMError(KnowledgeForgeError):
    """Base class for LLM-related errors."""


class LLMConnectionError(LLMError):
    """Could not connect to the LLM service."""


class LLMResponseError(LLMError):
    """LLM returned an invalid or unparseable response."""


class LLMTimeoutError(LLMError):
    """LLM request timed out."""


# ── Graph / Storage ─────────────────────────────────────────────────────────

class GraphDatabaseError(KnowledgeForgeError):
    """Neo4j or other graph database operation failed."""


class StorageError(KnowledgeForgeError):
    """Persistent storage operation failed (embedding store, metadata store)."""


# ── Extraction ──────────────────────────────────────────────────────────────

class ExtractionError(KnowledgeForgeError):
    """An extraction step failed."""


class ContainerDetectionError(ExtractionError):
    """Failed to detect containers from repo structure."""


class ComponentExtractionError(ExtractionError):
    """Failed to extract components."""


class ServiceExtractionError(ExtractionError):
    """Failed to extract services."""


# ── WebSocket / Broadcast ───────────────────────────────────────────────────

class BroadcastError(KnowledgeForgeError):
    """Failed to broadcast a WebSocket message."""
