"""Streamlined configuration management for KnowledgeForge API."""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    """PostgreSQL database connection configuration."""

    type: str = Field(default="postgresql", description="Database type")
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="knowledgeforge", description="Database name")
    username: str = Field(default="knowledgeforge", description="Database username")
    password: str = Field(default="knowledgeforge123", description="Database password")
    connection_pool: dict = Field(
        default_factory=lambda: {
            "min_connections": 1,
            "max_connections": 20,
            "connection_timeout": 30,
            "idle_timeout": 300,
        },
        description="Connection pool settings"
    )
    ssl_mode: str = Field(default="prefer", description="SSL mode")
    application_name: str = Field(
        default="KnowledgeForge-API", description="Application name"
    )


class Neo4jConfig(BaseModel):
    """Neo4j database connection configuration."""

    uri: str = Field(
        default="bolt://localhost:7687", description="Neo4j connection URI"
    )
    username: str = Field(default="neo4j", description="Database username")
    password: str = Field(default="password", description="Database password")
    database: str = Field(default="neo4j", description="Database name")
    max_connection_pool_size: int = Field(
        default=50, ge=1, le=1000, description="Maximum connection pool size"
    )
    connection_timeout: int = Field(
        default=30, ge=1, description="Connection timeout in seconds"
    )
    encrypted: bool = Field(default=False, description="Use encrypted connections")

    @validator("uri")
    def validate_uri(cls, v):
        if not v.startswith(("bolt://", "neo4j://")):
            raise ValueError("URI must start with bolt:// or neo4j://")
        return v


class LMStudioConfig(BaseModel):
    """LM Studio LLM service configuration."""

    base_url: str = Field(
        default="http://localhost:1234", description="LM Studio service base URL"
    )
    model_name: str = Field(
        default="deepseek/deepseek-r1-0528-qwen3-8b", description="Default model to use"
    )
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=100, ge=1, le=4096, description="Maximum tokens to generate"
    )
    timeout: int = Field(default=30, ge=1, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, ge=1, description="Number of retry attempts")
    use_embeddings: bool = Field(default=True, description="Enable sentence embeddings")
    embedding_model: str = Field(
        default="text-embedding-nomic-embed-text-v1.5",
        description="Sentence transformer model",
    )
    context_length: int = Field(
        default=4096, ge=512, le=32768, description="Context window size"
    )
    stop_sequences: list = Field(
        default=["</s>", "<|endoftext|>"], description="Stop generation sequences"
    )
    top_p: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Top-p sampling parameter"
    )
    top_k: int = Field(default=40, ge=1, le=100, description="Top-k sampling parameter")

    @validator("base_url")
    def validate_base_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return v.rstrip("/")


class ExtractionConfig(BaseModel):
    """Ontology extraction process configuration."""

    confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )
    batch_size: int = Field(
        default=1000, ge=1, le=10000, description="Processing batch size"
    )
    max_entities_per_column: int = Field(
        default=100, ge=1, le=1000, description="Maximum entities per column"
    )
    relationship_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Relationship confidence threshold"
    )
    enable_semantic_similarity: bool = Field(
        default=True, description="Enable semantic similarity analysis"
    )
    enable_hierarchical_discovery: bool = Field(
        default=True, description="Enable hierarchical relationship discovery"
    )
    enable_temporal_analysis: bool = Field(
        default=True, description="Enable temporal relationship analysis"
    )
    sample_size: int = Field(
        default=1000, ge=100, le=100000, description="Sample size for profiling"
    )
    parallel_processing: bool = Field(
        default=False, description="Enable parallel processing"
    )
    max_workers: int = Field(
        default=4, ge=1, le=16, description="Maximum worker processes"
    )


