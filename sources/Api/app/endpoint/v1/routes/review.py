"""Review queue API — CRUD for HITL review items."""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.domain.models import Base, ReviewItemModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review", tags=["review"])

DATABASE_URL = "postgresql://knowledgeforge:knowledgeforge123@postgres:5432/knowledgeforge"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ReviewItemBase(BaseModel):
    field: str
    candidate_values: list[str]
    llm_suggestion: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[dict] = Field(default_factory=list)


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
    db: Session = Depends(get_db),
):
    """List all pending review items for a given extraction run."""
    items = (
        db.query(ReviewItemModel)
        .filter(
            ReviewItemModel.extraction_run_id == run_id,
            ReviewItemModel.status == "PENDING",
        )
        .order_by(ReviewItemModel.confidence.asc())
        .all()
    )
    return PendingResponse(items=[ReviewItemResponse.model_validate(i) for i in items], total=len(items))


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
    item.status = "APPROVED"
    if payload.reviewer_note:
        item.reviewer_note = payload.reviewer_note
    item.updated_at = datetime.utcnow()
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
    item.status = "REJECTED"
    if payload.reviewer_note:
        item.reviewer_note = payload.reviewer_note
    item.updated_at = datetime.utcnow()
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
    item.status = "OVERRIDDEN"
    item.llm_suggestion = payload.value
    if payload.reviewer_note:
        item.reviewer_note = payload.reviewer_note
    item.updated_at = datetime.utcnow()
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
            ReviewItemModel.status == "PENDING",
            ReviewItemModel.confidence >= payload.min_confidence,
        )
        .update(
            {"status": "APPROVED", "updated_at": datetime.utcnow()},
            synchronize_session=False,
        )
    )
    db.commit()
    return MessageResponse(message=f"Bulk approved {updated} items")