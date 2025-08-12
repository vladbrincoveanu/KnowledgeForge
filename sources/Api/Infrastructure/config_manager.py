"""
Configuration Manager

Infrastructure layer component for managing application configuration.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration from JSON files."""
    
    def __init__(self, config_path: str = "config.json", default_config_path: str = "config.default.json"):
        """
        Initialize configuration manager.
        
        Args:
            config_path (str): Path to the main configuration file
            default_config_path (str): Path to the default configuration template
        """
        self.config_path = Path(config_path)
        self.default_config_path = Path(default_config_path)
        self._config: Optional[Dict[str, Any]] = None
        
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Returns:
            Dict[str, Any]: Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if self._config is not None:
            return self._config
            
        # Try to load the main config file
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
                logger.info(f"Configuration loaded from {self.config_path}")
                return self._config
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {self.config_path}: {e}")
                raise
        else:
            # If main config doesn't exist, try to create it from default
            if self.default_config_path.exists():
                logger.warning(f"Config file {self.config_path} not found. Creating from default template.")
                self._create_config_from_default()
                return self.load_config()
            else:
                raise FileNotFoundError(f"Neither {self.config_path} nor {self.default_config_path} found")
    
    def _create_config_from_default(self):
        """Create config.json from config.default.json template."""
        try:
            with open(self.default_config_path, 'r') as f:
                default_config = json.load(f)
            
            # Create the config file with default values
            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            
            logger.info(f"Created {self.config_path} from default template")
            logger.warning("Please update config.json with your actual values!")
            
        except Exception as e:
            logger.error(f"Failed to create config from default: {e}")
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key (str): Configuration key (e.g., 'database.mongodb.connection_string')
            default (Any): Default value if key not found
            
        Returns:
            Any: Configuration value
        """
        config = self.load_config()
        keys = key.split('.')
        value = config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        # Prioritize environment variables over config file
        connection_string = os.getenv('MONGODB_URI') or self.get('database.mongodb.connection_string')
        database_name = os.getenv('MONGODB_DATABASE') or self.get('database.mongodb.database_name')
        
        return {
            'connection_string': connection_string,
            'database_name': database_name,
            'max_pool_size': self.get('database.mongodb.max_pool_size', 10),
            'min_pool_size': self.get('database.mongodb.min_pool_size', 1)
        }
    
    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration."""
        # Prioritize environment variables over config file
        connection_string = os.getenv('REDIS_URL') or self.get('cache.redis.connection_string')
        
        return {
            'connection_string': connection_string,
            'max_connections': self.get('cache.redis.max_connections', 20),
            'timeout': self.get('cache.redis.timeout', 30)
        }
    
    def get_storage_config(self) -> Dict[str, Any]:
        """Get storage configuration."""
        # Prioritize environment variables over config file
        endpoint = os.getenv('MINIO_ENDPOINT') or self.get('storage.minio.endpoint')
        access_key = os.getenv('MINIO_ACCESS_KEY') or self.get('storage.minio.access_key')
        secret_key = os.getenv('MINIO_SECRET_KEY') or self.get('storage.minio.secret_key')
        
        return {
            'endpoint': endpoint,
            'access_key': access_key,
            'secret_key': secret_key,
            'bucket_name': self.get('storage.minio.bucket_name'),
            'use_ssl': self.get('storage.minio.use_ssl', False)
        }
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration."""
        return {
            'host': self.get('api.host', '0.0.0.0'),
            'port': self.get('api.port', 8000),
            'debug': self.get('api.debug', False),
            'cors_origins': self.get('api.cors_origins', ['*']),
            'rate_limit': self.get('api.rate_limit', {})
        }
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return {
            'level': self.get('logging.level', 'INFO'),
            'format': self.get('logging.format'),
            'file': self.get('logging.file'),
            'max_size': self.get('logging.max_size', '10MB'),
            'backup_count': self.get('logging.backup_count', 5)
        }
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration."""
        return {
            'jwt_secret': self.get('security.jwt_secret'),
            'jwt_expiration': self.get('security.jwt_expiration', 3600),
            'bcrypt_rounds': self.get('security.bcrypt_rounds', 12),
            'session_timeout': self.get('security.session_timeout', 1800)
        }
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration."""
        return {
            'max_file_size': self.get('processing.max_file_size', '100MB'),
            'allowed_extensions': self.get('processing.allowed_extensions', ['.csv', '.xlsx', '.xls']),
            'batch_size': self.get('processing.batch_size', 1000),
            'timeout': self.get('processing.timeout', 300)
        }
    
    def reload(self):
        """Reload configuration from file."""
        self._config = None
        return self.load_config()


# Global configuration instance
config_manager = ConfigManager() 