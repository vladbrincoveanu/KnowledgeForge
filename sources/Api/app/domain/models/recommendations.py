from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class NodeRecommendation(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    recommended_name: str
    entity_type: str
    confidence_score: float
    reasoning: str
    source_columns: List[str] = Field(default_factory=list)
    llm_metadata: Optional[dict[str, Any]] = None
    user_feedback: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EdgeRecommendation(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relationship_type: str
    confidence_score: float
    reasoning: str
    connection_evidence: Optional[dict[str, Any]] = None
    user_feedback: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RecommendationSession(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_id: str
    status: str = "pending"
    phase: str = "nodes"  # "nodes", "nodes_completed", "edges", or "completed"
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    nodes_approved_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None
    node_recommendations: List[NodeRecommendation] = Field(default_factory=list)
    edge_recommendations: List[EdgeRecommendation] = Field(default_factory=list)
