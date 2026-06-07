"""Review queue API — CRUD for HITL review items."""

import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.domain.models import Base, ReviewItemModel
from app.utils.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["review"])


def _build_database_url() -> str:
    config = get_config()
    db = config.database
    password = os.environ.get("POSTGRES_PASSWORD", db.password)
    host = os.environ.get("POSTGRES_HOST", db.host)
    username = os.environ.get("POSTGRES_USERNAME", db.username)
    name = os.environ.get("POSTGRES_DB", db.name)
    return f"postgresql://{username}:{password}@{host}:5432/{name}"


_database_url = os.environ.get("DATABASE_URL") or _build_database_url()
_engine = create_engine(
    _database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(bind=_engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"


# ── Schemas ────────────────────────────────────────────────────────────────────

class ReviewItemBase(BaseModel):
    field: str
    candidate_values: list[str]
    llm_suggestion: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class ReviewItemResponse(ReviewItemBase):
    id: UUID
    extraction_run_id: str
    status: str
    reviewer_note: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PendingResponse(BaseModel):
    items: list[ReviewItemResponse]
    total: int


class ApprovePayload(BaseModel):
    reviewer_note: str | None = None


class OverridePayload(BaseModel):
    value: str
    reviewer_note: str | None = None


class BulkApprovePayload(BaseModel):
    min_confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class MessageResponse(BaseModel):
    message: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/pending", response_model=PendingResponse)
def list_pending(
    run_id: Annotated[str, Query(description="Extraction run ID to filter by")],
    skip: Annotated[int, Query(description="Number of items to skip", ge=0)] = 0,
    limit: Annotated[int, Query(description="Max items to return", ge=1)] = 50,
    db: Session = Depends(get_db),
):
    """List all pending review items for a given extraction run."""
    if run_id == "latest":
        latest_run = (
            db.query(ReviewItemModel.extraction_run_id)
            .group_by(ReviewItemModel.extraction_run_id)
            .order_by(func.max(ReviewItemModel.created_at).desc())
            .first()
        )
        if latest_run is None:
            return PendingResponse(items=[], total=0)
        run_id = latest_run[0]

    items = (
        db.query(ReviewItemModel)
        .filter(
            ReviewItemModel.extraction_run_id == run_id,
            ReviewItemModel.status == ReviewStatus.PENDING.value,
        )
        .order_by(ReviewItemModel.confidence.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = (
        db.query(ReviewItemModel)
        .filter(
            ReviewItemModel.extraction_run_id == run_id,
            ReviewItemModel.status == ReviewStatus.PENDING.value,
        )
        .count()
    )
    return PendingResponse(items=[ReviewItemResponse.model_validate(i) for i in items], total=total)


@router.post("/{item_id}/approve", response_model=MessageResponse)
def approve_item(
    item_id: UUID,
    payload: ApprovePayload,
    db: Session = Depends(get_db),
):
    """Approve an item — accept the LLM suggestion or keep existing value."""
    item = db.query(ReviewItemModel).filter(ReviewItemModel.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    item.status = ReviewStatus.APPROVED.value
    if payload.reviewer_note:
        item.reviewer_note = payload.reviewer_note
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message="Item approved")


@router.post("/{item_id}/reject", response_model=MessageResponse)
def reject_item(
    item_id: UUID,
    payload: ApprovePayload,
    db: Session = Depends(get_db),
):
    """Reject an item — fallback to heuristic/deterministic value."""
    item = db.query(ReviewItemModel).filter(ReviewItemModel.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    item.status = ReviewStatus.REJECTED.value
    if payload.reviewer_note:
        item.reviewer_note = payload.reviewer_note
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message="Item rejected")


@router.post("/{item_id}/override", response_model=MessageResponse)
def override_item(
    item_id: UUID,
    payload: OverridePayload,
    db: Session = Depends(get_db),
):
    """Override — human provides the correct value directly."""
    item = db.query(ReviewItemModel).filter(ReviewItemModel.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    item.status = ReviewStatus.OVERRIDDEN.value
    item.llm_suggestion = payload.value
    if payload.reviewer_note:
        item.reviewer_note = payload.reviewer_note
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message="Item overridden")


@router.post("/{run_id}/bulk-approve", response_model=MessageResponse)
def bulk_approve(
    run_id: str,
    payload: BulkApprovePayload,
    db: Session = Depends(get_db),
):
    """Approve all pending items above the confidence threshold."""
    updated = (
        db.query(ReviewItemModel)
        .filter(
            ReviewItemModel.extraction_run_id == run_id,
            ReviewItemModel.status == ReviewStatus.PENDING.value,
            ReviewItemModel.confidence >= payload.min_confidence,
        )
        .update(
            {"status": ReviewStatus.APPROVED.value, "updated_at": datetime.now(timezone.utc)},
            synchronize_session="fetch",
        )
    )
    db.commit()
    return MessageResponse(message=f"Bulk approved {updated} items")
