"""Repository scanner orchestrator."""

import asyncio
import hashlib
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from domain.models.code_entities import (
    CodeEntity,
    CodeLanguage,
    CodeRelationship,
    DependencyInfo,
    ExtractionResult,
    IncrementalScanResult,
    RepositoryMetadata,
    SourceFile,
)
from services.code_extraction.base_extractor import BaseExtractor
from services.code_extraction.layer1_code import (
    CICDExtractor,
    ConfigExtractor,
    DockerExtractor,
    IaCExtractor,
    JavaScriptExtractor,
    PythonExtractor,
    KubernetesExtractor,
)

logger = logging.getLogger(__name__)


class RepositoryScanner:
    """Scan a repository and extract code entities and relationships."""
    
    DEFAULT_IGNORE_PATTERNS = [
        '.git', '.gitignore',
        '__pycache__', '*.pyc', '*.pyo', '*.pyd',
        'node_modules', '.npm',
        'venv', 'env', '.env', '.venv',
        'dist', 'build', 'target', 'out',
        '.idea', '.vscode', '.vs',
        '*.egg-info', '.eggs',
        '.pytest_cache', '.tox', '.coverage',
        '*.log', 'logs',
        '.DS_Store', 'Thumbs.db',
        '*.min.js', '*.min.css',
        '*.map', '*.chunk.js',
        'vendor', 'vendors',
    ]
    
    def __init__(
        self,
        repo_path: Path,
        ignore_patterns: Optional[list[str]] = None,
        max_file_size_mb: float = 10.0
    ):
        """
        Initialize repository scanner.
        
        Args:
            repo_path: Path to repository root
            ignore_patterns: Additional patterns to ignore (merged with defaults)
            max_file_size_mb: Maximum file size to process (in MB)
        """
        self.repo_path = Path(repo_path).resolve()
        self.max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)
        
        # Combine default and custom ignore patterns
        self.ignore_patterns = self.DEFAULT_IGNORE_PATTERNS.copy()
        if ignore_patterns:
            self.ignore_patterns.extend(ignore_patterns)
        
        # Initialize extractors
        self.extractors: list[BaseExtractor] = [
            PythonExtractor(self.repo_path),
            JavaScriptExtractor(self.repo_path),
            DockerExtractor(self.repo_path),
            ConfigExtractor(self.repo_path),
            CICDExtractor(self.repo_path),
            KubernetesExtractor(self.repo_path),
            IaCExtractor(self.repo_path),
        ]
        
        # Storage for results
        self.entities: list[CodeEntity] = []
        self.relationships: list[CodeRelationship] = []
        self.dependencies: list[DependencyInfo] = []
        self.source_files: list[SourceFile] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.last_result: Optional[ExtractionResult] = None
        self.last_incremental_result: Optional[IncrementalScanResult] = None
        
        # Previous scan state for incremental scanning
        self.previous_scan_data: Optional[dict[str, Any]] = None
    
    def scan(self, force_full: bool = False) -> ExtractionResult:
        """
        Scan the repository and extract all entities.
        
        Args:
            force_full: Force a full scan even if previous scan data exists
            
        Returns:
            ExtractionResult with all extracted data
        """
        self._reset_state()
        start_time = datetime.now()
        
        logger.info(f"Starting repository scan: {self.repo_path}")
        
        # Get repository metadata
        repo_metadata = self._get_repository_metadata()
        
        # Manage previous scan data depending on mode
        # Note: previous_scan_data may already be set by incremental_scan()
        if force_full:
            self.previous_scan_data = None
        elif self.previous_scan_data is None:
            self.previous_scan_data = self._load_previous_scan()
        
        # Collect all files to process
        files_to_process = self._collect_files()
        
        logger.info(f"Found {len(files_to_process)} files to process")
        
        # Process each file
        for file_path in files_to_process:
            self._process_file(file_path)
        
        # Collect dependencies from config extractors
        for extractor in self.extractors:
            if isinstance(extractor, ConfigExtractor):
                self.dependencies.extend(extractor.dependencies)
        
        # Update repository metadata with statistics
        repo_metadata.total_files = len(self.source_files)
        repo_metadata.total_entities = len(self.entities)
        repo_metadata.total_relationships = len(self.relationships)
        repo_metadata.languages_detected = list(set(e.language for e in self.entities))
        
        # Count files by type
        file_counts: dict[str, int] = {}
        for source_file in self.source_files:
            source_type = source_file.source_type.value
            file_counts[source_type] = file_counts.get(source_type, 0) + 1
        repo_metadata.file_counts = file_counts
        
        # Calculate extraction duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Create extraction result
        result = ExtractionResult(
            repository=repo_metadata,
            files=self.source_files,
            entities=self.entities,
            relationships=self.relationships,
            dependencies=self.dependencies,
            extraction_duration_seconds=duration,
            errors=self.errors,
            warnings=self.warnings,
        )
        self.last_result = result
        
        # Save scan data for incremental scanning
        self._save_scan_data(result)
        
        logger.info(
            f"Scan complete: {len(self.entities)} entities, "
            f"{len(self.relationships)} relationships, "
            f"{len(self.dependencies)} dependencies in {duration:.2f}s"
        )
        
        return result
    
    def incremental_scan(self) -> IncrementalScanResult:
        """
        Perform an incremental scan, detecting changes since last scan.
        
        Returns:
            IncrementalScanResult with added/modified/deleted entities
        """
        logger.info("Starting incremental scan")
        
        # Load previous scan data BEFORE resetting state
        previous_scan_data = self._load_previous_scan()
        if not previous_scan_data:
            logger.warning("No previous scan data found, performing baseline scan")
            result = self.scan(force_full=True)
            return IncrementalScanResult(
                added_entities=result.entities,
                modified_entities=[],
                deleted_entity_ids=[],
                added_relationships=result.relationships,
                modified_relationships=[],
                deleted_relationship_ids=[],
                unchanged_entity_count=0,
                unchanged_relationship_count=0,
                previous_scan_timestamp=None,
            )
        
        # Store previous scan data so scan() can use it for comparison
        self.previous_scan_data = previous_scan_data
        
        # Perform scan (will preserve previous_scan_data for diff computation)
        current_scan = self.scan(force_full=False)
        
        # Compute diff using the preserved previous scan data
        diff_result = self._compute_diff(current_scan)
        
        # Store the diff result for later retrieval
        self.last_incremental_result = diff_result
        
        return diff_result

    def _reset_state(self) -> None:
        """Reset accumulated scan state before processing."""
        self.entities = []
        self.relationships = []
        self.dependencies = []
        self.source_files = []
        self.errors = []
        self.warnings = []
        self.last_result = None
        
        for extractor in self.extractors:
            reset_method = getattr(extractor, "reset", None)
            if callable(reset_method):
                reset_method()
    
    def _collect_files(self) -> list[Path]:
        """Collect all files to process, respecting ignore patterns."""
        files: list[Path] = []
        
        for file_path in self.repo_path.rglob('*'):
            if not file_path.is_file():
                continue
            
            # Check if file should be ignored
            if self._should_ignore(file_path):
                continue
            
            # Check file size
            try:
                if file_path.stat().st_size > self.max_file_size_bytes:
                    self.warnings.append(f"Skipping large file: {file_path}")
                    continue
            except Exception:
                continue
            
            files.append(file_path)
        
        return files
    
    def _should_ignore(self, file_path: Path) -> bool:
        """Check if file should be ignored based on patterns."""
        rel_path = str(file_path.relative_to(self.repo_path))
        
        for pattern in self.ignore_patterns:
            # Simple pattern matching (could be enhanced with fnmatch)
            if pattern in rel_path or rel_path.endswith(pattern.replace('*', '')):
                return True
        
        return False
    
    def _process_file(self, file_path: Path) -> None:
        """Process a single file with appropriate extractor."""
        try:
            # Find appropriate extractor
            for extractor in self.extractors:
                if extractor.can_handle(file_path):
                    logger.debug(f"Processing {file_path} with {extractor.__class__.__name__}")
                    
                    entities, relationships = extractor.extract(file_path)
                    
                    self.entities.extend(entities)
                    self.relationships.extend(relationships)
                    
                    # Create source file entry
                    rel_path = str(file_path.relative_to(self.repo_path))
                    source_file = extractor.create_source_file(
                        file_path,
                        entities[0].language if entities else CodeLanguage.UNKNOWN,
                        entities[0].source_type if entities else extractor._detect_source_type(file_path)
                    )
                    self.source_files.append(source_file)
                    
                    # Collect errors
                    self.errors.extend(extractor.errors)
                    self.warnings.extend(extractor.warnings)
                    extractor.errors = []
                    extractor.warnings = []
                    
                    break
        
        except Exception as e:
            self.errors.append(f"Failed to process {file_path}: {e}")
            logger.error(f"Failed to process {file_path}: {e}", exc_info=True)
    
    def _get_repository_metadata(self) -> RepositoryMetadata:
        """Extract repository metadata (git info, etc.)."""
        metadata = RepositoryMetadata(
            repo_path=str(self.repo_path),
            repo_name=self.repo_path.name,
        )
        
        # Try to get git information
        try:
            # Get current branch
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                metadata.branch = result.stdout.strip()
            
            # Get commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                metadata.commit_hash = result.stdout.strip()
        
        except Exception as e:
            logger.debug(f"Failed to get git info: {e}")
        
        return metadata
    
    def _load_previous_scan(self) -> Optional[dict[str, Any]]:
        """Load previous scan data from cache file."""
        cache_file = self.repo_path / '.knowledgeforge' / 'last_scan.json'
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load previous scan data: {e}")
            return None
    
    def _save_scan_data(self, result: ExtractionResult) -> None:
        """Save scan data for future incremental scans."""
        cache_dir = self.repo_path / '.knowledgeforge'
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        cache_file = cache_dir / 'last_scan.json'
        
        try:
            # Create simplified scan data
            scan_data = {
                'timestamp': result.repository.scan_timestamp.isoformat(),
                'commit_hash': result.repository.commit_hash,
                'files': {
                    f.path: f.content_hash
                    for f in result.files
                },
                'entities': {
                    e.id: {
                        'name': e.name,
                        'type': e.entity_type.value,
                        'file': e.file_path,
                        'hash': self._hash_entity(e),
                    }
                    for e in result.entities if e.id
                },
                'relationships': {
                    r.id: {
                        'source': r.source_entity_id,
                        'target': r.target_entity_id,
                        'type': r.relationship_type.value,
                    }
                    for r in result.relationships if r.id
                },
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(scan_data, f, indent=2)
        
        except Exception as e:
            logger.warning(f"Failed to save scan data: {e}")
    
    def _compute_diff(self, current_scan: ExtractionResult) -> IncrementalScanResult:
        """Compute difference between current and previous scan."""
        if not self.previous_scan_data:
            return IncrementalScanResult(
                added_entities=current_scan.entities,
                added_relationships=current_scan.relationships,
            )
        
        prev_entities = self.previous_scan_data.get('entities', {})
        prev_relationships = self.previous_scan_data.get('relationships', {})
        
        # Build current entity/relationship maps
        current_entities = {e.id: e for e in current_scan.entities if e.id}
        current_relationships = {r.id: r for r in current_scan.relationships if r.id}
        
        # Find added entities
        added_entities = [
            e for e in current_scan.entities
            if e.id and e.id not in prev_entities
        ]
        
        # Find modified entities
        modified_entities = [
            e for e in current_scan.entities
            if e.id and e.id in prev_entities and
            self._hash_entity(e) != prev_entities[e.id].get('hash')
        ]
        
        # Find deleted entities
        deleted_entity_ids = [
            entity_id for entity_id in prev_entities.keys()
            if entity_id not in current_entities
        ]
        
        # Find added relationships
        added_relationships = [
            r for r in current_scan.relationships
            if r.id and r.id not in prev_relationships
        ]
        
        # Find deleted relationships
        deleted_relationship_ids = [
            rel_id for rel_id in prev_relationships.keys()
            if rel_id not in current_relationships
        ]
        
        unchanged_entity_count = len(current_entities) - len(added_entities) - len(modified_entities)
        unchanged_relationship_count = len(current_relationships) - len(added_relationships)
        
        return IncrementalScanResult(
            added_entities=added_entities,
            modified_entities=modified_entities,
            deleted_entity_ids=deleted_entity_ids,
            added_relationships=added_relationships,
            modified_relationships=[],
            deleted_relationship_ids=deleted_relationship_ids,
            unchanged_entity_count=unchanged_entity_count,
            unchanged_relationship_count=unchanged_relationship_count,
            previous_scan_timestamp=datetime.fromisoformat(
                self.previous_scan_data.get('timestamp', datetime.now().isoformat())
            ),
        )
    
    def _hash_entity(self, entity: CodeEntity) -> str:
        """Compute hash of entity for change detection."""
        content = f"{entity.name}:{entity.entity_type}:{entity.file_path}:{entity.line_start}:{entity.line_end}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


# Add this method to BaseExtractor
def _detect_source_type_impl(self, file_path: Path):
    """Detect source type from file path."""
    from app.domain.models.code_entities import SourceType
    
    if 'docker' in file_path.name.lower() or file_path.name.lower() == 'dockerfile':
        return SourceType.DOCKER
    elif '.github' in str(file_path) or '.gitlab' in str(file_path) or file_path.name == 'Jenkinsfile':
        return SourceType.CICD
    elif file_path.suffix in ['.json', '.toml', '.yaml', '.yml', '.xml', '.lock', '.txt']:
        return SourceType.CONFIG
    else:
        return SourceType.CODE

# Monkey-patch the method onto BaseExtractor
BaseExtractor._detect_source_type = _detect_source_type_impl
