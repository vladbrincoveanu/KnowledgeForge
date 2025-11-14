"""Data models for code-native extraction."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Type of source from which entities are extracted."""
    CSV = "csv"
    CODE = "code"
    CONFIG = "config"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    CICD = "cicd"
    IAC = "iac"
    LOCKFILE = "lockfile"


class CodeLanguage(str, Enum):
    """Programming languages supported."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CSHARP = "csharp"
    GO = "go"
    RUST = "rust"
    RUBY = "ruby"
    PHP = "php"
    KOTLIN = "kotlin"
    SWIFT = "swift"
    CPP = "cpp"
    UNKNOWN = "unknown"


class CodeEntityType(str, Enum):
    """Types of entities extracted from code."""
    # Code-level
    CLASS = "class"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    MODULE = "module"
    PACKAGE = "package"
    NAMESPACE = "namespace"
    VARIABLE = "variable"
    CONSTANT = "constant"
    
    # Dependency-level
    DEPENDENCY = "dependency"
    IMPORT = "import"
    LIBRARY = "library"
    
    # Infrastructure
    SERVICE = "service"
    CONTAINER = "container"
    POD = "pod"
    DEPLOYMENT = "deployment"
    VOLUME = "volume"
    NETWORK = "network"
    
    # Configuration
    CONFIG_FILE = "config_file"
    ENV_VAR = "env_var"
    SECRET = "secret"
    
    # CI/CD
    PIPELINE = "pipeline"
    JOB = "job"
    STEP = "step"
    TRIGGER = "trigger"
    
    # IaC
    RESOURCE = "resource"
    MODULE_REF = "module_ref"
    DATA_SOURCE = "data_source"


class CodeRelationType(str, Enum):
    """Types of relationships between code entities."""
    # Code relationships
    INHERITS_FROM = "inherits_from"
    IMPLEMENTS = "implements"
    CALLS = "calls"
    IMPORTS = "imports"
    USES = "uses"
    DEPENDS_ON = "depends_on"
    CONTAINS = "contains"
    EXTENDS = "extends"
    
    # Infrastructure relationships
    DEPLOYS = "deploys"
    EXPOSES = "exposes"
    MOUNTS = "mounts"
    CONNECTS_TO = "connects_to"
    RUNS_ON = "runs_on"
    
    # Configuration relationships
    CONFIGURES = "configures"
    REFERENCES = "references"
    DEFINES = "defines"
    
    # CI/CD relationships
    TRIGGERS = "triggers"
    BUILDS = "builds"
    TESTS = "tests"
    DEPLOYS_TO = "deploys_to"
    
    # Generic
    RELATED_TO = "related_to"


class SourceFile(BaseModel):
    """Represents a source file in the repository."""
    path: str = Field(..., description="Relative path from repository root")
    language: CodeLanguage = Field(default=CodeLanguage.UNKNOWN)
    source_type: SourceType = Field(..., description="Type of source file")
    size_bytes: int = Field(default=0)
    last_modified: Optional[datetime] = None
    content_hash: str = Field(..., description="SHA256 hash of file content for change detection")
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodeEntity(BaseModel):
    """Represents an entity extracted from code."""
    id: Optional[str] = Field(None, description="Deterministic ID based on file path and entity signature")
    name: str = Field(..., description="Entity name (e.g., class name, function name)")
    entity_type: CodeEntityType
    language: CodeLanguage = Field(default=CodeLanguage.UNKNOWN)
    source_type: SourceType
    
    # Location information
    file_path: str = Field(..., description="Source file path")
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    
    # Entity details
    signature: Optional[str] = Field(None, description="Full signature (for functions/methods)")
    documentation: Optional[str] = Field(None, description="Docstring or comment")
    modifiers: list[str] = Field(default_factory=list, description="public, private, static, etc.")
    
    # Relationships
    parent_entity_id: Optional[str] = Field(None, description="Parent entity (e.g., class for method)")
    
    # Metadata
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")
    
    # Provenance
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extractor_version: str = Field(default="1.0.0")


class CodeRelationship(BaseModel):
    """Represents a relationship between code entities."""
    id: Optional[str] = Field(None, description="Deterministic ID")
    source_entity_id: str
    target_entity_id: str
    relationship_type: CodeRelationType
    
    # Relationship details
    direction: str = Field(default="forward", description="forward, bidirectional, reverse")
    strength: float = Field(default=1.0, ge=0.0, le=1.0, description="Relationship strength")
    
    # Context
    context: Optional[str] = Field(None, description="Code context where relationship appears")
    line_number: Optional[int] = None
    
    # Metadata
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Provenance
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


class DependencyInfo(BaseModel):
    """Represents a dependency extracted from lockfiles or configs."""
    name: str
    version: Optional[str] = None
    version_spec: Optional[str] = Field(None, description="Version specifier (e.g., ^1.2.3, >=2.0.0)")
    language: CodeLanguage
    source_file: str = Field(..., description="File where dependency is declared")
    dependency_type: str = Field(default="runtime", description="runtime, dev, build, test, etc.")
    resolved_version: Optional[str] = Field(None, description="Resolved version from lockfile")
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositoryMetadata(BaseModel):
    """Metadata about the scanned repository."""
    repo_path: str = Field(..., description="Path to repository root")
    repo_name: Optional[str] = None
    branch: Optional[str] = None
    commit_hash: Optional[str] = None
    scan_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Repository statistics
    total_files: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    languages_detected: list[CodeLanguage] = Field(default_factory=list)
    
    # File counts by type
    file_counts: dict[str, int] = Field(default_factory=dict)
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Complete extraction result from a repository scan."""
    repository: RepositoryMetadata
    files: list[SourceFile]
    entities: list[CodeEntity]
    relationships: list[CodeRelationship]
    dependencies: list[DependencyInfo]
    
    # Statistics
    extraction_duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncrementalScanResult(BaseModel):
    """Result of an incremental scan showing changes."""
    added_entities: list[CodeEntity] = Field(default_factory=list)
    modified_entities: list[CodeEntity] = Field(default_factory=list)
    deleted_entity_ids: list[str] = Field(default_factory=list)
    
    added_relationships: list[CodeRelationship] = Field(default_factory=list)
    modified_relationships: list[CodeRelationship] = Field(default_factory=list)
    deleted_relationship_ids: list[str] = Field(default_factory=list)
    
    unchanged_entity_count: int = 0
    unchanged_relationship_count: int = 0
    
    scan_timestamp: datetime = Field(default_factory=datetime.utcnow)
    previous_scan_timestamp: Optional[datetime] = None

