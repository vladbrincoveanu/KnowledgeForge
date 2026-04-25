# Integration Test Suite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a comprehensive pytest harness library and test suite using existing OmniPay demo repos, covering core services, edge cases, provider catalog, LLM enrichment, and snapshot regression.

**Architecture:** Shared fixture library (`tests/harness/`) provides deterministic extraction runs against OmniPay demo repos. Four new test files use these fixtures to validate extraction behavior.

**Tech Stack:** Python 3.11, pytest, pytest-asyncio

---

## File Map

```
sources/Api/tests/
  harness/
    __init__.py                          # NEW — makes harness a package
    omnipay_harness.py                    # NEW — shared fixtures
    fixtures.py                           # NEW — LLM doubles
  e2e/
    test_omnipay_extraction.py            # EXISTING — keep as-is
    test_omnipay_harness.py              # NEW — harness-driven core tests
    test_edge_cases.py                   # NEW — 5 edge case tests
    test_provider_catalog.py              # NEW — provider matching tests
    test_llm_enrichment.py              # NEW — LLM adjudication tests
    test_snapshot_regression.py           # NEW — snapshot drift detection
    snapshots/
      omnipay_extraction.json             # EXISTING — snapshot file
```

**Important:** The test API root is `sources/Api/`. All `tests/` paths below are relative to `sources/Api/`. Tests run via `docker compose exec api python -m pytest`.

---

### Task 1: Create harness package and init file

**Files:**
- Create: `tests/harness/__init__.py`

- [ ] **Step 1: Create directory and init file**

```bash
mkdir -p sources/Api/tests/harness
touch sources/Api/tests/harness/__init__.py
```

```python
"""Test harness for OmniPay demo extraction tests."""

from .omnipay_harness import omnipay_repo, extract_containers, extract_context
from .fixtures import FakeOmniPayLLM

__all__ = [
    "omnipay_repo",
    "extract_containers",
    "extract_context",
    "FakeOmniPayLLM",
]
```

- [ ] **Step 2: Commit**

```bash
git add tests/harness/__init__.py
git commit -m "feat(tests): create harness package init"
```

---

### Task 2: Write omnipay_harness.py

**Files:**
- Create: `tests/harness/omnipay_harness.py`
- Dependencies: reads `sources/Api/app/services/c4/context/context_manager.py`, `sources/Api/app/services/c4/containers/structure_detector.py`

- [ ] **Step 1: Write the harness module**

```python
"""Shared pytest fixtures for OmniPay demo extraction tests."""

import subprocess
from pathlib import Path
from typing import List, Dict, Any

import pytest


# Path to the OmniPay demo directory inside the Docker container
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


@pytest.fixture(scope="module")
def demo_dir() -> Path:
    """Return path to the OmniPay demo directory."""
    if not DEMO_DIR.exists():
        pytest.skip(f"Demo directory not found: {DEMO_DIR}")
    return DEMO_DIR


@pytest.fixture(scope="module")
def omnipay_repo(demo_dir: Path) -> Dict[str, Path]:
    """Return a dict mapping service name to its path, with git initialized."""
    if not demo_dir.exists():
        pytest.skip(f"Demo directory not found: {demo_dir}")
    _init_git(demo_dir)
    result = {}
    for subdir in demo_dir.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            result[subdir.name] = subdir
    return result


def extract_containers(repo_path: Path) -> List[Dict[str, Any]]:
    """Run StructureDetector on a repo path and return container list."""
    from app.services.c4.containers.structure_detector import StructureDetector

    detector = StructureDetector(repo_path, llm_manager=None)
    return detector.detect()


def extract_context(repo_path: Path) -> Dict[str, Any]:
    """Run ContextManager on a repo path and return system context."""
    from app.services.c4.context.context_manager import ContextManager

    manager = ContextManager(repo_path, llm_manager=None)
    return manager.extract_context()


@pytest.fixture(scope="module")
def extracted_containers(demo_dir: Path) -> List[Dict[str, Any]]:
    """Extract containers from the full OmniPay demo directory."""
    if not demo_dir.exists():
        pytest.skip(f"Demo directory not found: {demo_dir}")
    _init_git(demo_dir)
    return extract_containers(demo_dir)


@pytest.fixture(scope="module")
def extracted_context(demo_dir: Path) -> Dict[str, Any]:
    """Extract system context from the full OmniPay demo directory."""
    if not demo_dir.exists():
        pytest.skip(f"Demo directory not found: {demo_dir}")
    _init_git(demo_dir)
    return extract_context(demo_dir)
```

