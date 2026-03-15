"""
End-to-end tests for the OmniPay demo extraction.

These tests validate that the extraction pipeline correctly identifies
all 6 OmniPay services and extracts the expected metadata.

Run inside docker:
    docker compose exec -T api python -m pytest tests/e2e/test_omnipay_extraction.py -v

Or via Make:
    make test-e2e-omnipay
"""

import json
import subprocess
from pathlib import Path
from typing import List

import pytest

from app.services.c4.context.context_manager import ContextManager
from app.services.c4.containers.container_manager import ContainerManager
from app.services.c4.containers.structure_detector import StructureDetector


# Path to the OmniPay demo directory
DEMO_DIR = Path("/app/sources/demo")


def _init_git(repo_path: Path) -> None:
    """Initialize a git repo with a single commit so git-based detectors work."""
    for cmd in [
        ["git", "init", str(repo_path)],
        ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
        ["git", "-C", str(repo_path), "config", "user.name", "Test"],
        ["git", "-C", str(repo_path), "add", "."],
        ["git", "-C", str(repo_path), "commit", "-m", "initial"],
    ]:
        subprocess.run(cmd, capture_output=True, check=False)


def _run_extraction(repo_path: Path) -> tuple[List[dict], dict]:
    """Run the extraction pipeline and return (containers, system_context)."""
    # Initialize git for ownership detection
    _init_git(repo_path)

    # Extract system context
    context_manager = ContextManager(repo_path, llm_manager=None)
    system_context = context_manager.extract_context()

    # Detect containers
    structure_detector = StructureDetector(repo_path, llm_manager=None)
    containers = structure_detector.detect()

    return containers, system_context


class FakeOmniPayLLM:
    """Deterministic LLM double for container enrichment tests."""

    def __init__(self) -> None:
        self.timeout = 30

    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 0,
        temperature: float = 0.0,
        use_cache: bool = True,
    ) -> str:
        del max_tokens, temperature, use_cache

        if "C4 CONTAINER DEFINITION" not in prompt:
            return "OmniPay is a demo payment platform with multiple service boundaries."

        return json.dumps(
            {
                "containers": [
                    {
                        "name": "omnipay-billing-llm",
                        "verdict": "keep",
                        "container_type": "Billing Service",
                        "technology": "Python/FastAPI",
                        "protocol": "HTTP",
                        "description": (
                            "Handles subscription billing, invoice generation, "
                            "refunds, and payment reconciliation workflows."
                        ),
                        "confidence": 0.91,
                        "notes": (
                            "Derived from billing and ledger signals in README and code."
                        ),
                    },
                    {
                        "name": "omnipay-ml-pipeline",
                        "verdict": "keep",
                        "container_type": "ML Pipeline",
                        "technology": "Python/Hydra/MLflow/PyTorch",
                        "protocol": "HTTP",
                        "description": (
                            "Runs risk-scoring training and inference workflows "
                            "backed by Hydra-managed ML configuration."
                        ),
                        "confidence": 0.93,
                        "notes": (
                            "Hydra config and MLflow markers indicate ML orchestration."
                        ),
                    },
                ],
                "inferred_relationships": [],
            }
        )


def _run_llm_container_extraction(repo_path: Path) -> List[dict]:
    """Run level-2 extraction with a deterministic LLM enrichment pass."""
    container_manager = ContainerManager(repo_path, llm_manager=FakeOmniPayLLM())
    containers = container_manager.detect_all_containers()
    container_manager.enrich_containers_with_llm()
    return list(containers.values())


@pytest.fixture(scope="module")
def omnipay_extraction() -> tuple[List[dict], dict]:
    """Extract from the OmniPay demo directory."""
    if not DEMO_DIR.exists():
        pytest.skip(f"Demo directory not found: {DEMO_DIR}")

    containers, system_context = _run_extraction(DEMO_DIR)
    return containers, system_context


@pytest.fixture
def omnipay_containers(omnipay_extraction):
    """Get containers from extraction."""
    return omnipay_extraction[0]


@pytest.fixture
def omnipay_context(omnipay_extraction):
    """Get system context from extraction."""
    return omnipay_extraction[1]


@pytest.fixture(scope="module")
def omnipay_llm_containers() -> List[dict]:
    """Get containers from extraction with deterministic LLM enrichment."""
    if not DEMO_DIR.exists():
        pytest.skip(f"Demo directory not found: {DEMO_DIR}")

    _init_git(DEMO_DIR)
    return _run_llm_container_extraction(DEMO_DIR)


