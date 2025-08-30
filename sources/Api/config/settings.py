"""Configuration management for ontology extraction system."""

import os
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator, root_validator
from pydantic_settings import BaseSettings


class Neo4jConfig(BaseModel):
    """Neo4j database connection configuration."""
    
    uri: str = Field(default="bolt://localhost:7687", description="Neo4j connection URI")
    username: str = Field(default="neo4j", description="Database username")
    password: str = Field(default="password", description="Database password")
    database: str = Field(default="neo4j", description="Database name")
    max_connection_pool_size: int = Field(default=50, description="Maximum connection pool size")
    connection_timeout: int = Field(default=30, description="Connection timeout in seconds")
    encrypted: bool = Field(default=True, description="Use encrypted connections")
    
    @validator('uri')
    def validate_uri(cls, v):
        """Validate Neo4j URI format."""
        if not v.startswith(('bolt://', 'neo4j://')):
            raise ValueError('URI must start with bolt:// or neo4j://')
        return v
    
    @validator('max_connection_pool_size')
    def validate_pool_size(cls, v):
        """Validate connection pool size."""
        if v < 1 or v > 1000:
            raise ValueError('Pool size must be between 1 and 1000')
        return v


class LMStudioConfig(BaseModel):
    """LM Studio LLM service configuration."""
    
    base_url: str = Field(default="http://localhost:1234", description="LM Studio service base URL")
    model_name: str = Field(default="deepseek/deepseek-r1-0528-qwen3-8b", description="Default model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=100, ge=1, le=4096, description="Maximum tokens to generate")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")
    use_embeddings: bool = Field(default=True, description="Enable sentence embeddings")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="Sentence transformer model")
    # LM Studio specific settings
    context_length: int = Field(default=4096, ge=512, le=32768, description="Context window size")
    stop_sequences: list = Field(default=["</s>", "<|endoftext|>"], description="Stop generation sequences")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Top-p sampling parameter")
    top_k: int = Field(default=40, ge=1, le=100, description="Top-k sampling parameter")
    
    @validator('base_url')
    def validate_base_url(cls, v):
        """Validate LM Studio base URL."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Base URL must start with http:// or https://')
        return v.rstrip('/')
    
    @validator('temperature')
    def validate_temperature(cls, v):
        """Validate temperature range."""
        if v < 0.0 or v > 2.0:
            raise ValueError('Temperature must be between 0.0 and 2.0')
        return v
    
    @validator('top_p')
    def validate_top_p(cls, v):
        """Validate top-p range."""
        if v < 0.0 or v > 1.0:
            raise ValueError('Top-p must be between 0.0 and 1.0')
        return v


class ExtractionConfig(BaseModel):
    """Ontology extraction process configuration."""
    
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence threshold")
    batch_size: int = Field(default=1000, ge=1, le=10000, description="Processing batch size")
    max_entities_per_column: int = Field(default=100, ge=1, le=1000, description="Maximum entities per column")
    relationship_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Relationship confidence threshold")
    enable_semantic_similarity: bool = Field(default=True, description="Enable semantic similarity analysis")
    enable_hierarchical_discovery: bool = Field(default=True, description="Enable hierarchical relationship discovery")
    enable_temporal_analysis: bool = Field(default=True, description="Enable temporal relationship analysis")
    sample_size: int = Field(default=1000, ge=100, le=100000, description="Sample size for profiling")
    parallel_processing: bool = Field(default=False, description="Enable parallel processing")
    max_workers: int = Field(default=4, ge=1, le=16, description="Maximum worker processes")
    
    @validator('confidence_threshold', 'relationship_threshold')
    def validate_thresholds(cls, v):
        """Validate confidence thresholds."""
        if v < 0.0 or v > 1.0:
            raise ValueError('Threshold must be between 0.0 and 1.0')
        return v
    
    @validator('batch_size')
    def validate_batch_size(cls, v):
        """Validate batch size."""
        if v < 1 or v > 10000:
            raise ValueError('Batch size must be between 1 and 10000')
        return v


class MetadataStorageConfig(BaseModel):
    """Metadata storage configuration."""
    
    duckdb_path: str = Field(default=":memory:", description="DuckDB database path")
    cache_enabled: bool = Field(default=True, description="Enable metadata caching")
    cache_size_mb: int = Field(default=100, ge=1, le=1000, description="Cache size in MB")
    auto_cleanup: bool = Field(default=True, description="Enable automatic cleanup")
    cleanup_interval_days: int = Field(default=30, ge=1, le=365, description="Cleanup interval in days")
    export_format: str = Field(default="json", description="Export format (json, csv, parquet)")
    backup_enabled: bool = Field(default=False, description="Enable automatic backups")
    backup_interval_hours: int = Field(default=24, ge=1, le=168, description="Backup interval in hours")
    
    @validator('duckdb_path')
    def validate_duckdb_path(cls, v):
        """Validate DuckDB path."""
        if v != ":memory:" and not Path(v).parent.exists():
            raise ValueError('DuckDB path directory must exist')
        return v
    
    @validator('export_format')
    def validate_export_format(cls, v):
        """Validate export format."""
        valid_formats = ['json', 'csv', 'parquet']
        if v.lower() not in valid_formats:
            raise ValueError(f'Export format must be one of: {valid_formats}')
        return v.lower()


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format")
    file_enabled: bool = Field(default=False, description="Enable file logging")
    file_path: Optional[str] = Field(default=None, description="Log file path")
    max_file_size_mb: int = Field(default=10, ge=1, le=100, description="Maximum log file size in MB")
    backup_count: int = Field(default=5, ge=0, le=20, description="Number of backup files")
    console_enabled: bool = Field(default=True, description="Enable console logging")
    json_format: bool = Field(default=False, description="Use JSON log format")
    
    @validator('level')
    def validate_log_level(cls, v):
        """Validate logging level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of: {valid_levels}')
        return v.upper()
    
    @validator('file_path')
    def validate_file_path(cls, v, values):
        """Validate log file path if file logging is enabled."""
        if values.get('file_enabled') and v:
            log_dir = Path(v).parent
            if not log_dir.exists():
                log_dir.mkdir(parents=True, exist_ok=True)
        return v


