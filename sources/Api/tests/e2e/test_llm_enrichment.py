"""Tests for LLM enrichment and decision adjudication."""

import pytest


class TestLLMEnrichmentDecisionModels:
    """Test decision model enums and structures."""

    def test_decision_mode_enum_values(self):
        """DecisionMode enum has correct values."""
        from app.services.c4.context.decision_models import DecisionMode
        assert DecisionMode.DETERMINISTIC.value == "deterministic"
        assert DecisionMode.LLM_ADJUDICATED.value == "llm_adjudicated"
        assert DecisionMode.HUMAN_REVIEWED.value == "human_reviewed"

    def test_review_status_enum_values(self):
        """ReviewStatus enum has correct values."""
        from app.services.c4.context.decision_models import ReviewStatus
        assert ReviewStatus.AUTO_ACCEPTED.value == "auto_accepted"
        assert ReviewStatus.NEEDS_REVIEW.value == "needs_review"
        assert ReviewStatus.APPROVED.value == "approved"
        assert ReviewStatus.REJECTED.value == "rejected"

    def test_extraction_decision_to_dict(self):
        """ExtractionDecision.to_dict() produces correct structure."""
        from app.services.c4.context.decision_models import (
            ExtractionDecision,
            DecisionMode,
            ReviewStatus,
        )
        decision = ExtractionDecision(
            value="test_value",
            confidence=0.85,
            detection_source="test_source",
            decision_mode=DecisionMode.DETERMINISTIC,
            review_status=ReviewStatus.AUTO_ACCEPTED,
        )
        data = decision.to_dict()
        assert data["value"] == "test_value"
        assert data["confidence"] == 0.85
        assert data["decision_mode"] == "deterministic"
        assert data["review_status"] == "auto_accepted"

    def test_review_item_structure(self):
        """ReviewItem has required fields."""
        from app.services.c4.context.decision_models import (
            ReviewItem,
            EvidenceItem,
        )
        evidence = [
            EvidenceItem(
                type="codeowners",
                source="CODEOWNERS",
                snippet="@team-a and @team-b both claim ownership",
            )
        ]
        review = ReviewItem(
            field="owner",
            candidate_value="ambiguous",
            confidence=0.5,
            reason="Multiple teams claim ownership in CODEOWNERS",
            repo_path="/test/path",
            evidence=evidence,
        )
        data = review.to_dict()
        assert data["field"] == "owner"
        assert data["reason"] == "Multiple teams claim ownership in CODEOWNERS"
        assert len(data["evidence"]) == 1

    def test_evidence_item_structure(self):
        """EvidenceItem has required fields."""
        from app.services.c4.context.decision_models import EvidenceItem
        evidence = EvidenceItem(
            type="package_json",
            source="package.json",
            snippet='"dependencies": { "stripe": "^7.0.0" }',
        )
        data = evidence.to_dict()
        assert data["type"] == "package_json"
        assert data["source"] == "package.json"
        assert "stripe" in data["snippet"]


class TestLLMEnrichmentContainers:
    """Test LLM enrichment against fake OmniPay LLM."""

    def test_llm_enriched_billing_service(self):
        """omnipay-billing-llm gets llm_enriched=True with correct verdict."""
        from pathlib import Path
        from tests.harness.fixtures import FakeOmniPayLLM
        from app.services.c4.containers.container_manager import ContainerManager

        demo_dir = Path("/app/sources/demo/omnipay-billing-llm")
        if not demo_dir.exists():
            pytest.skip("omnipay-billing-llm demo not found")

        container_manager = ContainerManager(demo_dir, llm_manager=FakeOmniPayLLM())
        containers = container_manager.detect_all_containers()
        container_manager.enrich_containers_with_llm()

        billing = next(
            (c for c in containers.values() if c.get("name") == "omnipay-billing-llm"),
            None,
        )
        if billing is None:
            pytest.skip("omnipay-billing-llm not in extraction")

        assert billing.get("llm_enriched") is True
        assert billing.get("llm_verdict") == "keep"
        assert billing.get("llm_confidence") is not None

    def test_llm_enriched_ml_pipeline(self):
        """omnipay-ml-pipeline gets llm_enriched=True with Hydra notes."""
        from pathlib import Path
        from tests.harness.fixtures import FakeOmniPayLLM
        from app.services.c4.containers.container_manager import ContainerManager

        demo_dir = Path("/app/sources/demo/omnipay-ml-pipeline")
        if not demo_dir.exists():
            pytest.skip("omnipay-ml-pipeline demo not found")

        container_manager = ContainerManager(demo_dir, llm_manager=FakeOmniPayLLM())
        containers = container_manager.detect_all_containers()
        container_manager.enrich_containers_with_llm()

        ml = next(
            (c for c in containers.values() if c.get("name") == "omnipay-ml-pipeline"),
            None,
        )
        if ml is None:
            pytest.skip("omnipay-ml-pipeline not in extraction")

        assert ml.get("llm_enriched") is True
        assert ml.get("llm_verdict") == "keep"
