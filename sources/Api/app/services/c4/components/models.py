"""Pydantic models for C4 Component extraction pipeline (Level 3)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CodeElementKind(str, Enum):
    """Kinds of code elements that can be parsed from source files."""

    CLASS = "class"
    INTERFACE = "interface"
    ABSTRACT_CLASS = "abstract_class"
    STRUCT = "struct"
    MODULE = "module"
    FUNCTION = "function"
    ENUM = "enum"


class ArchitecturalLayer(str, Enum):
    """Inferred architectural layer for a code element."""

    PRESENTATION = "presentation"
    BUSINESS = "business"
    DATA_ACCESS = "data_access"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


class DependencyType(str, Enum):
    """Type of directed dependency between two code elements."""

    IMPORT = "import"
    CALL = "call"
    INHERITANCE = "inheritance"
    INJECTION = "injection"
    SEMANTIC = "semantic"
    DIRECTORY = "directory"


class ExtractionMethod(str, Enum):
    """Strategy used to extract or group components."""

    FRAMEWORK_DETECTION = "framework_detection"
    COMMUNITY_DETECTION = "community_detection"
    LLM_DIRECT = "llm_direct"
    LLM_REFINED = "llm_refined"
    HYBRID = "hybrid"
    MANUAL = "manual"


class CodeElement(BaseModel):
    """Represents a parsed code element (class, function, etc.) from a source file."""

    qualified_name: str
    kind: CodeElementKind
    file_path: str
    language: str
    annotations: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    base_classes: list[str] = Field(default_factory=list)
    method_calls: list[str] = Field(default_factory=list)
    layer: ArchitecturalLayer = ArchitecturalLayer.UNKNOWN
    role: str = ""
    filtered: bool = False
    filter_reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DependencyEdge(BaseModel):
    """Directed dependency edge between two qualified names."""

    source: str
    target: str
    dependency_type: DependencyType
    weight: float = Field(default=1.0, gt=0)


class ComponentRelationship(BaseModel):
    """Named relationship between two extracted component names."""

    source_component: str
    target_component: str
    label: str = ""


class ComponentObject(BaseModel):
    """An extracted C4 component with confidence, code elements, and metadata."""

    component_id: str
    name: str
    description: str = ""
    technology: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_method: ExtractionMethod = ExtractionMethod.HYBRID
    code_elements: list[CodeElement] = Field(default_factory=list)
    relationships: list[ComponentRelationship] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FrameworkResult(BaseModel):
    """Output of a single framework-based detector pass."""

    detector_name: str
    components: list[ComponentObject] = Field(default_factory=list)
    ungrouped_elements: list[CodeElement] = Field(default_factory=list)
