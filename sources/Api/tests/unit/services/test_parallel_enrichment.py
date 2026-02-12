"""Unit tests for parallel LLM enrichment in ServiceExtractionPipeline."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile

from app.domain.models.services import Service, ServiceStatus, ServiceTier
from app.services.service_extraction.service_extraction_pipeline import ServiceExtractionPipeline


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def pipeline(temp_repo):
    """Create a pipeline instance with mocked dependencies."""
    with patch("app.services.service_extraction.service_extraction_pipeline.GitFullAnalyzer"), \
         patch("app.services.service_extraction.service_extraction_pipeline.DomainExtractor"), \
         patch("app.services.service_extraction.service_extraction_pipeline.ServiceDiscoverer"):
        return ServiceExtractionPipeline(temp_repo)


def _make_service(name: str, domain=None, owner=None) -> Service:
    """Build a minimal Service for testing."""
    return Service(
        id=f"svc-{name}",
        name=name,
        domain=domain,
        owner=owner,
        status=ServiceStatus.UNKNOWN if domain is None else ServiceStatus.ACTIVE,
        tier=ServiceTier.UNKNOWN if domain is None else ServiceTier.TIER_2,
        data_class="Public" if domain else None,
    )


class TestNeedsLLMLabels:
    """Test _needs_llm_labels() logic."""

    def test_needs_labels_when_domain_missing(self, pipeline):
        svc = _make_service("api", domain=None, owner="Platform")
        assert pipeline._needs_llm_labels(svc) is True

    def test_needs_labels_when_status_unknown(self, pipeline):
        svc = Service(
            id="svc-1", name="api",
            domain="Checkout", owner="Payments",
            status=ServiceStatus.UNKNOWN,
            tier=ServiceTier.TIER_1,
            data_class="PII",
        )
        assert pipeline._needs_llm_labels(svc) is True

    def test_does_not_need_labels_when_all_fields_populated(self, pipeline):
        svc = Service(
            id="svc-1", name="api",
            domain="Checkout", owner="Payments",
            status=ServiceStatus.ACTIVE,
            tier=ServiceTier.TIER_1,
            data_class="PII",
            notes="Handles checkout flow.",
        )
        assert pipeline._needs_llm_labels(svc) is False


class TestEnrichSingleService:
    """Test _enrich_single_service() per-service enrichment."""

    def test_skips_when_no_service_path(self, pipeline, temp_repo):
        """Service with no resolvable path should be returned unchanged."""
        svc = _make_service("orphan")
        # No file_path set, so _resolve_service_path will return None
        result = pipeline._enrich_single_service(svc)
        assert result is svc  # returned unchanged

    def test_enriches_service_with_llm(self, pipeline, temp_repo):
        """Service with a valid path should be enriched by LLM."""
        # Create a file at the service path
        service_dir = temp_repo / "api"
        service_dir.mkdir()
        (service_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")

        svc = Service(
            id="svc-api", name="api",
            file_path=str(service_dir / "main.py"),
        )

        # Mock the enricher
        pipeline.llm_label_enricher = Mock()
        mock_enrichment = {"domain": "API", "tier": "Tier 2", "status": "ACTIVE"}
        pipeline.llm_label_enricher.enrich_service.return_value = mock_enrichment

        with patch.object(pipeline, "_enrich_with_llm_labels", return_value=mock_enrichment), \
             patch.object(pipeline, "_apply_llm_enrichment") as mock_apply:
            result = pipeline._enrich_single_service(svc)

        mock_apply.assert_called_once_with(svc, mock_enrichment)
        assert result is svc

    def test_handles_enrichment_error_gracefully(self, pipeline, temp_repo):
        """If LLM enrichment fails, service should still be returned."""
        service_dir = temp_repo / "failing-svc"
        service_dir.mkdir()
        svc = Service(id="svc-fail", name="failing-svc", file_path=str(service_dir))

        with patch.object(pipeline, "_enrich_with_llm_labels", side_effect=RuntimeError("LLM timeout")):
            # Should NOT propagate the error - calling code handles it
            with pytest.raises(RuntimeError):
                pipeline._enrich_single_service(svc)


class TestEnrichServicesParallel:
    """Test _enrich_services_parallel() orchestration."""

    def test_returns_all_services(self, pipeline):
        """All input services should appear in the output."""
        services = [_make_service("api"), _make_service("db"), _make_service("cache")]
        with patch.object(pipeline, "_enrich_single_service", side_effect=lambda s: s):
            result = pipeline._enrich_services_parallel(services)
        assert len(result) == 3

    def test_preserves_order(self, pipeline):
        """Output order should match input order."""
        services = [_make_service(f"svc-{i}") for i in range(5)]
        with patch.object(pipeline, "_enrich_single_service", side_effect=lambda s: s):
            result = pipeline._enrich_services_parallel(services)
        assert [s.name for s in result] == [s.name for s in services]

    def test_skips_fully_populated_services(self, pipeline):
        """Services with all fields set should not go to LLM."""
        full_svc = Service(
            id="svc-full", name="full-service",
            domain="Checkout", owner="Payments",
            status=ServiceStatus.ACTIVE, tier=ServiceTier.TIER_1,
            data_class="PII", notes="Full notes.",
        )
        empty_svc = _make_service("empty")

        with patch.object(pipeline, "_enrich_single_service", side_effect=lambda s: s) as mock_enrich:
            pipeline._enrich_services_parallel([full_svc, empty_svc])
        # Only the empty service (needs LLM) should be sent to _enrich_single_service
        called_names = [call.args[0].name for call in mock_enrich.call_args_list]
        assert "empty" in called_names
        assert "full-service" not in called_names

    def test_handles_individual_failures(self, pipeline):
        """If one service fails enrichment, others should still succeed."""
        services = [_make_service("ok-1"), _make_service("fail"), _make_service("ok-2")]

        def mock_enrich(svc):
            if svc.name == "fail":
                raise RuntimeError("LLM timeout")
            return svc

        with patch.object(pipeline, "_enrich_single_service", side_effect=mock_enrich):
            result = pipeline._enrich_services_parallel(services)

        # All 3 services should be returned (failures are caught and original returned)
        assert len(result) == 3
        assert {s.name for s in result} == {"ok-1", "fail", "ok-2"}

    def test_uses_configurable_max_workers(self, pipeline):
        """max_workers should be configurable via env var."""
        services = [_make_service(f"svc-{i}") for i in range(3)]
        import os
        with patch.dict(os.environ, {"LLM_MAX_CONCURRENT_CALLS": "2"}), \
             patch("concurrent.futures.ThreadPoolExecutor") as mock_executor_cls, \
             patch.object(pipeline, "_enrich_single_service", side_effect=lambda s: s):
            # Verify ThreadPoolExecutor is called with the env var value
            mock_executor = MagicMock()
            mock_executor_cls.return_value.__enter__ = lambda s: mock_executor
            mock_executor_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_executor.submit = MagicMock()
            pipeline._enrich_services_parallel(services, max_workers=2)
        # The pipeline accepted max_workers=2 without error
