"""Canonical context models for C4 Level-1 metadata snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha1
from typing import Any, Optional

from pydantic import BaseModel, Field


class CanonicalEntityType(str, Enum):
    """Supported canonical entity types for Level-1 context."""

    SOFTWARE_SYSTEM = "SoftwareSystem"
    EXTERNAL_SYSTEM = "ExternalSystem"
    ORGANIZATION_UNIT = "OrganizationUnit"
    PERSON = "Person"
    DATA_STORE = "DataStore"


class CanonicalRelationshipType(str, Enum):
    """Supported relationship taxonomy for Level-1 context."""

    USES = "uses"
    DEPENDS_ON = "depends_on"
    PUBLISHES_EVENTS_TO = "publishes_events_to"
    CONSUMES_FROM = "consumes_from"
    INTEGRATES_WITH = "integrates_with"
    OWNED_BY = "owned_by"


class OverrideStatus(str, Enum):
    """Lifecycle state for persisted field overrides."""

    ACTIVE = "active"
    STALE = "stale"
    SUPERSEDED = "superseded"


class FieldCandidate(BaseModel):
    """Extracted candidate value for a canonical field."""

    field_name: str
    value: Any = None
    source_type: str
    source_path: str = ""
    source_hash: str = ""
    artifact_version: str = ""
    extraction_rule: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FieldProvenance(BaseModel):
    """Provenance details attached to a generated field."""

    source_type: str
    source_path: str = ""
    source_hash: str = ""
    artifact_version: str = ""
    extraction_rule: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CanonicalFieldValue(BaseModel):
    """Generated canonical field value with provenance."""

    value: Any = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provenance: list[FieldProvenance] = Field(default_factory=list)
    contested: bool = False


class CanonicalEntity(BaseModel):
    """Canonical representation of a Level-1 entity."""

    entity_id: str
    entity_type: CanonicalEntityType
    name: str
    fields: dict[str, CanonicalFieldValue] = Field(default_factory=dict)


class CanonicalRelationship(BaseModel):
    """Canonical relationship between two entities."""

    relationship_id: str
    source_entity_id: str
    relation_type: CanonicalRelationshipType
    target_entity_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: list[FieldProvenance] = Field(default_factory=list)


class CanonicalSnapshot(BaseModel):
    """Versioned canonical snapshot for a system."""

    system_id: str
    snapshot_id: str
    extracted_at: datetime
    entities: list[CanonicalEntity] = Field(default_factory=list)
    relationships: list[CanonicalRelationship] = Field(default_factory=list)


class FieldOverride(BaseModel):
    """User override for a generated field path."""

    system_id: str
    field_path: str
    value: Any = None
    status: OverrideStatus = OverrideStatus.ACTIVE
    needs_review: bool = False
    updated_by: str = "system"
    field_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    override_reason: str = ""
    last_generated_value: Any = None
    last_generated_confidence: float = 0.0
    last_generated_source_rank: int = 999


class EffectiveFieldValue(BaseModel):
    """Merged view for generated and overridden field values."""

    generated: Optional[CanonicalFieldValue] = None
    override: Optional[FieldOverride] = None
    effective: Any = None
    state: str = "missing"


def deterministic_id(*parts: str) -> str:
    """Create stable deterministic IDs from normalized string parts."""
    normalized = "|".join(part.strip().lower() for part in parts if part is not None)
    return sha1(normalized.encode("utf-8")).hexdigest()[:16]

