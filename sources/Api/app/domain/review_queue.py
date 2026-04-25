"""Write review items to PostgreSQL from the extraction pipeline."""

import logging
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.models import ReviewItemModel

logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql://knowledgeforge:knowledgeforge123@postgres:5432/knowledgeforge"
_engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
_SessionLocal = sessionmaker(bind=_engine)


def enqueue_review_item(
    extraction_run_id: str,
    field: str,
    candidate_values: list[str],
    llm_suggestion: str | None,
    confidence: float,
    evidence: list[dict],
) -> str:
    """Write a single review item to PostgreSQL. Returns the item ID."""
    session = _SessionLocal()
    try:
        item = ReviewItemModel(
            id=uuid4(),
            extraction_run_id=extraction_run_id,
            field=field,
            candidate_values=candidate_values,
            llm_suggestion=llm_suggestion,
            confidence=confidence,
            evidence=evidence,
            status="PENDING",
        )
        session.add(item)
        session.commit()
        return str(item.id)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def enqueue_review_item_if_low_confidence(
    extraction_run_id: str,
    field: str,
    candidate_values: list[str],
    llm_suggestion: str | None,
    confidence: float,
    evidence: list[dict],
    threshold: float = 0.70,
) -> str | None:
    """Enqueue only if confidence is below threshold. Returns item ID or None."""
    if confidence >= threshold:
        return None
    return enqueue_review_item(
        extraction_run_id=extraction_run_id,
        field=field,
        candidate_values=candidate_values,
        llm_suggestion=llm_suggestion,
        confidence=confidence,
        evidence=evidence,
    )