"""SQLAlchemy models for KnowledgeForge persistence."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Text, Numeric, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ReviewItemModel(Base):
    """Review queue item persisted to PostgreSQL."""

    __tablename__ = "review_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    extraction_run_id = Column(String(255), nullable=False, index=True)
    field = Column(String(100), nullable=False)
    candidate_values = Column(JSONB, nullable=False)
    llm_suggestion = Column(Text, nullable=True)
    confidence = Column(Numeric(3, 2), nullable=False)
    evidence = Column(JSONB, nullable=False, default=list)
    status = Column(String(50), nullable=False, default="PENDING", index=True)
    reviewer_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
