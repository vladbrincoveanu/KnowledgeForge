"""Tests for LLMComponentService."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.services.c4.components.enrichment.llm_component_service import LLMComponentService
from app.services.c4.components.models import (
    ArchitecturalLayer,
    CodeElement,
    CodeElementKind,
    DependencyEdge,
    DependencyType,
    ExtractionMethod,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    m = MagicMock()
    m.timeout = 30
    return m


@pytest.fixture
def sample_elements() -> list[CodeElement]:
    return [
        CodeElement(
            qualified_name="com.example.OrderController",
            kind=CodeElementKind.CLASS,
            file_path="src/OrderController.java",
            language="java",
            annotations=["@Controller"],
            imports=["com.example.OrderService"],
            base_classes=[],
            method_calls=["orderService.create"],
        ),
        CodeElement(
            qualified_name="com.example.OrderService",
            kind=CodeElementKind.CLASS,
            file_path="src/OrderService.java",
            language="java",
            annotations=["@Service"],
            imports=["com.example.OrderRepository"],
            base_classes=[],
            method_calls=["orderRepo.save"],
        ),
        CodeElement(
            qualified_name="com.example.OrderRepository",
            kind=CodeElementKind.INTERFACE,
            file_path="src/OrderRepository.java",
            language="java",
            annotations=[],
            imports=[],
            base_classes=["JpaRepository"],
            method_calls=[],
        ),
    ]


@pytest.fixture
def sample_edges() -> list[DependencyEdge]:
    return [
        DependencyEdge(
            source="com.example.OrderController",
            target="com.example.OrderService",
            dependency_type=DependencyType.INJECTION,
        ),
        DependencyEdge(
            source="com.example.OrderService",
            target="com.example.OrderRepository",
            dependency_type=DependencyType.INJECTION,
        ),
    ]


# ---------------------------------------------------------------------------
# classify_elements tests
# ---------------------------------------------------------------------------

class TestClassifyElements:
    def test_classify_elements_success(self, mock_llm, sample_elements):
        response = json.dumps([
            {"element_name": "com.example.OrderController", "role": "controller", "layer": "presentation", "is_significant": True, "reasoning": "Handles HTTP requests."},
            {"element_name": "com.example.OrderService", "role": "service", "layer": "business", "is_significant": True, "reasoning": "Orchestrates order logic."},
            {"element_name": "com.example.OrderRepository", "role": "repository", "layer": "data_access", "is_significant": True, "reasoning": "Persists orders."},
        ])
        mock_llm.generate_text.return_value = response

        service = LLMComponentService(mock_llm)
        result = service.classify_elements(sample_elements)

        assert len(result) == 3
        controller = next(e for e in result if "Controller" in e.qualified_name)
        assert controller.role == "controller"
        assert controller.layer == ArchitecturalLayer.PRESENTATION

        svc = next(e for e in result if e.qualified_name == "com.example.OrderService")
        assert svc.role == "service"
        assert svc.layer == ArchitecturalLayer.BUSINESS

        repo = next(e for e in result if "Repository" in e.qualified_name)
        assert repo.role == "repository"
        assert repo.layer == ArchitecturalLayer.DATA_ACCESS

    def test_classify_elements_llm_failure(self, mock_llm, sample_elements):
        mock_llm.generate_text.side_effect = RuntimeError("connection error")

        service = LLMComponentService(mock_llm)
        result = service.classify_elements(sample_elements)

        # Should return elements unchanged
        assert len(result) == len(sample_elements)
        for orig, returned in zip(sample_elements, result):
            assert returned.qualified_name == orig.qualified_name
            assert returned.role == ""

    def test_classify_elements_invalid_json(self, mock_llm, sample_elements):
        mock_llm.generate_text.return_value = "This is not JSON at all!!!"

        service = LLMComponentService(mock_llm)
        result = service.classify_elements(sample_elements)

        assert len(result) == len(sample_elements)
        for orig, returned in zip(sample_elements, result):
            assert returned.role == ""

    def test_classify_elements_batching(self, mock_llm):
        # 55 elements → 2 batches (50 + 5)
        elements = [
            CodeElement(
                qualified_name=f"com.example.Class{i}",
                kind=CodeElementKind.CLASS,
                file_path=f"src/Class{i}.java",
                language="java",
            )
            for i in range(55)
        ]

        # Return empty array for each batch (valid but no updates)
        mock_llm.generate_text.return_value = "[]"

        service = LLMComponentService(mock_llm)
        result = service.classify_elements(elements)

        assert mock_llm.generate_text.call_count == 2
        assert len(result) == 55


# ---------------------------------------------------------------------------
# group_elements tests
# ---------------------------------------------------------------------------

class TestGroupElements:
    def test_group_elements_success(self, mock_llm, sample_elements, sample_edges):
        response = json.dumps([
            {
                "name": "OrderManagement",
                "description": "Handles order lifecycle.",
                "role": "service",
                "layer": "business",
                "element_names": [
                    "com.example.OrderController",
                    "com.example.OrderService",
                    "com.example.OrderRepository",
                ],
                "provided_interfaces": [],
                "required_interfaces": [],
            }
        ])
        mock_llm.generate_text.return_value = response

        service = LLMComponentService(mock_llm)
        result = service.group_elements(sample_elements, sample_edges)

        assert len(result) == 1
        comp = result[0]
        assert comp.name == "OrderManagement"
        assert comp.extraction_method == ExtractionMethod.HYBRID
        assert comp.confidence == 0.8
        assert len(comp.code_elements) == 3

    def test_group_elements_llm_failure(self, mock_llm, sample_elements, sample_edges):
        mock_llm.generate_text.side_effect = RuntimeError("timeout")

        service = LLMComponentService(mock_llm)
        result = service.group_elements(sample_elements, sample_edges)

        assert result == []

    def test_group_elements_empty_elements(self, mock_llm, sample_edges):
        service = LLMComponentService(mock_llm)
        result = service.group_elements([], sample_edges)

        assert result == []
        mock_llm.generate_text.assert_not_called()


# ---------------------------------------------------------------------------
# refine_grouping tests
# ---------------------------------------------------------------------------

class TestRefineGrouping:
    def test_refine_grouping_success(self, mock_llm, sample_elements, sample_edges):
        louvain_groups = [
            [sample_elements[0], sample_elements[1]],
            [sample_elements[2]],
        ]
        response = json.dumps([
            {
                "name": "OrderManagement",
                "description": "Merged controller and service.",
                "role": "service",
                "layer": "business",
                "element_names": [
                    "com.example.OrderController",
                    "com.example.OrderService",
                ],
                "provided_interfaces": [],
                "required_interfaces": [],
            },
            {
                "name": "OrderPersistence",
                "description": "Data access layer.",
                "role": "repository",
                "layer": "data_access",
                "element_names": ["com.example.OrderRepository"],
                "provided_interfaces": [],
                "required_interfaces": [],
            },
        ])
        mock_llm.generate_text.return_value = response

        service = LLMComponentService(mock_llm)
        result = service.refine_grouping(louvain_groups, sample_elements, sample_edges)

        assert len(result) == 2
        names = {c.name for c in result}
        assert "OrderManagement" in names
        assert "OrderPersistence" in names

    def test_refine_grouping_fallback(self, mock_llm, sample_elements, sample_edges):
        louvain_groups = [
            [sample_elements[0], sample_elements[1]],
            [sample_elements[2]],
        ]
        mock_llm.generate_text.side_effect = RuntimeError("model unavailable")

        service = LLMComponentService(mock_llm)
        result = service.refine_grouping(louvain_groups, sample_elements, sample_edges)

        # Fallback: one ComponentObject per Louvain group
        assert len(result) == 2
        for comp in result:
            assert comp.extraction_method == ExtractionMethod.COMMUNITY_DETECTION
            assert comp.confidence == 0.5
