"""Tests for C4 Component extraction pipeline models."""

import pytest
from pydantic import ValidationError

from app.services.c4.components.models import (
    ArchitecturalLayer,
    CodeElement,
    CodeElementKind,
    ComponentObject,
    ComponentRelationship,
    DependencyEdge,
    DependencyType,
    ExtractionMethod,
    FrameworkResult,
)


def test_code_element_kind_members():
    # Arrange
    expected = {"CLASS", "INTERFACE", "ABSTRACT_CLASS", "STRUCT", "MODULE", "FUNCTION", "ENUM"}

    # Act
    actual = {m.name for m in CodeElementKind}

    # Assert
    assert actual == expected


def test_architectural_layer_members():
    # Arrange
    expected = {"PRESENTATION", "BUSINESS", "DATA_ACCESS", "INFRASTRUCTURE", "UNKNOWN"}

    # Act
    actual = {m.name for m in ArchitecturalLayer}

    # Assert
    assert actual == expected


def test_dependency_type_members():
    # Arrange
    expected = {"IMPORT", "CALL", "INHERITANCE", "INJECTION", "SEMANTIC", "DIRECTORY"}

    # Act
    actual = {m.name for m in DependencyType}

    # Assert
    assert actual == expected


def test_extraction_method_members():
    # Arrange
    expected = {"FRAMEWORK_DETECTION", "COMMUNITY_DETECTION", "HYBRID", "MANUAL"}

    # Act
    actual = {m.name for m in ExtractionMethod}

    # Assert
    assert actual == expected


def test_code_element_minimal_construction():
    # Arrange / Act
    element = CodeElement(
        qualified_name="com.example.UserService",
        kind=CodeElementKind.CLASS,
        file_path="src/UserService.java",
        language="java",
    )

    # Assert
    assert element.annotations == []
    assert element.imports == []
    assert element.layer == ArchitecturalLayer.UNKNOWN


def test_component_object_json_roundtrip():
    # Arrange
    component = ComponentObject(
        component_id="comp-1",
        name="UserService",
        description="Handles user operations",
        confidence=0.9,
        extraction_method=ExtractionMethod.FRAMEWORK_DETECTION,
        code_elements=[
            CodeElement(
                qualified_name="com.example.UserService",
                kind=CodeElementKind.CLASS,
                file_path="src/UserService.java",
                language="java",
            )
        ],
        relationships=[
            ComponentRelationship(
                source_component="UserService",
                target_component="UserRepository",
                label="uses",
            )
        ],
    )

    # Act
    json_str = component.model_dump_json()
    restored = ComponentObject.model_validate_json(json_str)

    # Assert
    assert restored == component


def test_dependency_edge_weight_validation():
    # Arrange / Act / Assert — weight=0 must fail
    with pytest.raises(ValidationError):
        DependencyEdge(
            source="A",
            target="B",
            dependency_type=DependencyType.IMPORT,
            weight=0,
        )

    # weight=-1 must fail
    with pytest.raises(ValidationError):
        DependencyEdge(
            source="A",
            target="B",
            dependency_type=DependencyType.IMPORT,
            weight=-1,
        )

    # weight=0.5 must succeed
    edge = DependencyEdge(
        source="A",
        target="B",
        dependency_type=DependencyType.IMPORT,
        weight=0.5,
    )
    assert edge.weight == 0.5