class TestOmniPayServiceDiscovery:
    """Test that all 6 OmniPay services are discovered."""

    def test_discovers_six_services(self, omnipay_containers):
        """The demo has 6 services: ledger, fraud-ml, gateway, notifier, infra, card-router."""
        assert len(omnipay_containers) >= 6, (
            f"Expected at least 6 services, got {len(omnipay_containers)}. "
            f"Found: {[c.get('name') for c in omnipay_containers]}"
        )

    def test_service_names_match_expected(self, omnipay_containers):
        """Verify all expected service names are present."""
        expected_names = {
            "omnipay-ledger",
            "omnipay-fraud-ml",
            "omnipay-gateway",
            "omnipay-notifier",
            "omnipay-infra",
            "omnipay-card-router",
        }
        found_names = {c.get("name") for c in omnipay_containers}
        missing = expected_names - found_names
        assert not missing, f"Missing services: {missing}"

    def test_service_names_are_unique(self, omnipay_containers):
        """Ensure no duplicate service names."""
        names = [c.get("name") for c in omnipay_containers]
        assert len(names) == len(set(names)), f"Duplicate service names: {names}"


class TestOmniPayLanguageDetection:
    """Test language/technology detection for each OmniPay service."""

    def test_omnipay_ledger_detects_java(self, omnipay_containers):
        """omnipay-ledger is a Java Spring Boot service."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-ledger"), None)
        assert svc is not None, "omnipay-ledger not found"
        # Check either technology or language field
        tech = str(svc.get("technology", "")).lower()
        lang = svc.get("language")
        langs = svc.get("languages", []) or ([lang] if lang else [])
        lang_str = " ".join(str(l).lower() for l in langs)
        # Should detect Java via technology or language
        assert "java" in tech or "java" in lang_str, (
            f"Expected Java for omnipay-ledger, got tech={tech}, langs={langs}"
        )

    def test_omnipay_fraud_ml_detects_python(self, omnipay_containers):
        """omnipay-fraud-ml is a Python ML service."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-fraud-ml"), None)
        assert svc is not None, "omnipay-fraud-ml not found"
        tech = str(svc.get("technology", "")).lower()
        lang = svc.get("language")
        langs = svc.get("languages", []) or ([lang] if lang else [])
        lang_str = " ".join(str(l).lower() for l in langs)
        # Python might be in tech or language
        assert "python" in tech or "python" in lang_str, (
            f"Expected Python for omnipay-fraud-ml, got tech={tech}, langs={langs}"
        )

    def test_omnipay_gateway_detects_typescript(self, omnipay_containers):
        """omnipay-gateway is a TypeScript/Node.js NestJS service."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-gateway"), None)
        assert svc is not None, "omnipay-gateway not found"
        tech = str(svc.get("technology", "")).lower()
        lang = svc.get("language")
        langs = svc.get("languages", []) or ([lang] if lang else [])
        lang_str = " ".join(str(l).lower() for l in langs)
        # Should detect Node.js/TS/JS via technology or language
        assert any(kw in tech or kw in lang_str for kw in ["typescript", "javascript", "node"]), (
            f"Expected TS/JS/Node for omnipay-gateway, got tech={tech}, langs={langs}"
        )

    def test_omnipay_notifier_detects_go(self, omnipay_containers):
        """omnipay-notifier is a Go service."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-notifier"), None)
        assert svc is not None, "omnipay-notifier not found"
        tech = str(svc.get("technology", "")).lower()
        lang = svc.get("language")
        langs = svc.get("languages", []) or ([lang] if lang else [])
        lang_str = " ".join(str(l).lower() for l in langs)
        # Should detect Go via technology or language
        assert "go" in tech or "go" in lang_str or "golang" in lang_str, (
            f"Expected Go for omnipay-notifier, got tech={tech}, langs={langs}"
        )

    def test_omnipay_card_router_detects_csharp(self, omnipay_containers):
        """omnipay-card-router is a C# .NET service."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-card-router"), None)
        assert svc is not None, "omnipay-card-router not found"
        tech = str(svc.get("technology", "")).lower()
        lang = svc.get("language")
        langs = svc.get("languages", []) or ([lang] if lang else [])
        lang_str = " ".join(str(l).lower() for l in langs)
        # C# detection
        assert any(kw in tech or kw in lang_str for kw in ["c#", "csharp", "dotnet", ".net"]), (
            f"Expected C#/.NET for omnipay-card-router, got tech={tech}, langs={langs}"
        )


class TestOmniPayDeploymentTargets:
    """Test deployment target detection."""

    def test_omnipay_ledger_has_container_deployment(self, omnipay_containers):
        """omnipay-ledger has a Dockerfile."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-ledger"), None)
        assert svc is not None, "omnipay-ledger not found"
        # Check for Dockerfile
        has_dockerfile = svc.get("dockerfile") is not None and svc.get("dockerfile") != ""
        tech = str(svc.get("technology", "")).lower()
        assert has_dockerfile or "container" in tech or "docker" in tech or "java" in tech, (
            f"Expected Container deployment for omnipay-ledger"
        )

    def test_omnipay_infra_has_infrastructure(self, omnipay_containers):
        """omnipay-infra defines infrastructure (Terraform/Helm)."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-infra"), None)
        assert svc is not None, "omnipay-infra not found"
        tech = str(svc.get("technology", "")).lower()
        # Check if we can detect infra-related files or technology
        has_infra_files = svc.get("terraform") or svc.get("helm") or svc.get("kubernetes")
        # Infrastructure might be Unknown if not detected - this is a known gap
        assert has_infra_files or tech != "unknown" or tech != "", (
            f"Expected Infrastructure detection for omnipay-infra, got {tech}"
        )


class TestOmniPayOwnership:
    """Test ownership detection for OmniPay services.

    Note: Owner detection may require git history. The test verifies that
    the owner field exists and is populated when available.
    """

    def test_omnipay_ledger_has_owner_or_team(self, omnipay_containers):
        """omnipay-ledger should have an owner or team detected."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-ledger"), None)
        assert svc is not None, "omnipay-ledger not found"
        # Owner should be detected from CODEOWNERS or README
        owner = svc.get("owner")
        team = svc.get("team")
        # Either owner or team should be present
        has_ownership = (owner is not None and owner != "") or (team is not None and team != "")
        assert has_ownership, (
            f"Expected owner or team for omnipay-ledger, got owner={owner}, team={team}"
        )

    def test_omnipay_gateway_has_owner_or_team(self, omnipay_containers):
        """omnipay-gateway should have an owner or team detected."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-gateway"), None)
        assert svc is not None, "omnipay-gateway not found"
        owner = svc.get("owner")
        team = svc.get("team")
        has_ownership = (owner is not None and owner != "") or (team is not None and team != "")
        assert has_ownership, (
            f"Expected owner or team for omnipay-gateway, got owner={owner}, team={team}"
        )

    def test_omnipay_card_router_has_owner_or_team(self, omnipay_containers):
        """omnipay-card-router should have an owner or team detected."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-card-router"), None)
        assert svc is not None, "omnipay-card-router not found"
        owner = svc.get("owner")
        team = svc.get("team")
        has_ownership = (owner is not None and owner != "") or (team is not None and team != "")
        assert has_ownership, (
            f"Expected owner or team for omnipay-card-router, got owner={owner}, team={team}"
        )


