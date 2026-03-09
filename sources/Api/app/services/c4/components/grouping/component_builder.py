"""Factory for building ComponentObjects with inferred metadata."""

from __future__ import annotations

from collections import Counter

from app.services.c4.components.models import (
    ArchitecturalLayer,
    CodeElement,
    CodeElementKind,
    ComponentObject,
    ExtractionMethod,
)
from .community_detector import CommunityDetector

_SPRING_ANNOTATIONS = frozenset({
    "Controller", "RestController", "Service", "Repository",
    "Component", "SpringBootApplication",
})
_DJANGO_FILE_PATTERNS = frozenset({"models.py", "views.py", "serializers.py"})
_FASTAPI_IMPORTS = frozenset({"fastapi", "APIRouter"})

_community_detector = CommunityDetector()


class ComponentBuilder:
    """Builds ComponentObjects from a group of CodeElements with inferred metadata."""

    def build(
        self,
        group: list[CodeElement],
        method: ExtractionMethod,
    ) -> ComponentObject:
        name = _community_detector.name_cluster(group)
        technology = self._infer_technology(group)
        layer = self._infer_layer(group)
        interfaces = [
            e.qualified_name
            for e in group
            if e.kind in (CodeElementKind.INTERFACE, CodeElementKind.ABSTRACT_CLASS)
        ]
        confidence = self._infer_confidence(group, method)
        component_id = f"{method.value}_{name.lower()}"

        metadata: dict = {}
        if interfaces:
            metadata["interfaces"] = interfaces
        if layer != ArchitecturalLayer.UNKNOWN:
            metadata["layer"] = layer.value

        return ComponentObject(
            component_id=component_id,
            name=name,
            technology=technology,
            extraction_method=method,
            confidence=confidence,
            code_elements=group,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _infer_technology(self, group: list[CodeElement]) -> str:
        # Spring: any element has a Spring annotation
        for element in group:
            if any(ann in _SPRING_ANNOTATIONS for ann in element.annotations):
                return "Spring"

        # Django: file name matches known Django patterns
        for element in group:
            import os
            filename = os.path.basename(element.file_path)
            if filename in _DJANGO_FILE_PATTERNS:
                return "Django"

        # FastAPI: imports contain fastapi or APIRouter
        for element in group:
            if any(imp in _FASTAPI_IMPORTS for imp in element.imports):
                return "FastAPI"

        # Fallback: dominant language title-cased
        languages = [e.language for e in group if e.language]
        if languages:
            dominant, _ = Counter(languages).most_common(1)[0]
            return dominant.title()

        return ""

    def _infer_layer(self, group: list[CodeElement]) -> ArchitecturalLayer:
        layers = [
            e.layer for e in group if e.layer != ArchitecturalLayer.UNKNOWN
        ]
        if layers:
            dominant, _ = Counter(layers).most_common(1)[0]
            return dominant
        return ArchitecturalLayer.UNKNOWN

    def _infer_confidence(
        self, group: list[CodeElement], method: ExtractionMethod
    ) -> float:
        if len(group) == 1:
            return 0.3
        if method == ExtractionMethod.FRAMEWORK_DETECTION:
            return 0.9
        if method == ExtractionMethod.LLM_DIRECT:
            return 0.85
        if method == ExtractionMethod.LLM_REFINED:
            return 0.75
        if method == ExtractionMethod.COMMUNITY_DETECTION:
            return 0.5
        return 0.5
