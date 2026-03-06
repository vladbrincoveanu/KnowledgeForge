"""Canonical context models for C4 Level-1 (System Context)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CanonicalEntityType(str, Enum):
    """C4 Level-1 entity types."""

    SOFTWARE_SYSTEM = "SoftwareSystem"
    EXTERNAL_SYSTEM = "ExternalSystem"
    PERSON = "Person"


class CanonicalRelationshipType(str, Enum):
    """C4 Level-1 relationship types."""

    USES = "uses"
    DEPENDS_ON = "depends_on"
    INTEGRATES_WITH = "integrates_with"


class CanonicalEntity(BaseModel):
    """Canonical representation of a C4 Level-1 entity."""

    entity_id: str
    entity_type: CanonicalEntityType
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class CanonicalRelationship(BaseModel):
    """Canonical relationship between two C4 entities."""

    relationship_id: str
    source_entity_id: str
    relation_type: CanonicalRelationshipType
    target_entity_id: str
    description: str = ""
