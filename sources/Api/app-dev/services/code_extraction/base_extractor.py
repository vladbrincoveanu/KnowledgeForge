"""Base extractor interface for code extraction."""

import hashlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from domain.models.code_entities import (
    CodeEntity,
    CodeRelationship,
    SourceFile,
    SourceType,
    CodeLanguage,
)

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """Base class for all code extractors."""
    
    def __init__(self, repo_root: Path):
        """Initialize extractor with repository root."""
        self.repo_root = Path(repo_root)
        self.entities: list[CodeEntity] = []
        self.relationships: list[CodeRelationship] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
    
    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """Check if this extractor can handle the given file."""
        pass
    
    @abstractmethod
    def extract(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from a file."""
        pass
    
    def get_relative_path(self, file_path: Path) -> str:
        """Get relative path from repository root."""
        try:
            return str(file_path.relative_to(self.repo_root))
        except ValueError:
            return str(file_path)
    
    def compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to compute hash for {file_path}: {e}")
            return ""
    
    def generate_entity_id(self, file_path: str, entity_name: str, entity_type: str) -> str:
        """Generate deterministic entity ID."""
        content = f"{file_path}::{entity_type}::{entity_name}"
        return f"code_{hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]}"
    
    def generate_relationship_id(
        self,
        source_id: str,
        target_id: str,
        rel_type: str
    ) -> str:
        """Generate deterministic relationship ID."""
        content = f"{source_id}::{rel_type}::{target_id}"
        return f"rel_{hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]}"
    
    def create_source_file(
        self,
        file_path: Path,
        language: CodeLanguage,
        source_type: SourceType
    ) -> SourceFile:
        """Create a SourceFile model."""
        rel_path = self.get_relative_path(file_path)
        
        try:
            stat = file_path.stat()
            size_bytes = stat.st_size
            last_modified = stat.st_mtime
        except Exception:
            size_bytes = 0
            last_modified = None
        
        return SourceFile(
            path=rel_path,
            language=language,
            source_type=source_type,
            size_bytes=size_bytes,
            last_modified=last_modified,
            content_hash=self.compute_file_hash(file_path),
        )
    
    def safe_read_file(self, file_path: Path, encoding: str = 'utf-8') -> Optional[str]:
        """Safely read file content with fallback encodings."""
        encodings = [encoding, 'utf-8', 'latin-1', 'cp1252']
        
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")
                return None
        
        logger.warning(f"Could not decode {file_path} with any encoding")
        return None

    def reset(self) -> None:
        """Reset extractor-scoped caches between repository scans."""
        self.entities = []
        self.relationships = []
        self.errors = []
        self.warnings = []
