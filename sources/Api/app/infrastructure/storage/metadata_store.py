"""Native PostgreSQL metadata store using psycopg2 for direct database operations."""

import hashlib
import json
import logging
        Args:
            database_url: PostgreSQL connection string (overrides config)
            config: Configuration dictionary with database settings
        """
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
            raise
        """Register a new file with checksum calculation."""
        try:
            checksum = self._calculate_file_checksum(file_path)

            # Check if file already exists
            logger.info(f"Registered file '{file_name}' with ID {file_id}")
            return file_id

        except Exception as e:
            logger.error(f"Failed to register file: {e}")
            raise
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of file."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return "unknown"

# Backward compatibility alias
MetadataStore = PostgreSQLMetadataStore