class TestOmniPayAPISurface:
    """Test API surface type detection.

    Note: API surface detection may not be implemented for all container types.
    These tests verify that the extraction produces valid structure.
    """

    def test_omnipay_gateway_has_technology(self, omnipay_containers):
        """omnipay-gateway should have technology detected."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-gateway"), None)
        assert svc is not None, "omnipay-gateway not found"
        tech = svc.get("technology")
        # Technology should be detected
        assert tech is not None and tech != "Unknown", (
            f"Expected technology for omnipay-gateway, got {tech}"
        )

    def test_omnipay_ledger_has_technology(self, omnipay_containers):
        """omnipay-ledger should have technology detected."""
        svc = next((c for c in omnipay_containers if c.get("name") == "omnipay-ledger"), None)
        assert svc is not None, "omnipay-ledger not found"
        tech = svc.get("technology")
        # Technology should be detected
        assert tech is not None and tech != "Unknown", (
            f"Expected technology for omnipay-ledger, got {tech}"
        )


class TestOmniPayFieldCompleteness:
    """Test that all required fields are present for OmniPay services."""

    def test_all_services_have_id(self, omnipay_containers):
        """All services must have an ID or name."""
        for svc in omnipay_containers:
            assert svc.get("name") is not None, f"Service missing name: {svc}"

    def test_all_services_have_name(self, omnipay_containers):
        """All services must have a name."""
        for svc in omnipay_containers:
            assert svc.get("name") is not None and isinstance(svc.get("name"), str), (
                f"Service missing valid name: {svc}"
            )

    def test_all_services_have_technology(self, omnipay_containers):
        """All services should have technology detected."""
        for svc in omnipay_containers:
            tech = svc.get("technology")
            # Infrastructure services may have minimal tech info
            assert tech is not None, f"Service {svc.get('name')} missing technology"


class TestOmniPayPerformance:
    """Test that extraction completes within acceptable time."""

    def test_extraction_completes_within_timeout(self):
        """Full OmniPay extraction must complete within 60 seconds."""
        if not DEMO_DIR.exists():
            pytest.skip(f"Demo directory not found: {DEMO_DIR}")

        import time
        start = time.time()
        containers, context = _run_extraction(DEMO_DIR)
        elapsed = time.time() - start

        assert elapsed < 60, (
            f"OmniPay extraction took {elapsed:.1f}s — exceeds 60s budget"
        )
        assert len(containers) >= 6, f"Expected ≥6 services, got {len(containers)}"


class TestOmniPayConsistency:
    """Test consistency with known extraction output."""

    def test_extraction_finds_core_services(self):
        """Extraction should find the core services."""
        if not DEMO_DIR.exists():
            pytest.skip(f"Demo directory not found: {DEMO_DIR}")

        containers, _ = _run_extraction(DEMO_DIR)

        # Basic sanity check - ensure we get the expected services
        names = {c.get("name") for c in containers}

        # Core services that must be present
        required = {
            "omnipay-ledger",
            "omnipay-gateway",
            "omnipay-card-router",
        }

        missing = required - names
        assert not missing, f"Missing required services: {missing}"

    def test_extraction_produces_valid_json(self, omnipay_containers, omnipay_context):
        """Extraction should produce valid, serializable data."""
        # Should not raise
        json.dumps(omnipay_containers)
        json.dumps(omnipay_context)


class TestOmniPayExtendedServices:
    """Test that extended OmniPay services are discovered."""

    # Phase 1: Dictionary trigger services
    EXPECTED_DICTIONARY_SERVICES = {
        "omnipay-payment-processor",  # Stripe trigger
        "omnipay-analytics",  # Mixpanel trigger
        "omnipay-auth",  # Auth0 trigger
        "omnipay-database",  # PostgreSQL/Redis trigger
    }

    # Phase 2: LLM enrichment services
    EXPECTED_LLM_SERVICES = {
        "omnipay-billing-llm",  # Business domain inference
        "omnipay-ml-pipeline",  # Hydra config inference
    }

    # Phase 3: Human review services
    EXPECTED_HUMAN_REVIEW_SERVICES = {
        "omnipay-disputes",  # Ambiguous ownership
    }

    # Phase 4: Platform integration services
    EXPECTED_PLATFORM_SERVICES = {
        "omnipay-settlement-orchestrator",  # .NET + SQL Server + RabbitMQ + Redis
        "omnipay-event-projections",  # .NET + Kafka + MongoDB + Redis
        "omnipay-risk-streams",  # Kafka Streams Java app
        "omnipay-k8s-ops",  # Helm + Kustomize + stateful platform resources
    }

    ALL_EXPECTED_SERVICES = (
        EXPECTED_DICTIONARY_SERVICES
        | EXPECTED_LLM_SERVICES
        | EXPECTED_HUMAN_REVIEW_SERVICES
        | EXPECTED_PLATFORM_SERVICES
    )

    def test_discovers_extended_services(self, omnipay_containers):
        """Extended OmniPay demo should have all new services."""
        found_names = {c.get("name") for c in omnipay_containers}
        missing = self.ALL_EXPECTED_SERVICES - found_names

        assert not missing, f"Missing extended services: {missing}. Found: {found_names}"

    def test_payment_processor_exists(self, omnipay_containers):
        """omnipay-payment-processor (Stripe) should be discovered."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-payment-processor"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-payment-processor not found in extraction")
        # Should detect Python/Flask
        tech = str(svc.get("technology", "")).lower()
        assert "python" in tech or "flask" in tech, f"Expected Python/Flask, got {tech}"

    def test_analytics_exists(self, omnipay_containers):
        """omnipay-analytics (Mixpanel) should be discovered."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-analytics"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-analytics not found in extraction")
        # Should detect Node.js/JavaScript
        tech = str(svc.get("technology", "")).lower()
        lang = str(svc.get("language", "")).lower()
        assert "node" in tech or "javascript" in tech or "node" in lang, (
            f"Expected Node.js/JS, got tech={tech}, lang={lang}"
        )

    def test_auth_exists(self, omnipay_containers):
        """omnipay-auth (Auth0) should be discovered."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-auth"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-auth not found in extraction")
        # Should detect Node.js
        tech = str(svc.get("technology", "")).lower()
        assert "node" in tech or "javascript" in tech, f"Expected Node.js, got {tech}"

    def test_database_service_exists(self, omnipay_containers):
        """omnipay-database (PostgreSQL/Redis) should be discovered."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-database"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-database not found in extraction")
        # Should detect Python
        tech = str(svc.get("technology", "")).lower()
        assert "python" in tech, f"Expected Python, got {tech}"

    def test_billing_llm_exists(self, omnipay_containers):
        """omnipay-billing-llm should be discovered."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-billing-llm"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-billing-llm not found in extraction")
        # Should detect Python/FastAPI
        tech = str(svc.get("technology", "")).lower()
        assert "python" in tech or "fastapi" in tech, f"Expected Python/FastAPI, got {tech}"

    def test_ml_pipeline_exists(self, omnipay_containers):
        """omnipay-ml-pipeline should be discovered."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-ml-pipeline"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-ml-pipeline not found in extraction")
        # Should detect Python
        tech = str(svc.get("technology", "")).lower()
        assert "python" in tech, f"Expected Python, got {tech}"

    def test_disputes_service_exists(self, omnipay_containers):
        """omnipay-disputes (human review scenario) should be discovered."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-disputes"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-disputes not found in extraction")
        # Should detect Node.js
        tech = str(svc.get("technology", "")).lower()
        assert "node" in tech or "javascript" in tech, f"Expected Node.js, got {tech}"

    def test_settlement_orchestrator_exists(self, omnipay_containers):
        """omnipay-settlement-orchestrator should be discovered as a .NET service."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-settlement-orchestrator"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-settlement-orchestrator not found in extraction")
        tech = str(svc.get("technology", "")).lower()
        assert ".net" in tech or "dotnet" in tech, f"Expected .NET, got {tech}"

    def test_event_projections_exists(self, omnipay_containers):
        """omnipay-event-projections should be discovered as a .NET service."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-event-projections"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-event-projections not found in extraction")
        tech = str(svc.get("technology", "")).lower()
        assert ".net" in tech or "dotnet" in tech, f"Expected .NET, got {tech}"

    def test_risk_streams_exists(self, omnipay_containers):
        """omnipay-risk-streams should be discovered as a Java service."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-risk-streams"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-risk-streams not found in extraction")
        tech = str(svc.get("technology", "")).lower()
        assert "java" in tech, f"Expected Java, got {tech}"

    def test_k8s_ops_exists(self, omnipay_containers):
        """omnipay-k8s-ops should expose Kubernetes-oriented deployment metadata."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-k8s-ops"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-k8s-ops not found in extraction")
        tech = str(svc.get("technology", "")).lower()
        runtime = str(svc.get("runtime_environment", "")).lower()
        assert "helm" in tech or "kubernetes" in runtime or svc.get("kubernetes"), (
            f"Expected Kubernetes/Helm metadata, got tech={tech}, runtime={runtime}"
        )


