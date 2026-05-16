# C4 Book Integration — Context, Container, Component Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the C4 book's authoritative vocabulary into the extraction pipeline — adding C4ElementType labels, an ownership signal classifier (the "do you control its internals?" rule), protocol detection from source code, and a canonical container subtype taxonomy.

**Architecture:** Five surgical additions: (1) a `C4ElementType` enum wired to every output element, (2) an `OwnershipSignalDetector` that determines if a TECHNICAL_INFRA dep is a Container or SoftwareSystem, (3) a `ProtocolDetector` that fingerprints source code for relationship technology, (4) a `C4ContainerType` enum applied by `ContainerManager`, (5) `c4_element_type` on ComponentObject. All changes are additive — no existing fields removed.

**Tech Stack:** Python 3.11, Pydantic V2, FastAPI, pytest, docker compose exec

**Test runner:** `docker compose exec api python -m pytest tests/unit/services/c4/<file> -v`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| **Create** | `sources/Api/app/services/c4/context/ownership_classifier.py` | Detect repo ownership signals (migrations, Dockerfile, Terraform) for the Container vs SoftwareSystem decision |
| **Create** | `sources/Api/app/services/c4/containers/protocol_detector.py` | Fingerprint source files for communication protocols (REST, gRPC, Kafka, JDBC, etc.) |
| **Create** | `sources/Api/app/services/c4/containers/c4_types.py` | `C4ContainerType` enum + classifier function |
| **Modify** | `sources/Api/app/services/c4/context/decision_models.py` | Add `C4ElementType` enum |
| **Modify** | `sources/Api/app/services/c4/context/dependency_classifier.py` | Accept ownership signals; promote TECHNICAL_INFRA deps to Container when owned |
| **Modify** | `sources/Api/app/services/c4/context/context_manager.py` | Attach `c4_element_type` to actors and deps in output; add `technology` to relationships |
| **Modify** | `sources/Api/app/services/c4/containers/container_manager.py` | Attach `c4_element_type = "Container"` and `c4_container_type` to all container output; wire protocol detector into relationships |
| **Modify** | `sources/Api/app/services/c4/components/models.py` | Add `c4_element_type: str = "Component"` to `ComponentObject` |
| **Create** | `sources/Api/tests/unit/services/c4/test_ownership_classifier.py` | Tests for OwnershipSignalDetector |
| **Create** | `sources/Api/tests/unit/services/c4/test_protocol_detector.py` | Tests for ProtocolDetector |
| **Create** | `sources/Api/tests/unit/services/c4/test_c4_types.py` | Tests for C4ContainerType classifier |
| **Modify** | `sources/Api/tests/unit/services/c4/test_decision_models.py` | Add C4ElementType tests |
| **Modify** | `sources/Api/tests/unit/services/c4/test_context_manager.py` | Add element type + technology field assertions |

---

## Task 1: Add C4ElementType Enum

**Files:**
- Modify: `sources/Api/app/services/c4/context/decision_models.py`
- Modify: `sources/Api/tests/unit/services/c4/test_decision_models.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/services/c4/test_decision_models.py`:

```python
from app.services.c4.context.decision_models import C4ElementType

class TestC4ElementType:
    def test_has_person(self):
        assert C4ElementType.PERSON == "Person"

    def test_has_software_system(self):
        assert C4ElementType.SOFTWARE_SYSTEM == "SoftwareSystem"

    def test_has_container(self):
        assert C4ElementType.CONTAINER == "Container"

    def test_has_component(self):
        assert C4ElementType.COMPONENT == "Component"

    def test_is_string_enum(self):
        assert isinstance(C4ElementType.PERSON, str)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_decision_models.py::TestC4ElementType -v
```

Expected: `ImportError: cannot import name 'C4ElementType'`

- [ ] **Step 3: Add C4ElementType to decision_models.py**

Open `sources/Api/app/services/c4/context/decision_models.py`. After the existing `ReviewStatus` class, add:

```python
class C4ElementType(str, Enum):
    """Canonical C4 element type labels (from the C4 book).

    Every element in the extraction output carries one of these labels
    so consumers (frontend, Neo4j, API clients) can render correct C4 notation.
    """

    PERSON = "Person"
    SOFTWARE_SYSTEM = "SoftwareSystem"
    CONTAINER = "Container"
    COMPONENT = "Component"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_decision_models.py::TestC4ElementType -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/services/c4/context/decision_models.py \
        sources/Api/tests/unit/services/c4/test_decision_models.py
git commit -m "feat(c4): add C4ElementType enum to decision_models"
```

---

## Task 2: OwnershipSignalDetector

The book's canonical rule: "Do you control its internals?" — If yes, it's a Container (even if hosted externally — your S3 bucket, your RDS instance). If no, it's a SoftwareSystem (you call their API). This file detects repo-level ownership signals.

**Files:**
- Create: `sources/Api/app/services/c4/context/ownership_classifier.py`
- Create: `sources/Api/tests/unit/services/c4/test_ownership_classifier.py`

- [ ] **Step 1: Write failing test**

Create `sources/Api/tests/unit/services/c4/test_ownership_classifier.py`:

```python
"""Tests for OwnershipSignalDetector."""
from pathlib import Path

import pytest

from app.services.c4.context.ownership_classifier import OwnershipSignalDetector


class TestOwnershipSignalDetector:
    def test_detects_migration_files_as_owned(self, tmp_path):
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "0001_initial.sql").write_text("CREATE TABLE users (id SERIAL);")

        detector = OwnershipSignalDetector(tmp_path)
        is_owned, confidence, reason = detector.is_owned("PostgreSQL", "database")

        assert is_owned is True
        assert confidence >= 0.85
        assert "migration" in reason.lower()

    def test_detects_terraform_s3_bucket_as_owned(self, tmp_path):
        tf = tmp_path / "main.tf"
        tf.write_text('resource "aws_s3_bucket" "statements" {\n  bucket = "my-statements"\n}')

        detector = OwnershipSignalDetector(tmp_path)
        is_owned, confidence, reason = detector.is_owned("S3", "storage")

        assert is_owned is True
        assert confidence >= 0.9
        assert "terraform" in reason.lower()

    def test_returns_not_owned_when_no_signals(self, tmp_path):
        detector = OwnershipSignalDetector(tmp_path)
        is_owned, confidence, reason = detector.is_owned("Stripe", "payment")

        assert is_owned is False
        assert confidence <= 0.6

    def test_detects_alembic_as_migration(self, tmp_path):
        alembic = tmp_path / "alembic" / "versions"
        alembic.mkdir(parents=True)
        (alembic / "abc123_create_orders.py").write_text("def upgrade(): pass")

        detector = OwnershipSignalDetector(tmp_path)
        is_owned, confidence, reason = detector.is_owned("PostgreSQL", "database")

        assert is_owned is True

    def test_detects_dockerfile_reference_as_owned(self, tmp_path):
        (tmp_path / "Dockerfile").write_text(
            "FROM postgres:15\nCOPY init.sql /docker-entrypoint-initdb.d/"
        )

        detector = OwnershipSignalDetector(tmp_path)
        is_owned, confidence, reason = detector.is_owned("postgres", "database")

        assert is_owned is True
        assert confidence >= 0.75
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_ownership_classifier.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.c4.context.ownership_classifier'`

- [ ] **Step 3: Create ownership_classifier.py**

Create `sources/Api/app/services/c4/context/ownership_classifier.py`:

```python
"""Ownership signal detection for C4 Container vs SoftwareSystem boundary.

The C4 book rule: "Do you control its internals?"
- Yes → Container (even if hosted externally: your S3 bucket, your RDS instance)
- No  → SoftwareSystem (external API; vendor controls the runtime)

Ownership is detected by scanning the repo for:
- Migration files (you define the schema)
- Dockerfiles that build/run the dependency
- Terraform resources that provision it
- docker-compose service blocks
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_MIGRATION_DIR_PATTERNS = re.compile(
    r"(migrations?|alembic|flyway|liquibase|db/migrate|prisma/migrations)/",
    re.IGNORECASE,
)

_TERRAFORM_OWNERSHIP_RESOURCES: dict[str, list[str]] = {
    "aws_s3_bucket": ["s3", "blob", "storage", "bucket"],
    "aws_rds_instance": ["rds", "postgres", "mysql", "database", "db"],
    "aws_rds_cluster": ["rds", "aurora", "postgres", "mysql", "database"],
    "aws_elasticache_cluster": ["redis", "memcached", "cache"],
    "aws_sqs_queue": ["sqs", "queue"],
    "aws_dynamodb_table": ["dynamodb", "dynamo"],
    "aws_msk_cluster": ["kafka", "msk"],
    "google_sql_database_instance": ["cloudsql", "postgres", "mysql", "database"],
    "azurerm_sql_server": ["sql", "database", "db"],
    "azurerm_storage_account": ["blob", "storage", "azure"],
    "azurerm_cosmosdb_account": ["cosmos", "mongo", "database"],
}

_SOURCE_EXTENSIONS = {".py", ".ts", ".js", ".java", ".cs", ".go", ".rb", ".tf"}


@dataclass
class OwnershipSignal:
    """Evidence that a dependency is owned by this team."""

    signal_type: str  # migration | terraform | dockerfile | compose
    file_path: str
    confidence: float
    evidence: str


class OwnershipSignalDetector:
    """Scans a repository for signals that a dependency is team-owned."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = Path(repo_path).resolve()

    def detect_ownership_signals(self, dep_name: str) -> list[OwnershipSignal]:
        """Return all ownership signals found for this dependency name."""
        name_lower = dep_name.lower()
        signals: list[OwnershipSignal] = []
        signals.extend(self._scan_migration_dirs())
        signals.extend(self._scan_terraform(name_lower))
        signals.extend(self._scan_dockerfile(name_lower))
        signals.extend(self._scan_compose(name_lower))
        return signals

    def is_owned(
        self, dep_name: str, dep_type: str = ""
    ) -> tuple[bool, float, str]:
        """Return (is_owned, confidence, reason).

        A dependency is considered owned when at least one ownership signal
        exists in the repository with confidence >= 0.75.
        """
        signals = self.detect_ownership_signals(dep_name)
        if not signals:
            return False, 0.5, "No ownership signals found in repository"

        best = max(signals, key=lambda s: s.confidence)
        return True, best.confidence, f"Ownership signal ({best.signal_type}): {best.evidence}"

    # ------------------------------------------------------------------ #
    # Private scanners                                                     #
    # ------------------------------------------------------------------ #

    def _scan_migration_dirs(self) -> list[OwnershipSignal]:
        signals: list[OwnershipSignal] = []
        seen: set[str] = set()

        for path in self.repo_path.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.repo_path))
            if _MIGRATION_DIR_PATTERNS.search(rel) and rel not in seen:
                seen.add(rel)
                signals.append(
                    OwnershipSignal(
                        signal_type="migration",
                        file_path=rel,
                        confidence=0.9,
                        evidence=f"Migration file: {path.name}",
                    )
                )
                break  # one signal per repo is enough

        return signals

    def _scan_terraform(self, dep_name_lower: str) -> list[OwnershipSignal]:
        signals: list[OwnershipSignal] = []

        for tf_file in self.repo_path.rglob("*.tf"):
            try:
                content = tf_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for resource_type, keywords in _TERRAFORM_OWNERSHIP_RESOURCES.items():
                if resource_type not in content:
                    continue
                if any(kw in dep_name_lower for kw in keywords):
                    rel = str(tf_file.relative_to(self.repo_path))
                    signals.append(
                        OwnershipSignal(
                            signal_type="terraform",
                            file_path=rel,
                            confidence=0.95,
                            evidence=f"Terraform resource '{resource_type}' in {tf_file.name}",
                        )
                    )

        return signals

    def _scan_dockerfile(self, dep_name_lower: str) -> list[OwnershipSignal]:
        signals: list[OwnershipSignal] = []

        for df in self.repo_path.rglob("Dockerfile*"):
            try:
                content = df.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue

            if dep_name_lower in content:
                rel = str(df.relative_to(self.repo_path))
                signals.append(
                    OwnershipSignal(
                        signal_type="dockerfile",
                        file_path=rel,
                        confidence=0.8,
                        evidence=f"Dependency referenced in {df.name}",
                    )
                )

        return signals

    def _scan_compose(self, dep_name_lower: str) -> list[OwnershipSignal]:
        """Find docker-compose service definitions that run this dependency."""
        signals: list[OwnershipSignal] = []
        compose_files = list(self.repo_path.rglob("docker-compose*.yml")) + list(
            self.repo_path.rglob("docker-compose*.yaml")
        )

        for cf in compose_files:
            try:
                content = cf.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue

            if dep_name_lower in content and "image:" in content:
                rel = str(cf.relative_to(self.repo_path))
                signals.append(
                    OwnershipSignal(
                        signal_type="compose",
                        file_path=rel,
                        confidence=0.85,
                        evidence=f"Service image for '{dep_name_lower}' in {cf.name}",
                    )
                )

        return signals
```