class OntologyExtractionConfig(BaseSettings):
    """Main configuration class for ontology extraction system."""
    
    # Nested configurations
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    lmstudio: LMStudioConfig = Field(default_factory=LMStudioConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    metadata_storage: MetadataStorageConfig = Field(default_factory=MetadataStorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    # Global settings
    environment: str = Field(default="development", description="Environment name")
    debug: bool = Field(default=False, description="Enable debug mode")
    config_file: Optional[str] = Field(default=None, description="Path to config file")
    
    class Config:
        env_prefix = "ONTOLOGY_"
        env_nested_delimiter = "__"
        case_sensitive = False
    
    @root_validator(pre=True)
    def load_config_file(cls, values):
        """Load configuration from file if specified."""
        config_file = values.get('config_file') or os.getenv('ONTOLOGY_CONFIG_FILE')
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r') as f:
                    file_config = yaml.safe_load(f)
                
                # Merge file config with environment variables
                if file_config:
                    # Update nested configs
                    for key, config_class in [
                        ('neo4j', Neo4jConfig),
                        ('lmstudio', LMStudioConfig),
                        ('extraction', ExtractionConfig),
                        ('metadata_storage', MetadataStorageConfig),
                        ('logging', LoggingConfig)
                    ]:
                        if key in file_config:
                            if key in values:
                                # Merge with existing config
                                existing = values[key]
                                file_nested = file_config[key]
                                merged = {**existing.dict(), **file_nested}
                                values[key] = config_class(**merged)
                            else:
                                values[key] = config_class(**file_config[key])
                    
                    # Update top-level values
                    for key, value in file_config.items():
                        if key not in ['neo4j', 'lmstudio', 'extraction', 'metadata_storage', 'logging']:
                            values[key] = value
                            
            except Exception as e:
                raise ValueError(f"Failed to load config file {config_file}: {e}")
        
        return values
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate the complete configuration.
        
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Validate Neo4j connection
            if not self.neo4j.uri:
                validation_results['errors'].append("Neo4j URI is required")
                validation_results['valid'] = False
            
            # Validate LM Studio connection
            if not self.lmstudio.base_url:
                validation_results['errors'].append("LM Studio base URL is required")
                validation_results['valid'] = False
            
            # Validate file paths
            if self.metadata_storage.duckdb_path != ":memory:":
                duckdb_dir = Path(self.metadata_storage.duckdb_path).parent
                if not duckdb_dir.exists():
                    validation_results['warnings'].append(f"DuckDB directory {duckdb_dir} does not exist")
            
            if self.logging.file_enabled and self.logging.file_path:
                log_dir = Path(self.logging.file_path).parent
                if not log_dir.exists():
                    validation_results['warnings'].append(f"Log directory {log_dir} does not exist")
            
            # Validate thresholds
            if self.extraction.confidence_threshold > self.extraction.relationship_threshold:
                validation_results['warnings'].append(
                    "Confidence threshold is higher than relationship threshold"
                )
            
            # Check for potential performance issues
            if self.extraction.batch_size > 5000:
                validation_results['warnings'].append("Large batch size may impact performance")
            
            if self.extraction.max_workers > 8:
                validation_results['warnings'].append("High worker count may cause resource issues")
                
        except Exception as e:
            validation_results['errors'].append(f"Validation error: {str(e)}")
            validation_results['valid'] = False
        
        return validation_results
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """Update configuration at runtime.
        
        Args:
            updates: Dictionary with configuration updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            for key, value in updates.items():
                if hasattr(self, key):
                    if isinstance(value, dict) and hasattr(self, key):
                        # Update nested config
                        current_config = getattr(self, key)
                        if hasattr(current_config, 'dict'):
                            current_dict = current_config.dict()
                            current_dict.update(value)
                            # Recreate the nested config
                            config_class = type(current_config)
                            setattr(self, key, config_class(**current_dict))
                    else:
                        # Update top-level config
                        setattr(self, key, value)
            
            # Validate updated config
            validation = self.validate_config()
            if not validation['valid']:
                logging.error(f"Configuration validation failed: {validation['errors']}")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to update configuration: {e}")
            return False
    
    def get_neo4j_connection_string(self) -> str:
        """Get Neo4j connection string.
        
        Returns:
            Formatted connection string
        """
        return f"{self.neo4j.uri} (user: {self.neo4j.username}, db: {self.neo4j.database})"
    
    def get_llm_server_endpoint(self, endpoint: str = "") -> str:
        """Get LLM Server API endpoint URL.
        
        Args:
            endpoint: API endpoint path
            
        Returns:
            Full endpoint URL
        """
        return f"{self.lmstudio.base_url}/v1/{endpoint.lstrip('/')}"
    
    def export_config(self, output_path: str, format: str = "yaml") -> bool:
        """Export configuration to file.
        
        Args:
            output_path: Output file path
            format: Export format (yaml or json)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config_data = self.dict()
            
            if format.lower() == "yaml":
                with open(output_path, 'w') as f:
                    yaml.dump(config_data, f, default_flow_style=False, indent=2)
            elif format.lower() == "json":
                import json
                with open(output_path, 'w') as f:
                    json.dump(config_data, f, indent=2, default=str)
            else:
                raise ValueError("Format must be 'yaml' or 'json'")
            
            logging.info(f"Configuration exported to {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to export configuration: {e}")
            return False
    
    def setup_logging(self):
        """Setup logging based on configuration."""
        log_config = self.logging
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_config.level),
            format=log_config.format,
            force=True
        )
        
        # Add file handler if enabled
        if log_config.file_enabled and log_config.file_path:
            from logging.handlers import RotatingFileHandler
            
            file_handler = RotatingFileHandler(
                log_config.file_path,
                maxBytes=log_config.max_file_size_mb * 1024 * 1024,
                backupCount=log_config.backup_count
            )
            
            if log_config.json_format:
                import json
                formatter = logging.Formatter('%(message)s')
                file_handler.setFormatter(formatter)
            else:
                formatter = logging.Formatter(log_config.format)
                file_handler.setFormatter(formatter)
            
            logging.getLogger().addHandler(file_handler)
        
        # Set specific logger levels
        logging.getLogger('neo4j').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        
        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get configuration summary.
        
        Returns:
            Dictionary with configuration summary
        """
        return {
            'environment': self.environment,
            'neo4j_uri': self.neo4j.uri,
            'llm_server_model': self.lmstudio.model_name,
            'confidence_threshold': self.extraction.confidence_threshold,
            'batch_size': self.extraction.batch_size,
            'duckdb_path': self.metadata_storage.duckdb_path,
            'log_level': self.logging.level,
            'debug_mode': self.debug
        }


def load_config(config_file: Optional[str] = None, 
                environment: Optional[str] = None) -> OntologyExtractionConfig:
    """Load configuration from file and environment variables.
    
    Args:
        config_file: Path to configuration file
        environment: Environment name
        
    Returns:
        Loaded configuration object
    """
    # Set environment variable for config file if provided
    if config_file:
        os.environ['ONTOLOGY_CONFIG_FILE'] = config_file
    
    # Set environment if provided
    if environment:
        os.environ['ONTOLOGY_ENVIRONMENT'] = environment
    
    # Load configuration
    config = OntologyExtractionConfig()
    
    # Setup logging
    config.setup_logging()
    
    # Validate configuration
    validation = config.validate_config()
    if not validation['valid']:
        logging.error(f"Configuration validation failed: {validation['errors']}")
        raise ValueError("Invalid configuration")
    
    if validation['warnings']:
        logging.warning(f"Configuration warnings: {validation['warnings']}")
    
    logging.info("Configuration loaded successfully")
    return config


def create_default_config(output_path: str = "config.yaml") -> bool:
    """Create a default configuration file.
    
    Args:
        output_path: Output file path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        config = OntologyExtractionConfig()
        return config.export_config(output_path, "yaml")
    except Exception as e:
        logging.error(f"Failed to create default config: {e}")
        return False