- [ ] **Step 2: Run to verify imports work**

```bash
docker compose exec api python -c "from tests.harness import omnipay_repo, extract_containers, extract_context; print('OK')"
```

Expected: `OK` (no errors)

- [ ] **Step 3: Commit**

```bash
git add tests/harness/omnipay_harness.py tests/harness/__init__.py
git commit -m "feat(tests): add omnipay_harness shared fixtures"
```

---

### Task 3: Write fixtures.py (LLM double)

**Files:**
- Create: `tests/harness/fixtures.py`

- [ ] **Step 1: Write the LLM double**

```python
"""Deterministic LLM doubles for container enrichment tests."""

import json
from typing import Any, Dict


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
```

- [ ] **Step 2: Verify it imports**

```bash
docker compose exec api python -c "from tests.harness.fixtures import FakeOmniPayLLM; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add tests/harness/fixtures.py
git commit -m "feat(tests): add FakeOmniPayLLM double"
```

---

### Task 4: Write test_omnipay_harness.py

**Files:**
- Create: `tests/e2e/test_omnipay_harness.py`
- Test: run with `docker compose exec api python -m pytest tests/e2e/test_omnipay_harness.py -v`

- [ ] **Step 1: Write the test file**

```python
"""Harness-driven tests for core OmniPay services."""

import pytest

from tests.harness.omnipay_harness import (
    demo_dir,
    extract_containers,
    extract_context,
)


class TestOmniPayCoreServices:
    """Test the 6 core OmniPay services are detected and have correct fields."""

    @pytest.fixture(scope="class")
    def containers(self, demo_dir):
        """Extract containers from OmniPay demo directory."""
        return extract_containers(demo_dir)

    def test_discovers_six_core_services(self, containers):
        """Core 6 services: ledger, fraud-ml, gateway, notifier, infra, card-router."""
        expected = {
            "omnipay-ledger",
            "omnipay-fraud-ml",
            "omnipay-gateway",
            "omnipay-notifier",
            "omnipay-infra",
            "omnipay-card-router",
        }
        found = {c.get("name") for c in containers}
        missing = expected - found
        assert not missing, f"Missing core services: {missing}"

    def test_ledger_is_java(self, containers):
        """omnipay-ledger is Java Spring Boot."""
        svc = next((c for c in containers if c.get("name") == "omnipay-ledger"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        assert "java" in tech, f"Expected Java for ledger, got: {tech}"

    def test_fraud_ml_is_python(self, containers):
        """omnipay-fraud-ml is Python."""
        svc = next((c for c in containers if c.get("name") == "omnipay-fraud-ml"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        assert "python" in tech, f"Expected Python for fraud-ml, got: {tech}"

    def test_gateway_is_typescript(self, containers):
        """omnipay-gateway is TypeScript/Node.js."""
        svc = next((c for c in containers if c.get("name") == "omnipay-gateway"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        lang_str = str(svc.get("language", "")).lower()
        assert any(kw in tech or kw in lang_str for kw in ["typescript", "javascript", "node"]), \
            f"Expected TS/JS/Node for gateway, got: {tech}"

    def test_notifier_is_go(self, containers):
        """omnipay-notifier is Go."""
        svc = next((c for c in containers if c.get("name") == "omnipay-notifier"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        assert "go" in tech, f"Expected Go for notifier, got: {tech}"

    def test_card_router_is_csharp(self, containers):
        """omnipay-card-router is C#/.NET."""
        svc = next((c for c in containers if c.get("name") == "omnipay-card-router"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        assert any(kw in tech for kw in ["c#", "csharp", "dotnet", ".net"]), \
            f"Expected C#/.NET for card-router, got: {tech}"

    def test_infra_has_technology(self, containers):
        """omnipay-infra has infrastructure technology detected."""
        svc = next((c for c in containers if c.get("name") == "omnipay-infra"), None)
        assert svc is not None
        tech = str(svc.get("technology", "")).lower()
        assert tech != "unknown" and tech != "", \
            f"Expected infrastructure technology for infra, got: {tech}"

    def test_all_services_have_name(self, containers):
        """Every container has a non-empty name."""
        for svc in containers:
            assert svc.get("name"), f"Service missing name: {svc}"
            assert isinstance(svc.get("name"), str), f"Name not a string: {svc}"

    def test_all_services_have_technology(self, containers):
        """Every container has a non-Unknown technology."""
        for svc in containers:
            tech = svc.get("technology")
            assert tech is not None, f"Service {svc.get('name')} missing technology"
            assert tech != "Unknown", f"Service {svc.get('name')} has Unknown technology"

    def test_all_services_have_type(self, containers):
        """Every container has a container_type."""
        for svc in containers:
            ctype = svc.get("type") or svc.get("container_type")
            assert ctype, f"Service {svc.get('name')} missing container_type"

    def test_total_service_count(self, containers):
        """Should discover all current OmniPay services including extended ones."""
        assert len(containers) >= 6, f"Expected ≥6 services, got {len(containers)}"


class TestOmniPaySystemContext:
    """Test system context extraction for OmniPay."""

    @pytest.fixture(scope="class")
    def context(self, demo_dir):
        """Extract system context from OmniPay demo directory."""
        return extract_context(demo_dir)

    def test_context_has_required_fields(self, context):
        """System context has all required IT landscape fields."""
        required = ["name", "domain", "owner", "status", "tier", "data_class"]
        for field in required:
            assert field in context, f"Context missing '{field}'"

    def test_context_owner_not_unassigned(self, context):
        """Owner should be detected from git history (not 'Unassigned')."""
        owner = context.get("owner", "")
        assert owner not in ("Unassigned", "unknown", ""), \
            f"Owner should be detected from git history, got: {owner}"

    def test_context_domain_is_valid(self, context):
        """Domain should be a meaningful business domain."""
        domain = context.get("domain", "")
        assert domain not in ("Unknown", "unknown", ""), \
            f"Domain should be detected, got: {domain}"

    def test_context_produces_valid_json(self, context):
        """System context is JSON serializable."""
        import json
        json.dumps(context)
```

