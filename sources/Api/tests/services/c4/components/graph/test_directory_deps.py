"""Tests for DirectoryDependencyAnalyzer."""

from __future__ import annotations

from app.services.c4.components.graph import DirectoryDependencyAnalyzer
from app.services.c4.components.models import CodeElement, CodeElementKind, DependencyEdge, DependencyType


def _el(qualified_name: str, file_path: str) -> CodeElement:
    return CodeElement(
        qualified_name=qualified_name,
        kind=CodeElementKind.CLASS,
        file_path=file_path,
        language="python",
    )


def _find(edges, source_suffix, target_suffix):
    return [
        e for e in edges
        if e.source.endswith(source_suffix)
        and e.target.endswith(target_suffix)
        and e.dependency_type == DependencyType.DIRECTORY
    ]


def test_same_dir_weight():
    a = _el("app.foo", "app/foo.py")
    b = _el("app.bar", "app/bar.py")
    edges = DirectoryDependencyAnalyzer().analyze([a, b])
    ab = _find(edges, "app.foo", "app.bar")
    ba = _find(edges, "app.bar", "app.foo")
    assert len(ab) == 1
    assert len(ba) == 1
    assert ab[0].weight == 0.3
    assert ba[0].weight == 0.3


def test_parent_child_weight():
    a = _el("app.root", "app/root.py")
    b = _el("app.services.svc", "app/services/svc.py")
    edges = DirectoryDependencyAnalyzer().analyze([a, b])
    ab = _find(edges, "app.root", "app.services.svc")
    ba = _find(edges, "app.services.svc", "app.root")
    assert len(ab) == 1
    assert len(ba) == 1
    assert ab[0].weight == 0.15
    assert ba[0].weight == 0.15


def test_sibling_dirs_weight():
    a = _el("app.controllers.x", "app/controllers/x.py")
    b = _el("app.services.y", "app/services/y.py")
    edges = DirectoryDependencyAnalyzer().analyze([a, b])
    ab = _find(edges, "controllers.x", "services.y")
    ba = _find(edges, "services.y", "controllers.x")
    assert len(ab) == 1
    assert len(ba) == 1
    assert ab[0].weight == 0.1
    assert ba[0].weight == 0.1


def test_too_far_no_edge():
    a = _el("a.b.c.x", "a/b/c/x.py")
    b = _el("d.e.f.y", "d/e/f/y.py")
    edges = DirectoryDependencyAnalyzer().analyze([a, b])
    assert edges == []


def test_skip_existing_edge():
    a = _el("app.foo", "app/foo.py")
    b = _el("app.bar", "app/bar.py")
    existing = [
        DependencyEdge(source="app.foo", target="app.bar", dependency_type=DependencyType.DIRECTORY, weight=0.3),
        DependencyEdge(source="app.bar", target="app.foo", dependency_type=DependencyType.DIRECTORY, weight=0.3),
    ]
    edges = DirectoryDependencyAnalyzer().analyze([a, b], existing_edges=existing)
    assert edges == []


def test_existing_edges_none():
    a = _el("app.foo", "app/foo.py")
    b = _el("app.bar", "app/bar.py")
    # Should not raise
    edges = DirectoryDependencyAnalyzer().analyze([a, b], existing_edges=None)
    assert len(edges) == 2


def test_both_directions_generated():
    a = _el("app.foo", "app/foo.py")
    b = _el("app.bar", "app/bar.py")
    edges = DirectoryDependencyAnalyzer().analyze([a, b])
    sources = {e.source for e in edges}
    assert "app.foo" in sources
    assert "app.bar" in sources


def test_no_duplicate_edges():
    a = _el("app.foo", "app/foo.py")
    b = _el("app.bar", "app/bar.py")
    analyzer = DirectoryDependencyAnalyzer()
    edges1 = analyzer.analyze([a, b])
    edges2 = analyzer.analyze([a, b])
    combined = edges1 + edges2
    pairs = [(e.source, e.target) for e in combined]
    assert len(pairs) == len(set(pairs))