class MetadataStorageConfig(BaseModel):
    """Metadata storage configuration."""

    cache_enabled: bool = Field(default=True, description="Enable metadata caching")
    cache_size_mb: int = Field(
        default=100, ge=1, le=1000, description="Cache size in MB"
    )
    auto_cleanup: bool = Field(default=True, description="Enable automatic cleanup")
    cleanup_interval_days: int = Field(
        default=30, ge=1, le=365, description="Cleanup interval in days"
    )
    export_format: str = Field(
        default="json", description="Export format (json, csv, parquet)"
    )
    backup_enabled: bool = Field(default=False, description="Enable automatic backups")
    backup_interval_hours: int = Field(
        default=24, ge=1, le=168, description="Backup interval in hours"
    )

    @validator("export_format")
    def validate_export_format(cls, v):
        valid_formats = ["json", "csv", "parquet"]
        if v.lower() not in valid_formats:
            raise ValueError(f"Export format must be one of: {valid_formats}")
        return v.lower()


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format",
    )
    file_enabled: bool = Field(default=True, description="Enable file logging")
    file_path: Optional[str] = Field(
        default="./logs/api.log", description="Log file path"
    )
    max_file_size_mb: int = Field(
        default=10, ge=1, le=100, description="Maximum log file size in MB"
    )
    backup_count: int = Field(
        default=5, ge=0, le=20, description="Number of backup files"
    )
    console_enabled: bool = Field(default=True, description="Enable console logging")
    json_format: bool = Field(default=False, description="Use JSON log format")

    @validator("level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()


class SecurityConfig(BaseModel):
    """API security configuration."""

    api_key_required: bool = Field(
        default=True, description="Require API key for requests"
    )
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(
        default=100, ge=1, description="Rate limit requests per window"
    )
    rate_limit_window: int = Field(
        default=60, ge=1, description="Rate limit window in seconds"
    )
    cors_origins: list = Field(default=["*"], description="Allowed CORS origins")
    trusted_hosts: list = Field(default=["*"], description="Trusted host patterns")


class Config(BaseSettings):
    """Main configuration class for KnowledgeForge API."""

    # Configuration file path
    config_file: Optional[str] = Field(
        default=None, description="Path to configuration file"
    )

    # Environment settings
    environment: str = Field(default="development", description="Environment name")
    debug: bool = Field(default=True, description="Enable debug mode")

    # Nested configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    lmstudio: LMStudioConfig = Field(default_factory=LMStudioConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    metadata_storage: MetadataStorageConfig = Field(
        default_factory=MetadataStorageConfig
    )
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # WebSocket and background task settings
    websocket_ping_interval: int = Field(
        default=30, description="WebSocket ping interval"
    )
    websocket_ping_timeout: int = Field(
        default=10, description="WebSocket ping timeout"
    )
    max_concurrent_tasks: int = Field(
        default=5, description="Maximum concurrent background tasks"
    )
    task_timeout: int = Field(
        default=3600, description="Background task timeout in seconds"
    )

    class Config:
        env_prefix = "KF_"
        env_nested_delimiter = "__"
        case_sensitive = False

    def __init__(self, **kwargs):
        config_file = kwargs.get("config_file") or os.getenv("KF_CONFIG_FILE")
        if config_file and Path(config_file).exists():
            self._load_from_file(config_file, kwargs)
        super().__init__(**kwargs)

    def _load_from_file(self, config_file: str, kwargs: dict[str, Any]):
        """Load configuration from YAML file."""
        try:
            with open(config_file) as f:
                file_config = yaml.safe_load(f)

            if file_config:
                # Update kwargs with file config
                for key, value in file_config.items():
                    if key not in kwargs:
                        kwargs[key] = value

        except Exception as e:
            raise ValueError(f"Failed to load config file {config_file}: {e}")

    def setup_logging(self):
        """Setup logging based on configuration."""
        log_config = self.logging

        # Create logs directory if it doesn't exist
        if log_config.file_enabled and log_config.file_path:
            log_dir = Path(log_config.file_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)

        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_config.level),
            format=log_config.format,
            force=True,
        )

        # Add file handler if enabled
        if log_config.file_enabled and log_config.file_path:
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                log_config.file_path,
                maxBytes=log_config.max_file_size_mb * 1024 * 1024,
                backupCount=log_config.backup_count,
            )

            formatter = logging.Formatter(log_config.format)
            file_handler.setFormatter(formatter)
            logging.getLogger().addHandler(file_handler)

        # Set specific logger levels
        logging.getLogger("neo4j").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)

    def get_neo4j_connection_string(self) -> str:
        """Get Neo4j connection string."""
        return (
            f"{self.neo4j.uri} (user: {self.neo4j.username}, db: {self.neo4j.database})"
        )

    def get_llm_endpoint(self, endpoint: str = "") -> str:
        """Get LLM API endpoint URL."""
        return f"{self.lmstudio.base_url}/v1/{endpoint.lstrip('/')}"

    def validate(self) -> dict[str, Any]:
        """Validate configuration and return results."""
        results = {"valid": True, "errors": [], "warnings": []}

        try:
            # Basic validations
            if not self.neo4j.uri:
                results["errors"].append("Neo4j URI is required")
                results["valid"] = False

            if not self.lmstudio.base_url:
                results["errors"].append("LM Studio base URL is required")
                results["valid"] = False

            # Threshold validations
            if (
                self.extraction.confidence_threshold
                > self.extraction.relationship_threshold
            ):
                results["warnings"].append(
                    "Confidence threshold is higher than relationship threshold"
                )

            # Performance warnings
            if self.extraction.batch_size > 5000:
                results["warnings"].append("Large batch size may impact performance")

        except Exception as e:
            results["errors"].append(f"Validation error: {str(e)}")
            results["valid"] = False

        return results


def get_config(config_file: Optional[str] = None) -> Config:
    """Get application configuration.

    Args:
        config_file: Optional path to configuration file

    Returns:
        Configuration object
    """
    config = Config(config_file=config_file)

    # Setup logging
    config.setup_logging()

    # Validate configuration
    validation = config.validate()
    if not validation["valid"]:
        logging.error(f"Configuration validation failed: {validation['errors']}")
        raise ValueError("Invalid configuration")

    if validation["warnings"]:
        logging.warning(f"Configuration warnings: {validation['warnings']}")

    logging.info("Configuration loaded successfully")
    return config


# Global config instance
config = get_config()
