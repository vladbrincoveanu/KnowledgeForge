"""
Data models for the KnowledgeForge API.

This module contains Pydantic models for data validation and serialization.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BaseDataModel(BaseModel):
    """Base model for all data entities."""

    id: Optional[str] = Field(None, description="Unique identifier")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DataEntity(BaseDataModel):
    """Model for data entities."""

    name: str = Field(..., description="Entity name")
    type: str = Field(..., description="Entity type")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Entity properties"
    )
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score")


class DataRelationship(BaseDataModel):
    """Model for data relationships."""

    source_id: str = Field(..., description="Source entity ID")
    target_id: str = Field(..., description="Target entity ID")
    relationship_type: str = Field(..., description="Type of relationship")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Relationship properties"
    )
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score")
