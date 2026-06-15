"""SQLAlchemy models for KnowledgeForge persistence."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, Index
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


class ExtractionRunModel(Base):
    """Completed C4 extraction run persisted to PostgreSQL."""

    __tablename__ = "c4_extraction_runs"

    id = Column(String(36), primary_key=True)
    repo_url = Column(Text, nullable=True)
    repo_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending", index=True)
    containers_count = Column(Integer, nullable=False, default=0)
    components_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