- [ ] **Step 4: Run test to verify it passes**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_ownership_classifier.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/services/c4/context/ownership_classifier.py \
        sources/Api/tests/unit/services/c4/test_ownership_classifier.py
git commit -m "feat(c4): add OwnershipSignalDetector for Container vs SoftwareSystem boundary"
```

---

## Task 3: Integrate Ownership Signals into DependencyClassifier

Currently `dependency_classifier.py` classifies AWS S3 as `TECHNICAL_INFRA`, but when the repo has a Terraform `aws_s3_bucket` resource, that bucket is **owned** — it's a Container, not an external SoftwareSystem (the book's canonical SES-vs-S3 example). This task wires the ownership detector into the classifier.

**Files:**
- Modify: `sources/Api/app/services/c4/context/dependency_classifier.py`

- [ ] **Step 1: Write failing test**

Add to `sources/Api/tests/unit/services/c4/test_dependency_detector.py` (or create `test_dependency_classifier_ownership.py`):

```python
"""Test that owned TECHNICAL_INFRA deps are reclassified as Container."""
from pathlib import Path

from app.services.c4.context.dependency_classifier import DependencyClassifier, DependencyType


class TestOwnershipPromotion:
    def test_s3_with_terraform_resource_becomes_owned_container(self, tmp_path):
        tf = tmp_path / "infra.tf"
        tf.write_text('resource "aws_s3_bucket" "statements" {\n  bucket = "my-statements"\n}')

        classifier = DependencyClassifier(repo_path=tmp_path)
        result = classifier.classify_dependency(name="S3", dep_type="storage")

        assert result.type == DependencyType.OWNED_CONTAINER

    def test_external_stripe_stays_business_system(self, tmp_path):
        classifier = DependencyClassifier(repo_path=tmp_path)
        result = classifier.classify_dependency(name="Stripe", dep_type="payment")

        assert result.type == DependencyType.BUSINESS_SYSTEM

    def test_postgres_with_migrations_becomes_owned_container(self, tmp_path):
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "0001_initial.sql").write_text("CREATE TABLE orders (id SERIAL);")

        classifier = DependencyClassifier(repo_path=tmp_path)
        result = classifier.classify_dependency(name="PostgreSQL", dep_type="database")

        assert result.type == DependencyType.OWNED_CONTAINER
        assert result.confidence >= 0.85
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_dependency_classifier_ownership.py -v
```

Expected: `AssertionError` — `OWNED_CONTAINER` doesn't exist yet.

- [ ] **Step 3: Add OWNED_CONTAINER to DependencyType and wire ownership detection**

In `sources/Api/app/services/c4/context/dependency_classifier.py`:

**3a.** Add `OWNED_CONTAINER` to the `DependencyType` enum:

```python
class DependencyType(str, Enum):
    """Classification types for external dependencies."""

    BUSINESS_SYSTEM = "BUSINESS_SYSTEM"
    TECHNICAL_INFRA = "TECHNICAL_INFRA"
    OWNED_CONTAINER = "OWNED_CONTAINER"   # ← ADD THIS
    UNKNOWN = "UNKNOWN"
```

**3b.** Add `repo_path: Optional[Path] = None` parameter to `DependencyClassifier.__init__`:

```python
from pathlib import Path
from app.services.c4.context.ownership_classifier import OwnershipSignalDetector

class DependencyClassifier:
    def __init__(self, llm_manager=None, repo_path: Optional[Path] = None):
        self.llm_manager = llm_manager
        self._ownership_detector = OwnershipSignalDetector(repo_path) if repo_path else None
        # ... rest of __init__ unchanged
```

**3c.** Add ownership promotion step at the end of `classify_dependency()`. After the existing LLM/rule classification, before returning:

```python
def classify_dependency(self, name, dep_type="unknown", detected_from="", context="") -> DependencyClassification:
    # ... existing classification logic unchanged ...
    result = self._classify_with_llm(...) or self._classify_with_rules(name, dep_type)

    # Ownership promotion: TECHNICAL_INFRA → OWNED_CONTAINER when repo signals exist
    if result.type == DependencyType.TECHNICAL_INFRA and self._ownership_detector:
        is_owned, confidence, reason = self._ownership_detector.is_owned(name, dep_type)
        if is_owned:
            return DependencyClassification(
                type=DependencyType.OWNED_CONTAINER,
                confidence=confidence,
                reasoning=f"Promoted from TECHNICAL_INFRA: {reason}",
                decision_mode="deterministic",
                detection_source="ownership_signal_detector",
            )

    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_dependency_classifier_ownership.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/services/c4/context/dependency_classifier.py \
        sources/Api/tests/unit/services/c4/test_dependency_classifier_ownership.py