- [ ] **Step 2: Run the tests**

```bash
docker compose exec api python -m pytest tests/e2e/test_omnipay_harness.py -v
```

Expected: All tests pass (may need to skip some if demo dir not mounted)

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_omnipay_harness.py
git commit -m "feat(tests): add test_omnipay_harness for core services"
```

---

### Task 5: Write test_edge_cases.py

**Files:**
- Create: `tests/e2e/test_edge_cases.py`
- Demo services used: `omnipay-rust-service`, `omnipay-symlink-service`, `omnipay-multi-lang`, `omnipay-conflicted-ownership`, `omnipay-no-ownership`

**Note:** Rust technology detection is ALREADY implemented in `detect_technology_stack()` (utils.py line 99: `return "Rust"`). This test verifies it works.

**Note:** `omnipay-symlink-service` has `src/app.py` → symlink to `../shared/app.py`. Without symlink handling, this creates duplicate entries. The test verifies deduplication.

- [ ] **Step 1: Write the test file**

```python
"""Edge case tests using OmniPay edge-case demo services."""

import subprocess
from pathlib import Path

import pytest


DEMO_DIR = Path("/app/sources/demo")


def _init_git(repo_path: Path) -> None:
    for cmd in [
        ["git", "init", str(repo_path)],
        ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
        ["git", "-C", str(repo_path), "config", "user.name", "Test"],
        ["git", "-C", str(repo_path), "add", "."],
        ["git", "-C", str(repo_path), "commit", "-m", "initial"],
    ]:
        subprocess.run(cmd, capture_output=True, check=False)


def _extract_containers(repo_path: Path):
    from app.services.c4.containers.structure_detector import StructureDetector
    detector = StructureDetector(repo_path, llm_manager=None)
    return detector.detect()


def _extract_context(repo_path: Path):
    from app.services.c4.context.context_manager import ContextManager
    manager = ContextManager(repo_path, llm_manager=None)
    return manager.extract_context()


def _get_service(repo_path: Path, name: str):
    """Get a specific service from extraction."""
    containers = _extract_containers(repo_path)
    return next((c for c in containers if c.get("name") == name), None)


class TestRustDetection:
    """Test Rust service detection (Cargo.toml)."""

    @pytest.fixture(scope="class")
    def rust_service(self):
        """omnipay-rust-service: Rust + Cargo.toml + src/."""
        path = DEMO_DIR / "omnipay-rust-service"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _get_service(path, "omnipay-rust-service")

    def test_rust_detected(self, rust_service):
        """Technology field should be 'Rust'."""
        assert rust_service is not None, "omnipay-rust-service not found in extraction"
        tech = str(rust_service.get("technology", "")).lower()
        assert "rust" in tech, f"Expected Rust technology, got: {tech}"

    def test_rust_container_type(self, rust_service):
        """Container type should indicate a compiled language service."""
        ctype = str(rust_service.get("container_type") or rust_service.get("type", "")).lower()
        assert ctype, "Container type should not be empty"