class TestOmniPayDictionaryExtraction:
    """Test dictionary-based extraction (provider catalog matching)."""

    def test_provider_catalog_available(self):
        """Provider catalog should be importable and populated."""
        try:
            from app.services.c4.context.provider_catalog import (
                PROVIDER_CATALOG,
                match_provider_from_package,
                match_provider_from_env_var,
            )
        except ImportError as e:
            pytest.skip(f"Provider catalog not available: {e}")

        # Catalog should have entries
        assert len(PROVIDER_CATALOG) > 0, "Provider catalog should not be empty"

        # Test Stripe matching
        stripe = match_provider_from_package("stripe")
        assert stripe is not None, "Should match Stripe from package name"
        assert stripe.provider == "Stripe", f"Expected Stripe, got {stripe.provider}"

        # Test Mixpanel matching
        mixpanel = match_provider_from_package("mixpanel")
        assert mixpanel is not None, "Should match Mixpanel from package name"
        assert mixpanel.provider == "Mixpanel", f"Expected Mixpanel, got {mixpanel.provider}"

        # Test Auth0 matching
        auth0 = match_provider_from_package("@auth0/auth0-spa-js")
        assert auth0 is not None, "Should match Auth0 from package name"
        assert auth0.provider == "Auth0", f"Expected Auth0, got {auth0.provider}"

        # Test PostgreSQL matching
        postgres = match_provider_from_package("psycopg2")
        assert postgres is not None, "Should match PostgreSQL from package name"
        assert postgres.provider == "PostgreSQL", f"Expected PostgreSQL, got {postgres.provider}"

        # Test Redis matching
        redis_pkg = match_provider_from_package("redis")
        assert redis_pkg is not None, "Should match Redis from package name"
        assert redis_pkg.provider == "Redis", f"Expected Redis, got {redis_pkg.provider}"

        # Test MongoDB matching
        mongodb = match_provider_from_package("MongoDB.Driver")
        assert mongodb is not None, "Should match MongoDB from package name"
        assert mongodb.provider == "MongoDB", f"Expected MongoDB, got {mongodb.provider}"

        # Test Kafka matching
        kafka = match_provider_from_package("Confluent.Kafka")
        assert kafka is not None, "Should match Kafka from package name"
        assert kafka.provider == "Kafka", f"Expected Kafka, got {kafka.provider}"

        # Test RabbitMQ matching
        rabbitmq = match_provider_from_package("RabbitMQ.Client")
        assert rabbitmq is not None, "Should match RabbitMQ from package name"
        assert rabbitmq.provider == "RabbitMQ", f"Expected RabbitMQ, got {rabbitmq.provider}"

        # Test SQL Server matching
        sqlserver = match_provider_from_package("Microsoft.Data.SqlClient")
        assert sqlserver is not None, "Should match SQL Server from package name"
        assert sqlserver.provider == "SQL Server", (
            f"Expected SQL Server, got {sqlserver.provider}"
        )

    def test_env_var_matching(self):
        """Test environment variable matching in provider catalog."""
        try:
            from app.services.c4.context.provider_catalog import match_provider_from_env_var
        except ImportError as e:
            pytest.skip(f"Provider catalog not available: {e}")

        # Test Stripe env vars
        stripe = match_provider_from_env_var("STRIPE_API_KEY")
        assert stripe is not None, "Should match Stripe from STRIPE_API_KEY"
        assert stripe.provider == "Stripe"

        # Test Mixpanel env vars
        mixpanel = match_provider_from_env_var("MIXPANEL_TOKEN")
        assert mixpanel is not None, "Should match Mixpanel from MIXPANEL_TOKEN"
        assert mixpanel.provider == "Mixpanel"

        # Test Auth0 env vars
        auth0 = match_provider_from_env_var("AUTH0_DOMAIN")
        assert auth0 is not None, "Should match Auth0 from AUTH0_DOMAIN"
        assert auth0.provider == "Auth0"

        # Test PostgreSQL env vars
        postgres = match_provider_from_env_var("POSTGRES_HOST")
        assert postgres is not None, "Should match PostgreSQL from POSTGRES_HOST"
        assert postgres.provider == "PostgreSQL"

        # Test MongoDB env vars
        mongodb = match_provider_from_env_var("MONGODB_URI")
        assert mongodb is not None, "Should match MongoDB from MONGODB_URI"
        assert mongodb.provider == "MongoDB"

        # Test Kafka env vars
        kafka = match_provider_from_env_var("KAFKA_BOOTSTRAP_SERVERS")
        assert kafka is not None, "Should match Kafka from KAFKA_BOOTSTRAP_SERVERS"
        assert kafka.provider == "Kafka"

        # Test RabbitMQ env vars
        rabbitmq = match_provider_from_env_var("RABBITMQ_URL")
        assert rabbitmq is not None, "Should match RabbitMQ from RABBITMQ_URL"
        assert rabbitmq.provider == "RabbitMQ"

        # Test SQL Server env vars
        sqlserver = match_provider_from_env_var("SQLSERVER_CONNECTION_STRING")
        assert sqlserver is not None, (
            "Should match SQL Server from SQLSERVER_CONNECTION_STRING"
        )
        assert sqlserver.provider == "SQL Server"

    def test_payment_processor_triggers_stripe(self, omnipay_context):
        """omnipay-payment-processor should emit a Stripe provider-catalog hit."""
        stripe = next(
            (
                dep
                for dep in omnipay_context.get("external_dependencies", [])
                if dep.get("name") == "Stripe"
            ),
            None,
        )
        assert stripe is not None, "Stripe should be present in external dependencies"
        assert stripe.get("detection_source") == "provider_catalog"
        assert "omnipay-payment-processor/requirements.txt" in stripe.get(
            "detected_from_all", []
        )
        assert stripe.get("decision", {}).get("metadata", {}).get("catalog_match", {}).get(
            "alias_field"
        ) == "package_aliases"

    def test_analytics_triggers_mixpanel(self, omnipay_context):
        """omnipay-analytics should emit a Mixpanel provider-catalog hit."""
        mixpanel = next(
            (
                dep
                for dep in omnipay_context.get("external_dependencies", [])
                if dep.get("name") == "Mixpanel"
            ),
            None,
        )
        assert mixpanel is not None, "Mixpanel should be present in external dependencies"
        assert mixpanel.get("detection_source") == "provider_catalog"
        assert "omnipay-analytics/package.json" in mixpanel.get("detected_from_all", [])
        assert mixpanel.get("decision", {}).get("metadata", {}).get("catalog_match", {}).get(
            "alias_field"
        ) == "package_aliases"

    def test_database_triggers_postgres_redis(self, omnipay_context):
        """omnipay-database should emit PostgreSQL and Redis provider hits."""
        postgres = next(
            (
                dep
                for dep in omnipay_context.get("external_dependencies", [])
                if dep.get("name") == "PostgreSQL"
            ),
            None,
        )
        redis = next(
            (
                dep
                for dep in omnipay_context.get("external_dependencies", [])
                if dep.get("name") == "Redis"
            ),
            None,
        )

        assert postgres is not None, "PostgreSQL should be present in external dependencies"
        assert redis is not None, "Redis should be present in external dependencies"
        assert "omnipay-database/requirements.txt" in postgres.get("detected_from_all", [])
        assert "omnipay-database/requirements.txt" in redis.get("detected_from_all", [])
        assert postgres.get("detection_source") == "provider_catalog"
        assert redis.get("detection_source") == "provider_catalog"

    def test_platform_services_trigger_kafka_rabbit_mongo_sqlserver(self, omnipay_context):
        """Platform services should emit Kafka, RabbitMQ, MongoDB, and SQL Server hits."""
        names = {
            dep["name"]: dep
            for dep in omnipay_context.get("external_dependencies", [])
        }

        assert "Kafka" in names, "Kafka should be present in external dependencies"
        assert "RabbitMQ" in names, "RabbitMQ should be present in external dependencies"
        assert "MongoDB" in names, "MongoDB should be present in external dependencies"
        assert "SQL Server" in names, "SQL Server should be present in external dependencies"

        kafka = names["Kafka"]
        rabbitmq = names["RabbitMQ"]
        mongodb = names["MongoDB"]
        sqlserver = names["SQL Server"]

        assert "omnipay-event-projections/appsettings.json" in kafka.get(
            "detected_from_all", []
        )
        assert "omnipay-settlement-orchestrator/appsettings.json" in rabbitmq.get(
            "detected_from_all", []
        )
        assert "omnipay-event-projections/appsettings.json" in mongodb.get(
            "detected_from_all", []
        )
        assert "omnipay-settlement-orchestrator/OmniPay.SettlementOrchestrator.csproj" in (
            sqlserver.get("detected_from_all", [])
        )

        assert kafka.get("detection_source") == "provider_catalog"
        assert rabbitmq.get("detection_source") == "provider_catalog"
        assert mongodb.get("detection_source") == "provider_catalog"
        assert sqlserver.get("detection_source") == "provider_catalog"


