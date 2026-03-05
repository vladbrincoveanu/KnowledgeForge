"""Tests for StructuralDependencyAnalyzer."""

from __future__ import annotations

import pytest

from app.services.c4.components.graph import StructuralDependencyAnalyzer
from app.services.c4.components.models import CodeElement, CodeElementKind, DependencyType


def _el(qualified_name: str, imports=None, base_classes=None, method_calls=None) -> CodeElement:
    return CodeElement(
        qualified_name=qualified_name,
        kind=CodeElementKind.CLASS,
        file_path="dummy.py",
        language="python",
        imports=imports or [],
        base_classes=base_classes or [],
        method_calls=method_calls or [],
    )


@pytest.fixture()
def elements() -> list[CodeElement]:
    return [
        _el("app.services.user_service", imports=["sqlalchemy", "app.repos.user_repo"], base_classes=["BaseService"]),
        _el("app.services.base_service"),
        _el("app.repos.user_repo", imports=["sqlalchemy.orm"], base_classes=["BaseRepo"]),
        _el("app.repos.base_repo"),
        _el("app.controllers.user_controller", imports=["app.services.user_service"], method_calls=["UserService"]),
    ]


@pytest.fixture()
def edges(elements):
    return StructuralDependencyAnalyzer().analyze(elements)


def _find(edges, source_suffix, target_suffix, dep_type):
    return [
        e for e in edges
        if e.source.endswith(source_suffix)
        and e.target.endswith(target_suffix)
        and e.dependency_type == dep_type
    ]


def test_user_service_inherits_base_service(edges):
    found = _find(edges, "user_service", "base_service", DependencyType.INHERITANCE)
    assert len(found) == 1
    assert found[0].weight == 2.0


def test_user_repo_inherits_base_repo(edges):
    found = _find(edges, "user_repo", "base_repo", DependencyType.INHERITANCE)
    assert len(found) == 1
    assert found[0].weight == 2.0


def test_controller_imports_user_service(edges):
    found = _find(edges, "user_controller", "user_service", DependencyType.IMPORT)
    assert len(found) == 1
    assert found[0].weight == 1.0


def test_controller_calls_user_service(edges):
    found = _find(edges, "user_controller", "user_service", DependencyType.CALL)
    assert len(found) == 1
    assert found[0].weight == 1.5


def test_user_service_imports_user_repo(edges):
    found = _find(edges, "user_service", "user_repo", DependencyType.IMPORT)
    assert len(found) == 1
    assert found[0].weight == 1.0


def test_no_self_edges(edges):
    assert all(e.source != e.target for e in edges)


def test_deduplication(elements):
    # Add duplicate import to user_controller
    ctrl = next(e for e in elements if e.qualified_name.endswith("user_controller"))
    ctrl.imports = ["app.services.user_service", "app.services.user_service"]

    result = StructuralDependencyAnalyzer().analyze(elements)
    import_edges = _find(result, "user_controller", "user_service", DependencyType.IMPORT)
    assert len(import_edges) == 1
