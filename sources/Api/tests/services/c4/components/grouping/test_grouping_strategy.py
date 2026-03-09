"""Integration tests for GroupingStrategy two-tier orchestration."""

from __future__ import annotations
from unittest.mock import MagicMock

import networkx as nx
import pytest

from app.services.c4.components.grouping import GroupingStrategy
from app.services.c4.components.models import (
    ArchitecturalLayer,
    CodeElement,
    CodeElementKind,
    ComponentObject,
    ExtractionMethod,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _spring_element(name: str, annotation: str) -> CodeElement:
    return CodeElement(
        qualified_name=name,
        kind=CodeElementKind.CLASS,
        file_path=f"src/main/java/{name.replace('.', '/')}.java",
        language="java",
        annotations=[annotation],
    )


def _generic_element(name: str, file_path: str) -> CodeElement:
    return CodeElement(
        qualified_name=name,
        kind=CodeElementKind.CLASS,
        file_path=file_path,
        language="python",
    )


def _build_graph(
    elements: list[CodeElement],
    edges: list[tuple[str, str, float]],
) -> nx.DiGraph:
    g = nx.DiGraph()
    for e in elements:
        g.add_node(e.qualified_name)
    for src, dst, weight in edges:
        g.add_edge(src, dst, weight=weight)
    return g


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGroupingStrategy:
    def _make_elements_and_graph(self):
        spring_elements = [
            _spring_element("com.order.OrderController", "Controller"),
            _spring_element("com.order.OrderService", "Service"),
            _spring_element("com.payment.PaymentController", "Controller"),
            _spring_element("com.payment.PaymentService", "Service"),
        ]
        generic_elements = [
            _generic_element("utils.StringHelper", "src/utils/string_helper.py"),
            _generic_element("utils.DateHelper", "src/utils/date_helper.py"),
        ]
        all_elements = spring_elements + generic_elements

        edges = [
            ("utils.StringHelper", "utils.DateHelper", 2.0),
            ("utils.DateHelper", "utils.StringHelper", 2.0),
        ]
        dep_graph = _build_graph(all_elements, edges)
        return all_elements, dep_graph

    def test_framework_components_present(self):
        elements, dep_graph = self._make_elements_and_graph()
        result = GroupingStrategy().group(elements, dep_graph)

        framework_comps = [
            c for c in result
            if c.extraction_method == ExtractionMethod.FRAMEWORK_DETECTION
        ]
        assert len(framework_comps) >= 1

    def test_framework_components_technology_is_spring(self):
        elements, dep_graph = self._make_elements_and_graph()
        result = GroupingStrategy().group(elements, dep_graph)

        framework_comps = [
            c for c in result
            if c.extraction_method == ExtractionMethod.FRAMEWORK_DETECTION
        ]
        for comp in framework_comps:
            assert comp.technology == "Spring"

    def test_community_components_present(self):
        elements, dep_graph = self._make_elements_and_graph()
        result = GroupingStrategy().group(elements, dep_graph)

        community_comps = [
            c for c in result
            if c.extraction_method == ExtractionMethod.COMMUNITY_DETECTION
        ]
        assert len(community_comps) >= 1

    def test_all_elements_covered(self):
        elements, dep_graph = self._make_elements_and_graph()
        result = GroupingStrategy().group(elements, dep_graph)

        covered = {
            e.qualified_name
            for comp in result
            for e in comp.code_elements
        }
        expected = {e.qualified_name for e in elements}
        assert covered == expected

    def test_no_duplicate_component_ids(self):
        elements, dep_graph = self._make_elements_and_graph()
        result = GroupingStrategy().group(elements, dep_graph)

        ids = [c.component_id for c in result]
        assert len(ids) == len(set(ids))

    def test_empty_elements_returns_empty(self):
        dep_graph = nx.DiGraph()
        result = GroupingStrategy().group([], dep_graph)
        assert result == []

    def test_only_spring_elements_no_community(self):
        spring_elements = [
            _spring_element("com.order.OrderController", "Controller"),
            _spring_element("com.order.OrderService", "Service"),
        ]
        dep_graph = _build_graph(spring_elements, [])
        result = GroupingStrategy().group(spring_elements, dep_graph)

        community_comps = [
            c for c in result
            if c.extraction_method == ExtractionMethod.COMMUNITY_DETECTION
        ]
        assert len(community_comps) == 0


# ---------------------------------------------------------------------------
# LLM path tests
# ---------------------------------------------------------------------------

def _make_generic_elements(n: int) -> list[CodeElement]:
    return [
        _generic_element(f"pkg.Class{i}", f"src/pkg/class{i}.py")
        for i in range(n)
    ]


def _make_llm_component(method: ExtractionMethod, confidence: float) -> ComponentObject:
    return ComponentObject(
        component_id="llm-comp",
        name="LLMComponent",
        extraction_method=method,
        confidence=confidence,
        code_elements=[],
    )


class TestGroupingStrategyWithLLM:
    def test_llm_direct_path_used_when_available_small_remainder(self):
        elements = _make_generic_elements(5)
        dep_graph = _build_graph(elements, [])

        llm = MagicMock()
        llm.classify_elements.side_effect = lambda elems: elems
        llm.group_elements.return_value = [
            _make_llm_component(ExtractionMethod.LLM_DIRECT, 0.85)
        ]

        result = GroupingStrategy(llm_service=llm).group(elements, dep_graph)

        llm_comps = [c for c in result if c.extraction_method == ExtractionMethod.LLM_DIRECT]
        assert len(llm_comps) >= 1
        assert llm_comps[0].confidence == 0.85

    def test_llm_refined_path_used_for_large_remainder(self):
        elements = _make_generic_elements(65)
        dep_graph = _build_graph(elements, [])

        llm = MagicMock()
        llm.classify_elements.side_effect = lambda elems: elems
        llm.refine_grouping.return_value = [
            _make_llm_component(ExtractionMethod.LLM_REFINED, 0.75)
        ]

        result = GroupingStrategy(llm_service=llm).group(elements, dep_graph)

        refined_comps = [c for c in result if c.extraction_method == ExtractionMethod.LLM_REFINED]
        assert len(refined_comps) >= 1
        assert refined_comps[0].confidence == 0.75

    def test_llm_unavailable_falls_back_to_louvain(self):
        elements = _make_generic_elements(4)
        dep_graph = _build_graph(elements, [
            (elements[0].qualified_name, elements[1].qualified_name, 1.0),
            (elements[2].qualified_name, elements[3].qualified_name, 1.0),
        ])

        result = GroupingStrategy(llm_service=None).group(elements, dep_graph)

        community_comps = [
            c for c in result
            if c.extraction_method == ExtractionMethod.COMMUNITY_DETECTION
        ]
        assert len(community_comps) >= 1

    def test_high_confidence_framework_bypasses_llm(self):
        spring_elements = [
            _spring_element("com.order.OrderController", "Controller"),
            _spring_element("com.order.OrderService", "Service"),
            _spring_element("com.order.OrderRepository", "Repository"),
        ]
        dep_graph = _build_graph(spring_elements, [])

        llm = MagicMock()
        llm.classify_elements.side_effect = lambda elems: elems

        GroupingStrategy(llm_service=llm).group(spring_elements, dep_graph)

        llm.group_elements.assert_not_called()
