"""Unit tests for code extraction components."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure backend sources (sources/Api) are importable
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_SRC = PROJECT_ROOT / "sources" / "Api"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from app.domain.models.code_entities import CodeEntityType, CodeRelationType
from app.services.code_extraction.kubernetes_extractor import KubernetesExtractor
from app.services.code_extraction.repository_scanner import RepositoryScanner


def test_kubernetes_extractor_parses_deployment(tmp_path: Path):
    """Kubernetes extractor should produce workload + container entities."""
    manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  template:
    spec:
      containers:
      - name: api
        image: nginx:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: web
"""
    file_path = tmp_path / "deployment.yaml"
    file_path.write_text(manifest.strip())

    extractor = KubernetesExtractor(tmp_path)
    assert extractor.can_handle(file_path), "Extractor should detect Kubernetes manifest"

    entities, relationships = extractor.extract(file_path)
    names = {entity.name for entity in entities}

    assert "web" in names, "Deployment entity should be captured"
    container_entities = [e for e in entities if e.entity_type == CodeEntityType.CONTAINER]
    assert container_entities, "Container entities should be created for pod template"
    assert container_entities[0].attributes.get("image") == "nginx:latest"

    contains_relationships = [
        rel for rel in relationships if rel.relationship_type == CodeRelationType.CONTAINS
    ]
    assert contains_relationships, "Deployment should contain container relationships"


def test_repository_scanner_incremental_diff_reports_added_entities(tmp_path: Path):
    """Repository scanner should surface added entities via incremental diff."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    source_file = repo_path / "module.py"
    source_file.write_text(
        "class Example:\n"
        "    def foo(self):\n"
        "        return 1\n"
    )

    scanner = RepositoryScanner(repo_path)
    initial_result = scanner.scan(force_full=True)
    assert initial_result.entities, "Baseline scan should capture entities"

    # Modify repository by adding a new helper function
    source_file.write_text(
        "class Example:\n"
        "    def foo(self):\n"
        "        return 1\n\n\n"
        "def helper():\n"
        "    return 2\n"
    )

    incremental_scanner = RepositoryScanner(repo_path)
    diff = incremental_scanner.incremental_scan()

    added_names = {entity.name for entity in diff.added_entities}
    assert "helper" in added_names, "Incremental scan should report newly added function"
    assert diff.previous_scan_timestamp is not None, "Diff should reference previous scan metadata"
