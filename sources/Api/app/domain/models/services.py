"""Domain models for service extraction and service graph."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ServiceStatus(str, Enum):
    """
    Status of a service - where it is in its lifecycle.
    
    - ACTIVE_DEV: People are actively adding features
    - MAINTENANCE_ONLY: Bugfixes only, no new features
    - DEPRECATED: Scheduled for shutdown / frozen
    - UNKNOWN: Status not determined
    """
    ACTIVE_DEV = "Active-Dev"
    MAINTENANCE_ONLY = "Maintenance-Only"
    DEPRECATED = "Deprecated / Frozen"
    UNKNOWN = "unknown"


class ContextNodeType(str, Enum):
    """Types of context nodes for architecture visualization."""
    REPOSITORY = "repository"
    README = "readme"
    DOCKERFILE = "dockerfile"
    DOCKER_COMPOSE = "docker_compose"
    REQUIREMENTS = "requirements"  # Python
    PACKAGE_JSON = "package_json"  # Node.js
    CSPROJ = "csproj"  # .NET
    GEMFILE = "gemfile"  # Ruby
    GO_MOD = "go_mod"  # Go
    CARGO_TOML = "cargo_toml"  # Rust
    BUILD_GRADLE = "build_gradle"  # Java/Gradle
    POM_XML = "pom_xml"  # Java/Maven


class ServiceTier(str, Enum):
    """
    Criticality tier - how bad is it if this service breaks?
    
    - TIER_1: Site-wide outage, critical business impact
    - TIER_2: Specific journey broken, significant impact
    - TIER_3: Minor/cosmetic issues, low impact
    - UNKNOWN: Tier not determined
    """
    TIER_1 = "Tier 1"
    TIER_2 = "Tier 2"
    TIER_3 = "Tier 3"
    UNKNOWN = "unknown"


class ConnectionType(str, Enum):
    """Types of connections between services."""
    HTTP = "http"
    GRPC = "grpc"
    MESSAGE_QUEUE = "message_queue"
    DATABASE = "database"
    CACHE = "cache"
    STORAGE = "storage"
    DEPENDS_ON = "depends_on"
    CALLS = "calls"
    PUBLISHES = "publishes"
    SUBSCRIBES = "subscribes"
    UNKNOWN = "unknown"


class Service(BaseModel):
    """
    Represents a service in the system.
    
    Primary extraction fields (the 5 key attributes):
    1. domain - Business area (Revenue Core, Checkout, Identity, Logging)
    2. owner - Squad/team that owns and supports the service
    3. status - Lifecycle stage (Active-Dev, Maintenance-Only, Deprecated)
    4. tier - Criticality (Tier 1 = site-wide, Tier 2 = journey, Tier 3 = minor)
    5. data_class - Sensitive data classification (PII, Credit-Card, etc.)
    """
    id: str = Field(..., description="Unique service identifier")
    name: str = Field(..., description="Service name")
    display_name: Optional[str] = Field(None, description="Human-readable display name")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIMARY EXTRACTION FIELDS (The 5 key attributes for service metadata)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # 1. domain - Business area this service belongs to
    domain: Optional[str] = Field(
        None, 
        description="Business domain (e.g., 'Revenue Core', 'Checkout', 'Identity', 'Logging')"
    )
    
    # 2. owner - Squad/team that owns and supports the service
    owner: Optional[str] = Field(
        None, 
        description="Team or squad that owns the service (e.g., 'Growth Squad', 'Platform Team')"
    )
    owner_contributors: list[str] = Field(
        default_factory=list,
        description="Top contributors from git history (emails)"
    )
    owner_contributor_stats: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top contributors from git history with commit counts"
    )
    contributor_count: int = Field(
        default=0,
        description="Unique git contributors for this service"
    )
    
    # 3. status - Where the service is in its lifecycle
    status: ServiceStatus = Field(
        default=ServiceStatus.UNKNOWN, 
        description="Lifecycle status: Active-Dev, Maintenance-Only, or Deprecated/Frozen"
    )
    status_evidence: Optional[dict[str, Any]] = Field(
        None,
        description="Evidence for status determination (commit stats, dates, etc.)"
    )
    
    # 4. tier - Criticality level (how bad is it if this breaks?)
    tier: ServiceTier = Field(
        default=ServiceTier.UNKNOWN,
        description="Criticality: Tier 1 (site-wide), Tier 2 (journey), Tier 3 (minor)"
    )
    
    # 5. data_class - What sensitive data lives here
    data_class: Optional[str] = Field(
        None, 
        description="Data classification (e.g., 'PII', 'Credit-Card', 'Public', 'Internal')"
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ADDITIONAL METADATA (Secondary fields)
    # ═══════════════════════════════════════════════════════════════════════════
    
    description: Optional[str] = Field(None, description="Service description")
    notes: Optional[str] = Field(None, description="Short service notes")
    language: Optional[str] = Field(None, description="Primary programming language")
    framework: Optional[str] = Field(None, description="Framework used (e.g., 'FastAPI', 'Express')")
    port: Optional[int] = Field(None, description="Service port")
    endpoints: list[str] = Field(default_factory=list, description="API endpoints exposed by service")
    
    # Location information
    repository_url: Optional[str] = Field(None, description="GitHub/GitLab repository URL")
    file_path: Optional[str] = Field(None, description="Path to service definition file")
    docker_compose_service: Optional[str] = Field(None, description="Docker compose service name if applicable")
    
    # Relationships
    dependencies: list[str] = Field(default_factory=list, description="Service dependencies (other service IDs)")
    dependents: list[str] = Field(default_factory=list, description="Services that depend on this one")
    direct_depends: list[str] = Field(
        default_factory=list, 
        description="Direct service dependencies detected from imports (for graph edges)"
    )
    
    # Metadata
    attributes: dict[str, Any] = Field(default_factory=dict, description="Additional service attributes")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")
    
    # Git activity metrics
    last_commit_date: Optional[datetime] = Field(None, description="Date of last commit to this service")
    commit_count_30d: int = Field(default=0, description="Commits in last 30 days")
    commit_count_90d: int = Field(default=0, description="Commits in last 90 days")
    commit_count_180d: int = Field(default=0, description="Commits in last 180 days")

    # ═══════════════════════════════════════════════════════════════════════════
    # RISK & VULNERABILITY TRACKING (Manager-first view)
    # ═══════════════════════════════════════════════════════════════════════════

    # Field 6: Active Experts (Bus Factor)
    active_experts: int = Field(
        default=0,
        description="Number of active contributors (3+ commits in last 90 days). Bus factor indicator."
    )

    # Field 7: Compliance Risk Level (Architectural compliance, not legal/regulatory)
    compliance: Optional[str] = Field(
        default=None,
        description="Architectural compliance risk level: COMPLIANT, AT_RISK, NON_COMPLIANT, UNKNOWN. "
                    "Checks if sensitive data is properly prioritized and owned."
    )
    compliance_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence for compliance assessment (0-1)."
    )
    compliance_factors: list[str] = Field(
        default_factory=list,
        description="Factors contributing to the compliance assessment."
    )

    # Provenance
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="code_extraction", description="Source of extraction")


class ContextNode(BaseModel):
    """
    Represents a context node in the architecture graph.
    Context nodes provide additional context for managers (README, Dockerfile, etc.)
    """
    id: str = Field(..., description="Unique context node identifier")
    name: str = Field(..., description="Node name (e.g., 'README.md', 'Dockerfile')")
    type: ContextNodeType = Field(..., description="Type of context node")
    file_path: Optional[str] = Field(None, description="Path to the file")
    content_preview: Optional[str] = Field(None, description="Preview of file content (first 500 chars)")
    service_id: Optional[str] = Field(None, description="Associated service ID if applicable")
    
    # Metadata
    attributes: dict[str, Any] = Field(default_factory=dict, description="Additional attributes")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


class ServiceConnection(BaseModel):
    """Represents a connection/relationship between two services."""
    id: str = Field(..., description="Unique connection identifier")
    source_service_id: str = Field(..., description="Source service ID")
    target_service_id: str = Field(..., description="Target service ID")
    connection_type: ConnectionType = Field(..., description="Type of connection")
    
    # Connection details
    protocol: Optional[str] = Field(None, description="Protocol used (e.g., 'REST', 'GraphQL')")
    endpoint: Optional[str] = Field(None, description="Target endpoint URL")
    method: Optional[str] = Field(None, description="HTTP method if applicable")
    
    # Relationship strength
    strength: float = Field(default=1.0, ge=0.0, le=1.0, description="Connection strength/confidence")
    frequency: Optional[int] = Field(None, description="Estimated call frequency")
    
    # Context
    context: Optional[str] = Field(None, description="Context where connection was discovered")
    file_path: Optional[str] = Field(None, description="File where connection was found")
    line_number: Optional[int] = Field(None, description="Line number in source file")
    
    # Metadata
    attributes: dict[str, Any] = Field(default_factory=dict, description="Additional connection attributes")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")
    
    # Provenance
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="code_extraction", description="Source of discovery")


class ServiceGraph(BaseModel):
    """Complete service graph with services and connections."""
    services: list[Service] = Field(default_factory=list, description="All services in the graph")
    connections: list[ServiceConnection] = Field(default_factory=list, description="All connections between services")
    context_nodes: list[ContextNode] = Field(default_factory=list, description="Context nodes (README, Dockerfile, etc.)")
    
    # Metadata
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    repository_url: Optional[str] = Field(None, description="Source repository URL")
    repository_name: Optional[str] = Field(None, description="Source repository name")
    
    # Statistics
    total_services: int = Field(default=0, description="Total number of services")
    total_connections: int = Field(default=0, description="Total number of connections")
    
    def model_post_init(self, __context: Any) -> None:
        """Update statistics after initialization."""
        self.total_services = len(self.services)
        self.total_connections = len(self.connections)