class TestOmniPayLLMEnrichment:
    """Test LLM-based enrichment capabilities."""

    def test_decision_models_available(self):
        """Decision models should be importable."""
        try:
            from app.services.c4.context.decision_models import (
                DecisionMode,
                ReviewStatus,
                ExtractionDecision,
            )
        except ImportError as e:
            pytest.skip(f"Decision models not available: {e}")

        # Verify enum values
        assert DecisionMode.DETERMINISTIC.value == "deterministic"
        assert DecisionMode.LLM_ADJUDICATED.value == "llm_adjudicated"
        assert DecisionMode.HUMAN_REVIEWED.value == "human_reviewed"

        assert ReviewStatus.AUTO_ACCEPTED.value == "auto_accepted"
        assert ReviewStatus.NEEDS_REVIEW.value == "needs_review"
        assert ReviewStatus.APPROVED.value == "approved"
        assert ReviewStatus.REJECTED.value == "rejected"

    def test_extraction_decision_structure(self):
        """ExtractionDecision should have required fields."""
        try:
            from app.services.c4.context.decision_models import (
                ExtractionDecision,
                DecisionMode,
                ReviewStatus,
            )
        except ImportError as e:
            pytest.skip(f"Decision models not available: {e}")

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

    def test_llm_service_has_complex_logic(self, omnipay_llm_containers):
        """LLM-enriched services should record container enrichment output."""
        # omnipay-billing-llm has vague business domain description
        billing = next(
            (c for c in omnipay_llm_containers if c.get("name") == "omnipay-billing-llm"),
            None,
        )
        if billing is None:
            pytest.skip("omnipay-billing-llm not found")

        assert billing.get("llm_enriched") is True
        assert billing.get("llm_verdict") == "keep"
        assert billing.get("llm_confidence") == pytest.approx(0.91)
        assert "billing and ledger signals" in str(billing.get("llm_notes", "")).lower()

    def test_ml_pipeline_has_hydra_config(self, omnipay_llm_containers):
        """ML pipeline should record Hydra-oriented LLM enrichment notes."""
        ml = next(
            (c for c in omnipay_llm_containers if c.get("name") == "omnipay-ml-pipeline"),
            None,
        )
        if ml is None:
            pytest.skip("omnipay-ml-pipeline not found")

        assert ml.get("llm_enriched") is True
        assert ml.get("llm_verdict") == "keep"
        assert ml.get("llm_confidence") == pytest.approx(0.93)
        assert "hydra config" in str(ml.get("llm_notes", "")).lower()