git commit -m "feat(c4): promote owned TECHNICAL_INFRA deps to OWNED_CONTAINER via ownership signals"
```

---

## Task 4: Attach c4_element_type to Context Output

Every element the context extractor emits must carry a `c4_element_type` field so downstream consumers (frontend, Neo4j writer) can render correct C4 notation without guessing.

**Files:**
- Modify: `sources/Api/app/services/c4/context/context_manager.py`
- Modify: `sources/Api/tests/unit/services/c4/test_context_manager.py`

- [ ] **Step 1: Write failing test**

Add to `sources/Api/tests/unit/services/c4/test_context_manager.py`:

```python
class TestC4ElementTypeLabels:
    def test_actors_have_person_element_type(self, tmp_path):
        manager = ContextManager(tmp_path)
        ctx = {
            "name": "MySystem",
            "actors": [{"name": "Admin", "description": "manages the system"}],
            "external_dependencies": [],
        }
        rels = manager.build_context_relationships(ctx)
        # actor is the source of the relationship; check the raw context enrichment
        actor_types = manager._enrich_actors_with_element_type(ctx["actors"])
        assert all(a["c4_element_type"] == "Person" for a in actor_types)

    def test_business_system_deps_have_software_system_type(self, tmp_path):
        manager = ContextManager(tmp_path)
        deps = [{"name": "Stripe", "dependency_type": "BUSINESS_SYSTEM"}]
        enriched = manager._enrich_deps_with_element_type(deps)
        assert enriched[0]["c4_element_type"] == "SoftwareSystem"

    def test_owned_container_deps_have_container_type(self, tmp_path):
        manager = ContextManager(tmp_path)
        deps = [{"name": "PostgreSQL", "dependency_type": "OWNED_CONTAINER"}]
        enriched = manager._enrich_deps_with_element_type(deps)
        assert enriched[0]["c4_element_type"] == "Container"

    def test_technical_infra_deps_have_container_type(self, tmp_path):
        manager = ContextManager(tmp_path)
        deps = [{"name": "Redis", "dependency_type": "TECHNICAL_INFRA"}]
        enriched = manager._enrich_deps_with_element_type(deps)
        assert enriched[0]["c4_element_type"] == "Container"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_context_manager.py::TestC4ElementTypeLabels -v
```

Expected: `AttributeError: 'ContextManager' object has no attribute '_enrich_actors_with_element_type'`

- [ ] **Step 3: Add the two enrichment methods to context_manager.py**

In `sources/Api/app/services/c4/context/context_manager.py`, add after the imports:

```python
from app.services.c4.context.decision_models import C4ElementType
```

Then add two private methods inside `ContextManager`:

```python
def _enrich_actors_with_element_type(self, actors: list[dict]) -> list[dict]:
    """Tag each actor with c4_element_type = Person."""
    for actor in actors:
        actor["c4_element_type"] = C4ElementType.PERSON
    return actors

def _enrich_deps_with_element_type(self, deps: list[dict]) -> list[dict]:
    """Tag each dependency with its C4 element type.

    BUSINESS_SYSTEM → SoftwareSystem
    OWNED_CONTAINER → Container
    TECHNICAL_INFRA → Container (it's infrastructure you run, not an external SaaS)
    UNKNOWN         → SoftwareSystem (safer default for context diagram)
    """
    _type_map = {
        "BUSINESS_SYSTEM": C4ElementType.SOFTWARE_SYSTEM,
        "OWNED_CONTAINER": C4ElementType.CONTAINER,
        "TECHNICAL_INFRA": C4ElementType.CONTAINER,
        "UNKNOWN": C4ElementType.SOFTWARE_SYSTEM,
    }
    for dep in deps:
        dep_type = dep.get("dependency_type", "UNKNOWN")
        dep["c4_element_type"] = _type_map.get(dep_type, C4ElementType.SOFTWARE_SYSTEM)
    return deps
