# sources/Api/tests/e2e/test_hitl_review_workflow.py
"""E2E tests for the full HITL review workflow."""

import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.models import ReviewItemModel
from app.domain.review_queue import enqueue_review_item, enqueue_review_item_if_low_confidence

DATABASE_URL = "postgresql://knowledgeforge:knowledgeforge123@postgres:5432/knowledgeforge"
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(bind=engine)


class TestReviewQueueWrite:
    """Test writing review items to PostgreSQL."""

    def test_enqueue_low_confidence_item(self):
        """Low-confidence items are enqueued."""
        session = SessionLocal()
        session.query(ReviewItemModel).filter(
            ReviewItemModel.field == "test_owner"
        ).delete()
        session.commit()

        run_id = str(uuid.uuid4())
        item_id = enqueue_review_item_if_low_confidence(
            extraction_run_id=run_id,
            field="owner",
            candidate_values=["team-alpha", "team-beta"],
            llm_suggestion="team-alpha",
            confidence=0.55,
            evidence=[{"type": "codeowners", "source": "CODEOWNERS", "snippet": "* @omnipay/team-alpha"}],
            threshold=0.70,
        )

        assert item_id is not None
        item = session.query(ReviewItemModel).filter(ReviewItemModel.id == uuid.UUID(item_id)).first()
        assert item is not None
        assert item.status == "PENDING"
        assert item.field == "owner"
        session.close()

    def test_high_confidence_item_not_enqueued(self):
        """High-confidence items are NOT enqueued."""
        run_id = str(uuid.uuid4())
        result = enqueue_review_item_if_low_confidence(
            extraction_run_id=run_id,
            field="owner",
            candidate_values=["team-alpha"],
            llm_suggestion="team-alpha",
            confidence=0.92,
            evidence=[],
            threshold=0.70,
        )
        assert result is None


class TestReviewAPIEndpoints:
    """Test Review API endpoints via HTTP client."""

    @pytest.fixture
    def setup_item(self):
        """Create a pending review item for testing."""
        session = SessionLocal()
        run_id = str(uuid.uuid4())
        item = ReviewItemModel(
            id=uuid.uuid4(),
            extraction_run_id=run_id,
            field="business_domain",
            candidate_values=["Payments", "Infrastructure"],
            llm_suggestion="Payments",
            confidence=0.62,
            evidence=[{"type": "keyword", "source": "README.md", "snippet": "payment"}],
            status="PENDING",
        )
        session.add(item)
        session.commit()
        item_id = str(item.id)
        session.close()
        return item_id, run_id

    def test_list_pending(self, setup_item):
        """GET /review/pending returns items."""
        item_id, run_id = setup_item
        import requests
        resp = requests.get(f"http://localhost:8000/api/v1/review/pending?run_id={run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(i["id"] == item_id for i in data["items"])

    def test_approve_item(self, setup_item):
        """POST /review/{id}/approve changes status to APPROVED."""
        item_id, _ = setup_item
        import requests
        resp = requests.post(f"http://localhost:8000/api/v1/review/{item_id}/approve", json={})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Item approved"

    def test_reject_item(self, setup_item):
        """POST /review/{id}/reject changes status to REJECTED."""
        item_id, _ = setup_item
        import requests
        resp = requests.post(f"http://localhost:8000/api/v1/review/{item_id}/reject", json={})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Item rejected"

    def test_override_item(self, setup_item):
        """POST /review/{id}/override sets status to OVERRIDDEN with new value."""
        item_id, _ = setup_item
        import requests
        resp = requests.post(f"http://localhost:8000/api/v1/review/{item_id}/override", json={"value": "Finance"})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Item overridden"

    def test_bulk_approve(self, setup_item):
        """POST /review/{run_id}/bulk-approve approves all above threshold."""
        _, run_id = setup_item
        import requests
        resp = requests.post(f"http://localhost:8000/api/v1/review/{run_id}/bulk-approve", json={"min_confidence": 0.50})
        assert resp.status_code == 200
        assert "approved" in resp.json()["message"].lower()