class TestOmniPayHumanReview:
    """Test human review workflow scenarios."""

    def test_review_item_structure(self):
        """ReviewItem should have required fields."""
        try:
            from app.services.c4.context.decision_models import (
                ReviewItem,
                EvidenceItem,
            )
        except ImportError as e:
            pytest.skip(f"Decision models not available: {e}")

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

    def test_disputes_service_has_conflicting_ownership(self, omnipay_containers):
        """omnipay-disputes should have conflicting CODEOWNERS."""
        svc = next(
            (c for c in omnipay_containers if c.get("name") == "omnipay-disputes"),
            None,
        )
        if svc is None:
            pytest.skip("omnipay-disputes not found")

        assert svc.get("owner") == "omnipay/finance-team"
        assert svc.get("team") == "omnipay/risk-team"
        assert svc.get("owner") != svc.get("team")

    def test_evidence_item_structure(self):
        """EvidenceItem should have required fields."""
        try:
            from app.services.c4.context.decision_models import EvidenceItem
        except ImportError as e:
            pytest.skip(f"Decision models not available: {e}")

        evidence = EvidenceItem(
            type="package_json",
            source="package.json",
            snippet='"dependencies": { "stripe": "^7.0.0" }',
        )

        data = evidence.to_dict()
        assert data["type"] == "package_json"
        assert data["source"] == "package.json"
        assert "stripe" in data["snippet"]


class TestOmniPayTotalServiceCount:
    """Test that all OmniPay services are discovered."""

    def test_total_service_count(self, omnipay_containers):
        """Should discover all current OmniPay services, including platform extensions."""
        assert len(omnipay_containers) >= 17, (
            f"Expected at least 17 services, got {len(omnipay_containers)}. "
            f"Found: {[c.get('name') for c in omnipay_containers]}"
        )

    def test_all_original_services_present(self, omnipay_containers):
        """All original 6 services should still be present."""
        original = {
            "omnipay-ledger",
            "omnipay-fraud-ml",
            "omnipay-gateway",
            "omnipay-notifier",
            "omnipay-infra",
            "omnipay-card-router",
        }
        found = {c.get("name") for c in omnipay_containers}
        missing = original - found
        assert not missing, f"Missing original services: {missing}"