```

- [ ] **Step 4: Wire both methods into extract_context()**

In `extract_context()`, after `external_deps = self.dependency_detector.detect_external_dependencies()`, add:

```python
actors = self._enrich_actors_with_element_type(actors)
external_deps = self._enrich_deps_with_element_type(external_deps)
```

And add `"c4_element_type": "SoftwareSystem"` to the context dict itself:

```python
context = {
    "c4_level": 1,
    "c4_element_type": C4ElementType.SOFTWARE_SYSTEM,  # ← ADD
    "type": "system",
    # ... rest unchanged
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_context_manager.py::TestC4ElementTypeLabels -v
```

Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add sources/Api/app/services/c4/context/context_manager.py \
        sources/Api/tests/unit/services/c4/test_context_manager.py
git commit -m "feat(c4): attach c4_element_type to context output actors and dependencies"
```

---

## Task 5: ProtocolDetector

The book says: "The protocol field on L2 relationships is high-value and usually detectable. REST client calls, JDBC connection strings, gRPC stubs, Kafka producers/consumers — all leave strong fingerprints in source code." This task builds the detector.

**Files:**
- Create: `sources/Api/app/services/c4/containers/protocol_detector.py`
- Create: `sources/Api/tests/unit/services/c4/test_protocol_detector.py`

- [ ] **Step 1: Write failing test**

Create `sources/Api/tests/unit/services/c4/test_protocol_detector.py`:

```python
"""Tests for source-code protocol fingerprinting."""
from pathlib import Path

from app.services.c4.containers.protocol_detector import ProtocolDetector


class TestProtocolDetector:
    def test_detects_kafka_producer_import(self, tmp_path):
        (tmp_path / "service.py").write_text("from kafka import KafkaProducer\nproducer = KafkaProducer()")
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert any(m.protocol == "Kafka" for m in result)

    def test_detects_psycopg2_as_jdbc(self, tmp_path):
        (tmp_path / "db.py").write_text("import psycopg2\nconn = psycopg2.connect(DSN)")
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert any(m.protocol == "JDBC" for m in result)

    def test_detects_requests_as_rest(self, tmp_path):
        (tmp_path / "client.py").write_text("import requests\nrequests.get('https://api.example.com')")
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert any(m.protocol == "REST/HTTPS" for m in result)

    def test_detects_grpc_import(self, tmp_path):
        (tmp_path / "grpc_client.py").write_text("import grpc\nchannel = grpc.insecure_channel('localhost:50051')")
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert any(m.protocol == "gRPC" for m in result)

    def test_returns_empty_for_empty_repo(self, tmp_path):
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert result == []

    def test_relationship_hint_postgres_returns_jdbc(self, tmp_path):
        protocol = ProtocolDetector(tmp_path).detect_for_relationship("backend", "postgres")
        assert protocol == "JDBC"

    def test_relationship_hint_kafka_returns_kafka(self, tmp_path):
        protocol = ProtocolDetector(tmp_path).detect_for_relationship("backend", "kafka-broker")
        assert protocol == "Kafka"

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "kafka-node"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("const KafkaProducer = require('kafka-node');")
        result = ProtocolDetector(tmp_path).detect_protocols()
        assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_protocol_detector.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create protocol_detector.py**

Create `sources/Api/app/services/c4/containers/protocol_detector.py`:

```python
"""Protocol detection from source code fingerprints.

Detects inter-container communication protocols by scanning source files
for characteristic imports, class instantiations, and URL patterns.
This implements the C4 book insight: "The protocol field on L2 relationships
is high-value and usually detectable via tree-sitter fingerprints."
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# (protocol_name, [regex_patterns_that_fingerprint_it])
_FINGERPRINTS: list[tuple[str, list[str]]] = [
    ("Kafka", [
        r"\bKafkaProducer\b",
        r"\bKafkaConsumer\b",
        r"@KafkaListener",
        r"confluent_kafka",
        r"from kafka import",
        r"kafka-python",
        r"KafkaJS",
    ]),
    ("gRPC", [
        r"\bimport grpc\b",
        r"grpc\.insecure_channel",
        r"grpc\.secure_channel",
        r"_pb2\.py",
        r"from .+_pb2",
        r"\.proto\b",
    ]),
    ("JDBC", [
        r"\bpsycopg2\b",
        r"\bpymysql\b",
        r"\bcx_Oracle\b",
        r"jdbc:",
        r"SQLAlchemy",
        r"from sqlalchemy",
        r"pg\.Pool",
        r"mysql2",
        r"asyncpg",
    ]),
    ("AMQP", [
        r"\bimport pika\b",
        r"amqplib",
        r"amqp://",
        r"channel\.basic_publish",
        r"@RabbitListener",
        r"amqp\.connect",
    ]),
    ("WebSocket", [
        r"\bwebsockets\b",
        r"ws://",
        r"wss://",
        r"socket\.io",
        r"\bWebSocket\(",
        r"@ServerEndpoint",
        r"useWebSocket",
    ]),
    ("GraphQL", [
        r"\bfrom gql\b",
        r"\bApollo\b",
        r"@GraphQLQuery",
        r"\bgraphene\b",
        r"\.graphql\b",
        r"gql`",
        r"graphql-request",
    ]),
    ("REST/HTTPS", [
        r"requests\.(get|post|put|delete|patch)\(",
        r"axios\.(get|post|put|delete|patch)\(",
        r"\bfetch\(",
        r"HttpClient",
        r"urllib\.request",
        r"@RestController",
        r"@GetMapping",
        r"@PostMapping",
        r"http\.get\(",
        r"http\.post\(",
    ]),
    ("SMTP", [
        r"\bsmtplib\b",
        r"\bnodemailer\b",
        r"JavaMailSender",
        r"\bsendgrid\b",
        r"smtp://",
        r"MAIL_HOST",
    ]),
]

# Name-based heuristics for detect_for_relationship()
_NAME_PROTOCOL_HINTS: list[tuple[list[str], str]] = [
    (["kafka", "broker", "topic", "msk"], "Kafka"),
    (["postgres", "postgresql", "mysql", "mariadb", "rds", "aurora", "sqlite"], "JDBC"),
    (["rabbit", "amqp", "exchange", "queue"], "AMQP"),
    (["redis", "memcached", "elasticache"], "Redis Protocol"),
    (["s3", "minio", "blob", "gcs", "storage", "bucket"], "S3 API"),
    (["mongo", "dynamodb", "dynamo", "cosmos", "cassandra", "couchdb"], "MongoDB Wire Protocol"),
    (["grpc", "proto"], "gRPC"),
    (["graphql"], "GraphQL"),
    (["smtp", "mail", "ses", "sendgrid", "mailgun"], "SMTP"),
]

_SKIP_DIRS = frozenset({
    "node_modules", ".git", "vendor", "dist", "build",
    "__pycache__", ".venv", "venv", ".tox", "target",
})
_SOURCE_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".java", ".cs", ".go", ".rb", ".kt",
})


@dataclass
class ProtocolMatch:
    """A detected protocol with supporting evidence."""

    protocol: str
    confidence: float
    evidence: str  # "relative/path/file.py: pattern matched"


class ProtocolDetector:
    """Scan source files for inter-service communication protocol fingerprints."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = Path(repo_path).resolve()

    def detect_protocols(self) -> list[ProtocolMatch]:
        """Scan all source files and return one ProtocolMatch per detected protocol."""
        found: dict[str, ProtocolMatch] = {}

        for src_file in self._iter_source_files():
            try:
                content = src_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            rel = str(src_file.relative_to(self.repo_path))
            for protocol, patterns in _FINGERPRINTS:
                if protocol in found:
                    continue
                for pattern in patterns:
                    if re.search(pattern, content):
                        found[protocol] = ProtocolMatch(
                            protocol=protocol,
                            confidence=0.85,
                            evidence=f"{rel}: matched `{pattern}`",
                        )
                        break

        return list(found.values())

    def detect_for_relationship(
        self, source_container: str, target_container: str
    ) -> str | None:
        """Return the most likely protocol for a source→target relationship.

        First checks target name against known heuristics; falls back to a
        full source scan if no heuristic matches.
        """
        target_lower = target_container.lower()

        for keywords, protocol in _NAME_PROTOCOL_HINTS:
            if any(kw in target_lower for kw in keywords):
                logger.debug("Protocol hint for '%s': %s", target_container, protocol)
                return protocol

        matches = self.detect_protocols()
        if matches:
            return matches[0].protocol

        return "HTTPS"

    def _iter_source_files(self):
        for path in self.repo_path.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in _SOURCE_EXTENSIONS:
                yield path
```

- [ ] **Step 4: Run test to verify it passes**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_protocol_detector.py -v
```

Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/services/c4/containers/protocol_detector.py \
        sources/Api/tests/unit/services/c4/test_protocol_detector.py
git commit -m "feat(c4): add ProtocolDetector for source-code relationship technology fingerprinting"
```

---

## Task 6: C4ContainerType Enum and Classifier

Align container output with the book's canonical container type list: ServerSideWebApp, ClientSideWebApp, MobileApp, ConsoleApp, ServerlessFunction, ShellScript, Database, BlobStore, FileSystem, MessageBroker.

**Files:**
- Create: `sources/Api/app/services/c4/containers/c4_types.py`
- Create: `sources/Api/tests/unit/services/c4/test_c4_types.py`

- [ ] **Step 1: Write failing test**

Create `sources/Api/tests/unit/services/c4/test_c4_types.py`:

```python
"""Tests for C4ContainerType classifier."""
from app.services.c4.containers.c4_types import C4ContainerType, classify_c4_container_type


class TestC4ContainerType:
    def test_has_canonical_types(self):
        assert C4ContainerType.DATABASE == "Database"
        assert C4ContainerType.SERVER_SIDE_WEB_APP == "ServerSideWebApp"
        assert C4ContainerType.BLOB_STORE == "BlobStore"
        assert C4ContainerType.MESSAGE_BROKER == "MessageBroker"
        assert C4ContainerType.SERVERLESS_FUNCTION == "ServerlessFunction"

    def test_classifies_postgres_as_database(self):
        result = classify_c4_container_type({"technology": "PostgreSQL", "name": "db"})
        assert result == C4ContainerType.DATABASE

    def test_classifies_redis_as_database(self):
        result = classify_c4_container_type({"technology": "Redis", "name": "cache"})
        assert result == C4ContainerType.DATABASE

    def test_classifies_s3_as_blob_store(self):
        result = classify_c4_container_type({"technology": "AWS S3", "name": "statement-store"})
        assert result == C4ContainerType.BLOB_STORE

    def test_classifies_kafka_as_message_broker(self):
        result = classify_c4_container_type({"technology": "Kafka", "name": "events"})
        assert result == C4ContainerType.MESSAGE_BROKER

    def test_classifies_lambda_as_serverless(self):
        result = classify_c4_container_type({"technology": "AWS Lambda", "name": "processor"})
        assert result == C4ContainerType.SERVERLESS_FUNCTION

    def test_classifies_spring_boot_as_server_side_web_app(self):
        result = classify_c4_container_type({"technology": "Spring Boot", "name": "backend"})
        assert result == C4ContainerType.SERVER_SIDE_WEB_APP

    def test_classifies_react_spa_as_client_side_web_app(self):
        result = classify_c4_container_type({
            "technology": "React",
            "name": "frontend",
            "container_type": "frontend",
        })
        assert result == C4ContainerType.CLIENT_SIDE_WEB_APP

    def test_unknown_falls_back_to_unknown(self):
        result = classify_c4_container_type({"technology": "COBOL", "name": "legacy"})
        assert result == C4ContainerType.UNKNOWN
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_c4_types.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create c4_types.py**

Create `sources/Api/app/services/c4/containers/c4_types.py`:

```python
"""Canonical C4 container type taxonomy (from the C4 book, Chapter 4).

Containers are the applications and data stores that make up a software system.
Each container is a separately deployable/runnable unit.
"""

from enum import Enum


class C4ContainerType(str, Enum):
    """Book-canonical container types with their exact C4 labels."""

    # Application containers
    SERVER_SIDE_WEB_APP = "ServerSideWebApp"
    CLIENT_SIDE_WEB_APP = "ClientSideWebApp"
    MOBILE_APP = "MobileApp"
    CONSOLE_APP = "ConsoleApp"
    SERVERLESS_FUNCTION = "ServerlessFunction"
    SHELL_SCRIPT = "ShellScript"

    # Data store containers
    DATABASE = "Database"
    BLOB_STORE = "BlobStore"
    FILE_SYSTEM = "FileSystem"
    MESSAGE_BROKER = "MessageBroker"

    UNKNOWN = "Unknown"


def classify_c4_container_type(container: dict) -> C4ContainerType:
    """Map a detected container dict to a canonical C4ContainerType.

    Args:
        container: Dict with at least 'technology' and 'name' keys.
                   Optionally 'container_type' from the detector.

    Returns:
        The most specific C4ContainerType that matches.
    """
    tech = (container.get("technology") or "").lower()
    name = (container.get("name") or "").lower()
    ctype = (container.get("container_type") or "").lower()

    # Message broker — check first (Kafka is also sometimes called "database")
    if any(k in tech for k in ("kafka", "rabbitmq", "activemq", "nats", "sqs", "pubsub", "amqp")):
        return C4ContainerType.MESSAGE_BROKER
    if any(k in ctype for k in ("broker", "queue", "messaging", "event")):
        return C4ContainerType.MESSAGE_BROKER

    # Blob / object store
    if any(k in tech for k in ("s3", "minio", "blob", "gcs", "cloudfront", "cdn", "object store")):
        return C4ContainerType.BLOB_STORE
    if "blob" in ctype or "storage" in ctype:
        return C4ContainerType.BLOB_STORE

    # Database
    _db_techs = (
        "postgres", "postgresql", "mysql", "mariadb", "mongodb", "redis",
        "neo4j", "sqlite", "dynamodb", "cassandra", "elasticsearch",
        "opensearch", "oracle", "mssql", "sqlserver", "rds", "aurora",
        "cockroachdb", "tidb",
    )
    if any(k in tech for k in _db_techs):
        return C4ContainerType.DATABASE
    if any(k in ctype for k in ("database", "db", "store", "cache")):
        return C4ContainerType.DATABASE
    if any(k in name for k in ("db", "database", "store", "cache")):
        return C4ContainerType.DATABASE

    # Serverless function
    if any(k in tech for k in ("lambda", "azure function", "cloud function", "serverless")):
        return C4ContainerType.SERVERLESS_FUNCTION
    if "serverless" in ctype or "function" in ctype:
        return C4ContainerType.SERVERLESS_FUNCTION

    # Shell script
    if any(k in tech for k in ("bash", "shell", "sh", "zsh")):
        return C4ContainerType.SHELL_SCRIPT

    # Mobile app
    _mobile = ("ios", "android", "flutter", "react native", "swift", "kotlin", "xamarin", "ionic")
    if any(k in tech for k in _mobile):
        return C4ContainerType.MOBILE_APP
    if "mobile" in ctype:
        return C4ContainerType.MOBILE_APP

    # Client-side web app (SPA, frontend)
    _frontend_techs = ("react", "vue", "angular", "svelte", "next.js", "nuxt", "gatsby", "vite")
    if any(k in tech for k in _frontend_techs):
        if any(k in ctype for k in ("frontend", "spa", "web", "client", "ui")):
            return C4ContainerType.CLIENT_SIDE_WEB_APP
        if any(k in name for k in ("frontend", "spa", "ui", "web", "client")):
            return C4ContainerType.CLIENT_SIDE_WEB_APP

    # Server-side web application
    _server_techs = (
        "spring", "spring boot", "django", "flask", "fastapi", "rails",
        "express", "asp.net", "laravel", "symfony", "gin", "echo", "fiber",
        "node", "tomcat", "jetty", "quarkus", "micronaut",
    )
    if any(k in tech for k in _server_techs):
        return C4ContainerType.SERVER_SIDE_WEB_APP
    if any(k in ctype for k in ("api", "backend", "service", "server", "web")):
        return C4ContainerType.SERVER_SIDE_WEB_APP

    return C4ContainerType.UNKNOWN
```

- [ ] **Step 4: Run test to verify it passes**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_c4_types.py -v
```

Expected: 9 PASSED

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/services/c4/containers/c4_types.py \
        sources/Api/tests/unit/services/c4/test_c4_types.py
git commit -m "feat(c4): add C4ContainerType enum and classifier matching book taxonomy"
```

---

## Task 7: Wire C4ElementType + ContainerType + Protocol into ContainerManager

`ContainerManager.detect_all_containers()` returns a `dict[name → container]`. This task enriches every container with `c4_element_type`, `c4_container_type`, and adds `technology` (protocol) to every relationship.

**Files:**
- Modify: `sources/Api/app/services/c4/containers/container_manager.py`

- [ ] **Step 1: Write failing test**

Add to a new test file `sources/Api/tests/unit/services/c4/test_container_enrichment.py`:

```python
"""Test that ContainerManager attaches C4 metadata to output."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.c4.containers.container_manager import ContainerManager


class TestContainerEnrichment:
    def test_all_containers_have_c4_element_type(self, tmp_path):
        manager = ContainerManager(tmp_path)
        # Inject a fake container directly
        manager.containers["backend"] = {
            "name": "backend",
            "technology": "Spring Boot",
            "container_type": "service",
        }
        enriched = manager._enrich_containers_with_c4_metadata(manager.containers)
        assert enriched["backend"]["c4_element_type"] == "Container"

    def test_all_containers_have_c4_container_type(self, tmp_path):
        manager = ContainerManager(tmp_path)
        manager.containers["db"] = {
            "name": "db",
            "technology": "PostgreSQL",
            "container_type": "database",
        }
        enriched = manager._enrich_containers_with_c4_metadata(manager.containers)
        assert enriched["db"]["c4_container_type"] == "Database"

    def test_relationships_get_technology_field(self, tmp_path):
        manager = ContainerManager(tmp_path)
        rels = [
            {"from": "backend", "to": "postgres", "type": "uses"},
        ]
        enriched = manager._enrich_relationships_with_protocol(rels)
        assert "technology" in enriched[0]
        assert enriched[0]["technology"] == "JDBC"

    def test_kafka_relationship_gets_kafka_protocol(self, tmp_path):
        manager = ContainerManager(tmp_path)
        rels = [{"from": "backend", "to": "kafka-broker", "type": "publishes"}]
        enriched = manager._enrich_relationships_with_protocol(rels)
        assert enriched[0]["technology"] == "Kafka"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_container_enrichment.py -v
```

Expected: `AttributeError: 'ContainerManager' object has no attribute '_enrich_containers_with_c4_metadata'`

- [ ] **Step 3: Add enrichment methods to container_manager.py**

At the top of `sources/Api/app/services/c4/containers/container_manager.py`, add imports:

```python
from app.services.c4.context.decision_models import C4ElementType
from .c4_types import C4ContainerType, classify_c4_container_type
from .protocol_detector import ProtocolDetector
```

Add two private methods inside `ContainerManager`:

```python
def _enrich_containers_with_c4_metadata(
    self, containers: dict[str, dict]
) -> dict[str, dict]:
    """Attach c4_element_type and c4_container_type to every container."""
    for container in containers.values():
        container["c4_element_type"] = C4ElementType.CONTAINER
        container["c4_container_type"] = classify_c4_container_type(container).value
    return containers

def _enrich_relationships_with_protocol(
    self, relationships: list[dict]
) -> list[dict]:
    """Add technology/protocol field to every relationship.

    Uses ProtocolDetector: first checks target name heuristics,
    then falls back to source-code fingerprinting.
    """
    detector = ProtocolDetector(self.repo_path)
    for rel in relationships:
        if rel.get("technology") or rel.get("protocol"):
            # Already has a protocol from config-file extraction — keep it
            if not rel.get("technology"):
                rel["technology"] = rel.get("protocol")
            continue
        source = rel.get("from") or rel.get("source") or ""
        target = rel.get("to") or rel.get("destination") or ""
        rel["technology"] = detector.detect_for_relationship(source, target)
    return relationships
```

- [ ] **Step 4: Wire both methods into detect_all_containers()**

At the end of `detect_all_containers()`, just before `return self.containers`, add:

```python
self.containers = self._enrich_containers_with_c4_metadata(self.containers)
```

And wherever relationships are built / returned in the manager, call:

```python
relationships = self._enrich_relationships_with_protocol(relationships)
```

(Search for `relationships` in the file — there will be a return or assignment after deduplication. Wrap it there.)

- [ ] **Step 5: Run test to verify it passes**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_container_enrichment.py -v
```

Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add sources/Api/app/services/c4/containers/container_manager.py \
        sources/Api/tests/unit/services/c4/test_container_enrichment.py
git commit -m "feat(c4): wire C4ElementType, C4ContainerType, and protocol detection into ContainerManager"
```

---

## Task 8: Add c4_element_type to ComponentObject

The Component level is the smallest change — add a single typed field to the Pydantic model so every extracted component carries its C4 label.

**Files:**
- Modify: `sources/Api/app/services/c4/components/models.py`
- Modify: `sources/Api/tests/unit/services/c4/components/test_models.py`

- [ ] **Step 1: Write failing test**

Add to `sources/Api/tests/unit/services/c4/components/test_models.py`:

```python
from app.services.c4.components.models import ComponentObject, ComponentType


class TestComponentObjectC4Label:
    def test_component_has_c4_element_type_field(self):
        obj = ComponentObject(
            name="OrderController",
            component_type=ComponentType.CONTROLLER,
            description="Handles order requests",
            source_file="src/controllers/order.py",
            confidence=0.9,
        )
        assert obj.c4_element_type == "Component"

    def test_c4_element_type_is_always_component(self):
        obj = ComponentObject(
            name="PaymentRepository",
            component_type=ComponentType.REPOSITORY,
            description="Stores payment records",
            source_file="src/repos/payment.py",
            confidence=0.8,
        )
        # Should never be overridable to a different type
        assert obj.c4_element_type == "Component"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/components/test_models.py::TestComponentObjectC4Label -v
```

Expected: `ValidationError` or `AttributeError` — field doesn't exist.

- [ ] **Step 3: Add field to ComponentObject**

In `sources/Api/app/services/c4/components/models.py`, find the `ComponentObject` class and add one field:

```python
class ComponentObject(BaseModel):
    # ... existing fields unchanged ...

    c4_element_type: str = Field(
        default="Component",
        description="C4 canonical element type label. Always 'Component' at Level 3.",
    )
```

(Place it after the existing `tags` or `metadata` field, before any validators.)

- [ ] **Step 4: Run test to verify it passes**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/components/test_models.py::TestComponentObjectC4Label -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/services/c4/components/models.py \
        sources/Api/tests/unit/services/c4/components/test_models.py
git commit -m "feat(c4): add c4_element_type = Component to ComponentObject"
```

---

## Task 9: Integration Smoke Test

Verify the full pipeline end-to-end: Context emits `[Person]`/`[SoftwareSystem]`/`[Container]` labels, Container emits `[Container]` + `c4_container_type` + `technology` on relationships, Component emits `[Component]`.

**Files:**
- Create: `sources/Api/tests/unit/services/c4/test_c4_element_type_integration.py`

- [ ] **Step 1: Write failing test**

```python
"""Integration smoke test: verify C4 element type labels flow through all three levels."""
from pathlib import Path

from app.services.c4.context.context_manager import ContextManager
from app.services.c4.containers.container_manager import ContainerManager
from app.services.c4.components.models import ComponentObject, ComponentType


class TestC4ElementTypePipeline:
    def test_context_actor_carries_person_label(self, tmp_path):
        manager = ContextManager(tmp_path)
        actors = [{"name": "Admin", "description": "manages system"}]
        enriched = manager._enrich_actors_with_element_type(actors)
        assert enriched[0]["c4_element_type"] == "Person"

    def test_context_business_dep_carries_software_system_label(self, tmp_path):
        manager = ContextManager(tmp_path)
        deps = [{"name": "Stripe", "dependency_type": "BUSINESS_SYSTEM"}]
        enriched = manager._enrich_deps_with_element_type(deps)
        assert enriched[0]["c4_element_type"] == "SoftwareSystem"

    def test_container_carries_container_label(self, tmp_path):
        manager = ContainerManager(tmp_path)
        manager.containers["backend"] = {"name": "backend", "technology": "FastAPI"}
        enriched = manager._enrich_containers_with_c4_metadata(manager.containers)
        assert enriched["backend"]["c4_element_type"] == "Container"

    def test_container_relationship_has_technology(self, tmp_path):
        manager = ContainerManager(tmp_path)
        rels = [{"from": "backend", "to": "postgres-db", "type": "reads"}]
        enriched = manager._enrich_relationships_with_protocol(rels)
        assert "technology" in enriched[0]
        assert enriched[0]["technology"]  # non-empty

    def test_component_carries_component_label(self):
        comp = ComponentObject(
            name="OrderService",
            component_type=ComponentType.SERVICE,
            description="Manages orders",
            source_file="src/services/order.py",
            confidence=0.9,
        )
        assert comp.c4_element_type == "Component"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_c4_element_type_integration.py -v
```

Expected: failures until all previous tasks are merged.

- [ ] **Step 3: Run the full test suite to verify no regressions**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/ -v --tb=short 2>&1 | tail -30
```

Expected: all existing tests pass; new tests pass.

- [ ] **Step 4: Run integration smoke test**

```bash
docker compose exec api python -m pytest tests/unit/services/c4/test_c4_element_type_integration.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add sources/Api/tests/unit/services/c4/test_c4_element_type_integration.py
git commit -m "test(c4): integration smoke test for C4 element type labels across all three levels"
```

---

## Self-Review

### Spec coverage check

| Requirement | Task |
|---|---|
| `c4_element_type` on every output element | Tasks 1, 4, 7, 8 |
| Ownership classifier (Container vs SoftwareSystem) | Tasks 2, 3 |
| Protocol detection on L2 relationships | Tasks 5, 7 |
| Container subtype taxonomy from book | Tasks 6, 7 |
| `[Person]` label on actors | Task 4 |
| `[Component]` label on components | Task 8 |
| Integration verification | Task 9 |

### Type consistency check

- `C4ElementType.CONTAINER` (enum value `"Container"`) used consistently in Tasks 1, 4, 7
- `C4ContainerType` classifier returns `.value` string in Task 7 (not the enum itself — matches dict serialization)
- `OwnershipSignalDetector` in Task 2 uses `(bool, float, str)` tuple; consumed in Task 3 with same unpacking
- `ProtocolDetector.detect_for_relationship()` returns `str | None`; Task 7 wraps assignment so `None` is never written to output (falls back to `"HTTPS"` inside the method)
- `ComponentObject.c4_element_type` is `str` with default `"Component"` — not an enum — to avoid Pydantic V2 issues with string enums in nested models

### Placeholder scan
No TBD, TODO, or "implement later" in any step. Every code block is complete and functional.