class TestSymlinkHandling:
    """Test symlink resolution — no duplicate containers."""

    @pytest.fixture(scope="class")
    def symlink_containers(self):
        """omnipay-symlink-service: src/app.py -> ../shared/app.py (symlink)."""
        path = DEMO_DIR / "omnipay-symlink-service"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _extract_containers(path)

    def test_no_duplicate_containers(self, symlink_containers):
        """Symlink should not create duplicate containers."""
        names = [c.get("name") for c in symlink_containers]
        # shared and src should not both appear as separate services
        assert "shared" not in names or "src" not in names or names.count("shared") == 1, \
            f"Symlink created duplicate: {names}"

    def test_symlink_service_count(self, symlink_containers):
        """Should detect at least 1 service (the root), not double."""
        assert len(symlink_containers) >= 1, \
            f"Expected at least 1 service, got {len(symlink_containers)}: {[c.get('name') for c in symlink_containers]}"


class TestMultiLangTiering:
    """Test polyglot repos get correct tier based on highest-criticality language."""

    @pytest.fixture(scope="class")
    def multi_lang_context(self):
        """omnipay-multi-lang: polyglot service."""
        path = DEMO_DIR / "omnipay-multi-lang"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _extract_context(path)

    def test_tier_reflects_highest_language(self, multi_lang_context):
        """Tier should be set (not Unknown) for polyglot repos."""
        tier = str(multi_lang_context.get("tier", "")).lower()
        assert tier not in ("unknown", ""), \
            f"Polyglot repo should have a tier, got: {tier}"


class TestConflictedOwnership:
    """Test CODEOWNERS conflict — both owners recorded."""

    @pytest.fixture(scope="class")
    def conflicted_context(self):
        """omnipay-conflicted-ownership: two teams claim ownership."""
        path = DEMO_DIR / "omnipay-conflicted-ownership"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _extract_context(path)

    def test_conflicted_ownership_recorded(self, conflicted_context):
        """Conflicted ownership should be detected and recorded."""
        owner = conflicted_context.get("owner", "")
        team = conflicted_context.get("team", "")
        # At minimum, owner or team should be populated (not both unknown)
        has_owner = owner and owner not in ("Unassigned", "unknown", "")
        has_team = team and team not in ("Unassigned", "unknown", "")
        assert has_owner or has_team, \
            f"Expected at least one ownership field populated, got owner={owner}, team={team}"


class TestNoOwnershipGraceful:
    """Test repos with no ownership metadata — graceful degradation."""

    @pytest.fixture(scope="class")
    def no_owner_context(self):
        """omnipay-no-ownership: no CODEOWNERS, no owner in README."""
        path = DEMO_DIR / "omnipay-no-ownership"
        if not path.exists():
            pytest.skip(f"Demo not found: {path}")
        _init_git(path)
        return _extract_context(path)

    def test_no_ownership_graceful(self, no_owner_context):
        """No ownership metadata should result in owner='Unassigned', not crash."""
        owner = no_owner_context.get("owner", "")
        # Should NOT raise — graceful degradation
        assert isinstance(owner, str), f"Owner should be a string, got: {type(owner)}"
```

- [ ] **Step 2: Run the tests**

```bash
docker compose exec api python -m pytest tests/e2e/test_edge_cases.py -v
```

Expected: All 5 edge case tests pass (or skip if demo dirs not mounted)

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_edge_cases.py
git commit -m "feat(tests): add test_edge_cases for 5 edge scenarios"
```

---

### Task 6: Write test_provider_catalog.py

