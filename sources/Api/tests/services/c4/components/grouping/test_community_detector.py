"""Tests for community_detector.py — Louvain-based fallback grouping."""

from __future__ import annotations

import networkx as nx
import pytest

from app.services.c4.components.models import (
    CodeElement,
    CodeElementKind,
    ComponentObject,
    ExtractionMethod,
)
from app.services.c4.components.grouping.community_detector import CommunityDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _element(name: str, file_path: str) -> CodeElement:
    return CodeElement(
        qualified_name=name,
        kind=CodeElementKind.CLASS,
        file_path=file_path,
        language="python",
    )


def _build_two_cluster_graph() -> nx.Graph:
    """Graph with 2 dense clusters (A-B-C) and (D-E-F) with weak inter-edge."""
    g = nx.Graph()
    # Cluster 1
    g.add_edge("A", "B", weight=2.0)
    g.add_edge("B", "C", weight=2.0)
    g.add_edge("A", "C", weight=2.0)
    # Cluster 2
    g.add_edge("D", "E", weight=2.0)
    g.add_edge("E", "F", weight=2.0)
    g.add_edge("D", "F", weight=2.0)
    # Weak inter-cluster edge
    g.add_edge("C", "D", weight=0.1)
    return g


# ---------------------------------------------------------------------------
# TestDetect
# ---------------------------------------------------------------------------


class TestDetect:
    def test_two_obvious_clusters_separated(self):
        g = _build_two_cluster_graph()
        detector = CommunityDetector()
        partition = detector.detect(g)

        cluster_abc = {partition["A"], partition["B"], partition["C"]}
        cluster_def = {partition["D"], partition["E"], partition["F"]}
        # All three nodes in each dense group must share the same cluster id
        assert len(cluster_abc) == 1
        assert len(cluster_def) == 1
        # The two clusters must be distinct
        assert cluster_abc != cluster_def

    def test_empty_graph_returns_empty(self):
        detector = CommunityDetector()
        assert detector.detect(nx.Graph()) == {}

    def test_single_node_graph(self):
        g = nx.Graph()
        g.add_node("only")
        detector = CommunityDetector()
        partition = detector.detect(g)
        assert list(partition.keys()) == ["only"]
        assert len(partition) == 1


# ---------------------------------------------------------------------------
# TestPostProcess
# ---------------------------------------------------------------------------


class TestPostProcess:
    def test_singleton_merged_to_neighbor(self):
        """Isolated singleton weakly connected to a 3-node cluster should join it."""
        g = nx.Graph()
        g.add_edge("A", "B", weight=2.0)
        g.add_edge("B", "C", weight=2.0)
        g.add_edge("A", "C", weight=2.0)
        g.add_edge("C", "X", weight=0.5)  # X is the singleton

        # Initial partition: X is alone, ABC share cluster 0
        partition = {"A": 0, "B": 0, "C": 0, "X": 1}

        detector = CommunityDetector()
        result = detector.post_process(partition, g, min_size=2)

        # X should have joined cluster 0 (its only neighbor is C)
        assert result["X"] == result["C"]

    def test_oversized_cluster_split(self):
        """20 nodes in one cluster should be split when max_size=10."""
        g = nx.Graph()
        nodes = [f"n{i}" for i in range(20)]
        # Add edges to form two subgroups of 10
        for i in range(9):
            g.add_edge(nodes[i], nodes[i + 1], weight=1.0)
        for i in range(10, 19):
            g.add_edge(nodes[i], nodes[i + 1], weight=1.0)
        g.add_edge(nodes[9], nodes[10], weight=0.1)

        partition = {n: 0 for n in nodes}
        detector = CommunityDetector()
        result = detector.post_process(partition, g, max_size=10)

        cluster_ids = set(result.values())
        assert len(cluster_ids) >= 2

    def test_no_change_when_sizes_ok(self):
        """Clusters within bounds are left unchanged."""
        g = nx.Graph()
        g.add_edge("A", "B", weight=1.0)
        g.add_edge("C", "D", weight=1.0)

        partition = {"A": 0, "B": 0, "C": 1, "D": 1}
        detector = CommunityDetector()
        result = detector.post_process(partition, g, min_size=2, max_size=15)

        assert result["A"] == result["B"]
        assert result["C"] == result["D"]
        assert result["A"] != result["C"]


# ---------------------------------------------------------------------------
# TestPartitionToGroups
# ---------------------------------------------------------------------------


class TestPartitionToGroups:
    def test_groups_match_partition(self):
        elements = [
            _element("A", "a.py"),
            _element("B", "b.py"),
            _element("C", "c.py"),
        ]
        partition = {"A": 0, "B": 0, "C": 1}
        detector = CommunityDetector()
        groups = detector.partition_to_groups(partition, elements)

        sizes = sorted(len(g) for g in groups)
        assert sizes == [1, 2]

    def test_elements_not_in_partition_excluded(self):
        elements = [
            _element("A", "a.py"),
            _element("B", "b.py"),
            _element("Ghost", "ghost.py"),  # not in partition
        ]
        partition = {"A": 0, "B": 0}
        detector = CommunityDetector()
        groups = detector.partition_to_groups(partition, elements)

        all_names = {e.qualified_name for g in groups for e in g}
        assert "Ghost" not in all_names
        assert "A" in all_names
        assert "B" in all_names


# ---------------------------------------------------------------------------
# TestNameCluster
# ---------------------------------------------------------------------------


class TestNameCluster:
    def test_common_directory_prefix(self):
        elements = [
            _element("order.OrderService", "order/OrderService.py"),
            _element("order.OrderRepo", "order/OrderRepo.py"),
        ]
        detector = CommunityDetector()
        name = detector.name_cluster(elements)
        assert "order" in name.lower()

    def test_common_token_from_qualname(self):
        elements = [
            _element("user.UserService", "svc/user_service.py"),
            _element("user.UserController", "ctrl/user_ctrl.py"),
        ]
        detector = CommunityDetector()
        name = detector.name_cluster(elements)
        assert "user" in name.lower()

    def test_fallback_for_no_common_token(self):
        elements = [
            _element("xyz.Abc", "a/b.py"),
            _element("pqr.Def", "c/d.py"),
        ]
        detector = CommunityDetector()
        name = detector.name_cluster(elements)
        assert len(name) > 0

    def test_empty_elements_returns_default(self):
        detector = CommunityDetector()
        name = detector.name_cluster([])
        assert name == "Component"


# ---------------------------------------------------------------------------
# TestToComponents
# ---------------------------------------------------------------------------


class TestToComponents:
    def test_returns_component_objects(self):
        groups = [
            [_element("order.OrderService", "order/svc.py")],
            [_element("user.UserService", "user/svc.py"), _element("user.UserCtrl", "user/ctrl.py")],
        ]
        detector = CommunityDetector()
        components = detector.to_components(groups)

        assert len(components) == 2
        for comp in components:
            assert isinstance(comp, ComponentObject)
            assert comp.extraction_method == ExtractionMethod.COMMUNITY_DETECTION
            assert comp.confidence == pytest.approx(0.6)

    def test_component_has_all_elements(self):
        group = [
            _element("order.OrderService", "order/svc.py"),
            _element("order.OrderRepo", "order/repo.py"),
        ]
        detector = CommunityDetector()
        components = detector.to_components([group])

        assert len(components) == 1
        assert len(components[0].code_elements) == 2
        names = {e.qualified_name for e in components[0].code_elements}
        assert "order.OrderService" in names
        assert "order.OrderRepo" in names

    def test_empty_group_skipped(self):
        detector = CommunityDetector()
        components = detector.to_components([[]])
        assert components == []
