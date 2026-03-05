"""Tests for DependencyGraphBuilder."""

from __future__ import annotations

import pytest

from app.services.c4.components.graph import DependencyGraphBuilder
from app.services.c4.components.models import CodeElement, CodeElementKind, DependencyEdge, DependencyType


def _el(qualified_name: str) -> CodeElement:
    return CodeElement(
        qualified_name=qualified_name,
        kind=CodeElementKind.CLASS,
        file_path="dummy.py",
        language="python",
    )


def _edge(source: str, target: str, dep_type: DependencyType = DependencyType.IMPORT, weight: float = 1.0) -> DependencyEdge:
    return DependencyEdge(source=source, target=target, dependency_type=dep_type, weight=weight)


@pytest.fixture()
def builder() -> DependencyGraphBuilder:
    return DependencyGraphBuilder()


def test_nodes_from_elements(builder):
    elements = [_el("app.a"), _el("app.b"), _el("app.c")]
    g = builder.build(elements, [], [])
    assert set(g.nodes) == {"app.a", "app.b", "app.c"}
    assert g.nodes["app.a"]["element"].qualified_name == "app.a"


def test_edges_from_structural(builder):
    elements = [_el("app.a"), _el("app.b")]
    structural = [_edge("app.a", "app.b", DependencyType.IMPORT, 1.0)]
    g = builder.build(elements, structural, [])
    assert g.has_edge("app.a", "app.b")
    assert g["app.a"]["app.b"]["weight"] == 1.0


def test_same_edge_summed(builder):
    elements = [_el("app.a"), _el("app.b")]
    structural = [_edge("app.a", "app.b", DependencyType.IMPORT, 1.0)]
    directory = [_edge("app.a", "app.b", DependencyType.DIRECTORY, 0.5)]
    g = builder.build(elements, structural, directory)
    assert g["app.a"]["app.b"]["weight"] == pytest.approx(1.5)


def test_semantic_edges_optional(builder):
    elements = [_el("app.a"), _el("app.b")]
    structural = [_edge("app.a", "app.b")]
    g = builder.build(elements, structural, [], semantic_edges=None)
    assert g.has_edge("app.a", "app.b")
    assert g.number_of_edges() == 1


def test_get_undirected_weighted(builder):
    elements = [_el("app.a"), _el("app.b")]
    structural = [
        _edge("app.a", "app.b", DependencyType.IMPORT, 1.0),
        _edge("app.b", "app.a", DependencyType.CALL, 1.5),
    ]
    g = builder.build(elements, structural, [])
    ug = DependencyGraphBuilder.get_undirected_weighted(g)
    assert ug.has_edge("app.a", "app.b")
    assert ug.number_of_edges() == 1
    assert ug["app.a"]["app.b"]["weight"] == pytest.approx(2.5)


def test_get_subgraph(builder):
    elements = [_el("app.a"), _el("app.b"), _el("app.c")]
    structural = [
        _edge("app.a", "app.b"),
        _edge("app.a", "app.c"),
    ]
    g = builder.build(elements, structural, [])
    sub = DependencyGraphBuilder.get_subgraph(g, ["app.a", "app.b"])
    assert set(sub.nodes) == {"app.a", "app.b"}
    assert sub.has_edge("app.a", "app.b")
    assert not sub.has_edge("app.a", "app.c")


def test_summary_keys(builder):
    elements = [_el("app.a"), _el("app.b")]
    structural = [_edge("app.a", "app.b")]
    g = builder.build(elements, structural, [])
    s = DependencyGraphBuilder.summary(g)
    assert set(s.keys()) == {"nodes", "edges", "density", "weakly_connected_components"}
    assert s["nodes"] == 2
    assert s["edges"] == 1
    assert s["density"] > 0

    empty_g = builder.build([], [], [])
    es = DependencyGraphBuilder.summary(empty_g)
    assert es["density"] == 0.0