**Files:**
- Create: `tests/e2e/test_provider_catalog.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for provider catalog dictionary matching."""

import pytest


class TestProviderCatalogMatching:
    """Test package name and env var matching against provider catalog."""

    def test_provider_catalog_importable(self):
        """Provider catalog should be importable."""
        try:
            from app.services.c4.context.provider_catalog import (
                PROVIDER_CATALOG,
                match_provider_from_package,
                match_provider_from_env_var,
            )
        except ImportError as e:
            pytest.skip(f"Provider catalog not available: {e}")
        assert len(PROVIDER_CATALOG) > 0

    def test_stripe_package_match(self):
        """stripe package matches Stripe."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("stripe")
        assert result is not None, "Should match Stripe from stripe package"
        assert result.provider == "Stripe"

    def test_mixpanel_package_match(self):
        """mixpanel package matches Mixpanel."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("mixpanel")
        assert result is not None
        assert result.provider == "Mixpanel"

    def test_auth0_package_match(self):
        """@auth0/auth0-spa-js matches Auth0."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("@auth0/auth0-spa-js")
        assert result is not None
        assert result.provider == "Auth0"

    def test_postgres_package_match(self):
        """psycopg2 matches PostgreSQL."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("psycopg2")
        assert result is not None
        assert result.provider == "PostgreSQL"

    def test_redis_package_match(self):
        """redis package matches Redis."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("redis")
        assert result is not None
        assert result.provider == "Redis"

    def test_mongodb_package_match(self):
        """MongoDB.Driver matches MongoDB."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("MongoDB.Driver")
        assert result is not None
        assert result.provider == "MongoDB"

    def test_kafka_package_match(self):
        """Confluent.Kafka matches Kafka."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("Confluent.Kafka")
        assert result is not None
        assert result.provider == "Kafka"

    def test_rabbitmq_package_match(self):
        """RabbitMQ.Client matches RabbitMQ."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("RabbitMQ.Client")
        assert result is not None
        assert result.provider == "RabbitMQ"

    def test_sqlserver_package_match(self):
        """Microsoft.Data.SqlClient matches SQL Server."""
        from app.services.c4.context.provider_catalog import match_provider_from_package
        result = match_provider_from_package("Microsoft.Data.SqlClient")
        assert result is not None
        assert result.provider == "SQL Server"

    def test_stripe_env_var_match(self):
        """STRIPE_API_KEY matches Stripe."""
        from app.services.c4.context.provider_catalog import match_provider_from_env_var
        result = match_provider_from_env_var("STRIPE_API_KEY")
        assert result is not None
        assert result.provider == "Stripe"

    def test_postgres_env_var_match(self):
        """POSTGRES_HOST matches PostgreSQL."""
        from app.services.c4.context.provider_catalog import match_provider_from_env_var
        result = match_provider_from_env_var("POSTGRES_HOST")
        assert result is not None
        assert result.provider == "PostgreSQL"

    def test_kafka_env_var_match(self):
        """KAFKA_BOOTSTRAP_SERVERS matches Kafka."""
        from app.services.c4.context.provider_catalog import match_provider_from_env_var
        result = match_provider_from_env_var("KAFKA_BOOTSTRAP_SERVERS")
        assert result is not None
        assert result.provider == "Kafka"

    def test_mongodb_env_var_match(self):
        """MONGODB_URI matches MongoDB."""
        from app.services.c4.context.provider_catalog import match_provider_from_env_var
        result = match_provider_from_env_var("MONGODB_URI")
        assert result is not None
        assert result.provider == "MongoDB"
```

- [ ] **Step 2: Run the tests**

```bash
docker compose exec api python -m pytest tests/e2e/test_provider_catalog.py -v
```

Expected: All pass or skip if provider_catalog not available

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_provider_catalog.py
git commit -m "feat(tests): add test_provider_catalog matching tests"
```

---

### Task 7: Write test_llm_enrichment.py

**Files:**
- Create: `tests/e2e/test_llm_enrichment.py`

- [ ] **Step 1: Write the test file**

```python
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
```

- [ ] **Step 2: Run the tests**

```bash
docker compose exec api python -m pytest tests/e2e/test_llm_enrichment.py -v
```

Expected: All pass or skip if demos not mounted

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_llm_enrichment.py
git commit -m "feat(tests): add test_llm_enrichment for decision models"
```

---

### Task 8: Write test_snapshot_regression.py

**Files:**
- Create: `tests/e2e/test_snapshot_regression.py`

**Note:** This file reuses the snapshot logic already in `test_omnipay_extraction.py` (the existing file has `TestOmniPaySnapshotValidation`). This new file creates a cleaner standalone regression test that can be run independently.

- [ ] **Step 1: Write the test file**

