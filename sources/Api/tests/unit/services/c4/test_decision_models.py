"""Unit tests for decision models used in C4 context extraction."""

import pytest

from app.services.c4.context.decision_models import (
    DecisionMode,
    EvidenceItem,
    ExtractionDecision,
    ReviewItem,
    ReviewStatus,
)


class TestDecisionMode:
    """Test DecisionMode enum values."""

    def test_has_deterministic_mode(self):
        assert DecisionMode.DETERMINISTIC.value == "deterministic"

    def test_has_llm_adjudicated_mode(self):
        assert DecisionMode.LLM_ADJUDICATED.value == "llm_adjudicated"

    def test_has_human_reviewed_mode(self):
        assert DecisionMode.HUMAN_REVIEWED.value == "human_reviewed"


class TestReviewStatus:
    """Test ReviewStatus enum values."""

    def test_has_auto_accepted_status(self):
        assert ReviewStatus.AUTO_ACCEPTED.value == "auto_accepted"

    def test_has_needs_review_status(self):
        assert ReviewStatus.NEEDS_REVIEW.value == "needs_review"

    def test_has_approved_status(self):
        assert ReviewStatus.APPROVED.value == "approved"

    def test_has_rejected_status(self):
        assert ReviewStatus.REJECTED.value == "rejected"


class TestEvidenceItem:
    """Test EvidenceItem dataclass."""

    def test_creates_evidence_item(self):
        evidence = EvidenceItem(
            type="file_content",
            source="package.json",
            snippet='"dependencies": {"express": "^4.18.2"}',
        )
        assert evidence.type == "file_content"
        assert evidence.source == "package.json"
        assert evidence.snippet == '"dependencies": {"express": "^4.18.2"}'

    def test_to_dict_returns_serializable(self):
        evidence = EvidenceItem(
            type="env_var",
            source=".env",
            snippet="DATABASE_URL=postgresql://...",
        )
        result = evidence.to_dict()
        assert result == {
            "type": "env_var",
            "source": ".env",
            "snippet": "DATABASE_URL=postgresql://...",
        }
        # Verify it's JSON serializable
        import json
        json.dumps(result)


class TestExtractionDecision:
    """Test ExtractionDecision dataclass."""

    def test_creates_extraction_decision(self):
        decision = ExtractionDecision(
            value="active",
            confidence=0.85,
            detection_source="package_json",
            decision_mode=DecisionMode.DETERMINISTIC,
            review_status=ReviewStatus.AUTO_ACCEPTED,
        )
        assert decision.value == "active"
        assert decision.confidence == 0.85
        assert decision.detection_source == "package_json"
        assert decision.decision_mode == DecisionMode.DETERMINISTIC
        assert decision.review_status == ReviewStatus.AUTO_ACCEPTED
        assert decision.evidence == []
        assert decision.metadata == {}

    def test_creates_with_evidence_and_metadata(self):
        evidence = [
            EvidenceItem(type="file", source="package.json", snippet='"status": "active"')
        ]
        decision = ExtractionDecision(
            value="active",
            confidence=0.92,
            detection_source="llm",
            decision_mode=DecisionMode.LLM_ADJUDICATED,
            review_status=ReviewStatus.NEEDS_REVIEW,
            evidence=evidence,
            metadata={"model": "claude-3-sonnet"},
        )
        assert len(decision.evidence) == 1
        assert decision.metadata["model"] == "claude-3-sonnet"

    def test_to_dict_serializes_enums_as_values(self):
        decision = ExtractionDecision(
            value="deprecated",
            confidence=0.75,
            detection_source="readme",
            decision_mode=DecisionMode.HUMAN_REVIEWED,
            review_status=ReviewStatus.APPROVED,
        )
        result = decision.to_dict()
        # Enums should be serialized as their string values
        assert result["decision_mode"] == "human_reviewed"
        assert result["review_status"] == "approved"

    def test_to_dict_serializes_evidence(self):
        evidence = [
            EvidenceItem(type="file", source="Dockerfile", snippet="FROM node:18")
        ]
        decision = ExtractionDecision(
            value="containerized",
            confidence=0.95,
            detection_source="dockerfile",
            decision_mode=DecisionMode.DETERMINISTIC,
            review_status=ReviewStatus.AUTO_ACCEPTED,
            evidence=evidence,
        )
        result = decision.to_dict()
        assert len(result["evidence"]) == 1
        assert result["evidence"][0]["type"] == "file"


class TestReviewItem:
    """Test ReviewItem dataclass."""

    def test_creates_review_item(self):
        review = ReviewItem(
            field="status",
            candidate_value="active",
            confidence=0.78,
            reason="Multiple conflicting sources detected",
            repo_path="/repos/payment-service",
        )
        assert review.field == "status"
        assert review.candidate_value == "active"
        assert review.confidence == 0.78
        assert review.reason == "Multiple conflicting sources detected"
        assert review.repo_path == "/repos/payment-service"
        assert review.evidence == []
        assert review.recommended_action == "human_review"

    def test_creates_with_custom_action(self):
        review = ReviewItem(
            field="owner_team",
            candidate_value="Platform",
            confidence=0.65,
            reason="LLM confidence below threshold",
            repo_path="/repos/auth-service",
            recommended_action="llm_retry",
        )
        assert review.recommended_action == "llm_retry"

    def test_to_dict_serializes_evidence(self):
        evidence = [
            EvidenceItem(type="file", source="OWNERS", snippet="@platform-team")
        ]
        review = ReviewItem(
            field="owner_team",
            candidate_value="Platform",
            confidence=0.70,
            reason="Found OWNERS file",
            repo_path="/repos/api",
            evidence=evidence,
        )
        result = review.to_dict()
        assert len(result["evidence"]) == 1
        assert result["evidence"][0]["source"] == "OWNERS"

    def test_default_factory_for_evidence(self):
        """Evidence should default to empty list, not None."""
        review = ReviewItem(
            field="tier",
            candidate_value="gold",
            confidence=0.90,
            reason="Direct match",
            repo_path="/repos/legacy",
        )
        assert review.evidence == []
        assert isinstance(review.evidence, list)
