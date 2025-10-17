"""Domain models for PostgreSQL storage entities."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class File(BaseModel):
    """Domain model for files table."""

    id: str
    file_path: str
    file_name: str
    file_size: int
    file_type: str
    checksum: str
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_status: str = "uploaded"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ExtractionRun(BaseModel):
    """Domain model for extraction_runs table."""

    id: str
    file_id: Optional[str] = None
    status: str = "pending"
    entities_count: int = 0
    relationships_count: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UserFeedback(BaseModel):
    """Domain model for user_feedback table."""

    id: str
    entity_id: Optional[str] = None
    relationship_id: Optional[str] = None
    feedback_type: str
    feedback_value: Optional[str] = None
    confidence_adjustment: float = 0.0
    user_id: Optional[str] = None
    feedback_source: str = "api"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SystemMetric(BaseModel):
    """Domain model for system_metrics table."""

    id: Optional[int] = None
    metric_name: str
    metric_value: dict[str, Any]
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