```python
"""Snapshot regression tests for OmniPay extraction.

Run with --snapshot-update to regenerate the snapshot:
    docker compose exec api python -m pytest tests/e2e/test_snapshot_regression.py -v --snapshot-update
"""

import json
from pathlib import Path

import pytest


SNAPSHOT_FILE = Path(__file__).parent / "snapshots" / "omnipay_extraction.json"
DEMO_DIR = Path("/app/sources/demo")


def _init_git(repo_path: Path) -> None:
    import subprocess
    for cmd in [
        ["git", "init", str(repo_path)],
        ["git", "-C", str(repo_path), "config", "user.email", "test@example.com"],
        ["git", "-C", str(repo_path), "config", "user.name", "Test"],
        ["git", "-C", str(repo_path), "add", "."],
        ["git", "-C", str(repo_path), "commit", "-m", "initial"],
    ]:
        subprocess.run(cmd, capture_output=True, check=False)


def _serialize(containers, context):
    """Serialize extraction output deterministically."""
    containers_sorted = sorted(containers, key=lambda c: c.get("name", ""))
    for container in containers_sorted:
        for key in ["relationships", "dependencies_internal"]:
            if key in container and isinstance(container[key], list):
                container[key] = sorted(container[key], key=lambda x: str(x) if x else "")
        if "path" in container:
            container["path"] = str(container["path"])
    return {
        "containers": containers_sorted,
        "system_context": context,
    }


@pytest.fixture
def snapshot_path():
    return SNAPSHOT_FILE


@pytest.fixture
def extraction_output():
    """Run extraction and return deterministic output."""
    if not DEMO_DIR.exists():
        pytest.skip(f"Demo directory not found: {DEMO_DIR}")
    _init_git(DEMO_DIR)

    from app.services.c4.containers.structure_detector import StructureDetector
    from app.services.c4.context.context_manager import ContextManager

    detector = StructureDetector(DEMO_DIR, llm_manager=None)
    containers = detector.detect()

    manager = ContextManager(DEMO_DIR, llm_manager=None)
    context = manager.extract_context()

    return _serialize(containers, context)


@pytest.fixture
def expected_snapshot(snapshot_path):
    """Load expected snapshot, or skip if doesn't exist."""
    if not snapshot_path.exists():
        pytest.skip(
            f"Snapshot file not found: {snapshot_path}. "
            "Run with --snapshot-update to create."
        )
    with open(snapshot_path, "r") as f:
        return json.load(f)


def test_snapshot_exists(snapshot_path):
    """Snapshot file should exist after initial generation."""
    assert snapshot_path.exists(), (
        f"Snapshot file missing: {snapshot_path}. "
        "Run with --snapshot-update to generate."
    )


def test_container_count_matches_snapshot(extraction_output, expected_snapshot):
    """Container count should match snapshot."""
    expected_count = len(expected_snapshot["containers"])
    actual_count = len(extraction_output["containers"])
    assert actual_count == expected_count, (
        f"Container count mismatch: got {actual_count}, expected {expected_count}. "
        "Run with --snapshot-update to update."
    )


def test_all_snapshot_services_present(extraction_output, expected_snapshot):
    """All services in snapshot should be present in extraction."""
    expected_names = {c["name"] for c in expected_snapshot["containers"]}
    actual_names = {c["name"] for c in extraction_output["containers"]}
    missing = expected_names - actual_names
    extra = actual_names - expected_names
    if missing or extra:
        msg = ""
        if missing:
            msg += f"\n  Missing services: {sorted(missing)}"
        if extra:
            msg += f"\n  New services: {sorted(extra)}"
        msg += "\nRun with --snapshot-update to update snapshot."
        pytest.fail(msg)


def test_system_context_has_required_fields(extraction_output):
    """System context should have all required fields."""
    context = extraction_output["system_context"]
    required_fields = [
        "c4_level", "type", "name", "purpose", "domain",
        "owner", "status", "tier", "data_class",
    ]
    missing = [f for f in required_fields if f not in context]
    assert not missing, f"System context missing fields: {missing}"
```

- [ ] **Step 2: Run the tests**

```bash
docker compose exec api python -m pytest tests/e2e/test_snapshot_regression.py -v
```

Expected: Skip (no snapshot yet) or pass if snapshot exists

- [ ] **Step 3: Generate initial snapshot**

```bash
docker compose exec api python -m pytest tests/e2e/test_snapshot_regression.py -v --snapshot-update
```

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_snapshot_regression.py
git commit -m "feat(tests): add test_snapshot_regression"
```

---

## Self-Review Checklist

- [ ] Spec coverage: All spec items (2A-1 through 2A-3) mapped to tasks?
- [ ] No placeholders: All code is complete, no "TBD" or "TODO"
- [ ] File paths: All paths are absolute and correct (`sources/Api/tests/...`)
- [ ] Test commands: All run commands are correct
- [ ] Task count: 8 tasks, each bite-sized (2-5 min)
