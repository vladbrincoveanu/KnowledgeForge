"""Factory for building ComponentObjects with inferred metadata."""

from __future__ import annotations

import os
import re
from collections import Counter

from app.services.c4.components.models import (
    ArchitecturalLayer,
    CodeElement,
    CodeElementKind,
    ComponentObject,
    ComponentType,
    ExtractionMethod,
)
from .community_detector import CommunityDetector

_SPRING_ANNOTATIONS = frozenset({
    "Controller", "RestController", "Service", "Repository",
    "Component", "SpringBootApplication",
})
_DJANGO_FILE_PATTERNS = frozenset({"models.py", "views.py", "serializers.py"})
_DJANGO_IMPORT_RE = re.compile(r'^django\b|^rest_framework\b')
_FASTAPI_IMPORTS = frozenset({"fastapi", "APIRouter"})

_ASPNET_ANNOTATIONS = frozenset({
    "ApiController", "Controller",
    "HttpGet", "HttpPost", "HttpPut", "HttpDelete", "HttpPatch", "Authorize",
})
_DBCONTEXT_BASE = "DbContext"

_NESTJS_DECORATORS = frozenset({"Controller", "Injectable", "Guard", "Interceptor", "Pipe"})
_EXPRESS_IMPORT_RE = re.compile(r'\bexpress\b')

_LAYER_TO_COMPONENT_TYPE: dict[ArchitecturalLayer, ComponentType] = {
    ArchitecturalLayer.PRESENTATION: ComponentType.CONTROLLER,
    ArchitecturalLayer.BUSINESS: ComponentType.SERVICE,
    ArchitecturalLayer.DATA_ACCESS: ComponentType.REPOSITORY,
    ArchitecturalLayer.INFRASTRUCTURE: ComponentType.COMPONENT,
}
_ROLE_TO_COMPONENT_TYPE: dict[str, ComponentType] = {
    "controller": ComponentType.CONTROLLER,
    "service": ComponentType.SERVICE,
    "repository": ComponentType.REPOSITORY,
}

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
        component_type = self._infer_component_type(group)
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
            component_type=component_type,
            extraction_method=method,
            confidence=confidence,
            code_elements=group,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _infer_technology(self, group: list[CodeElement]) -> str:
        languages = [e.language for e in group if e.language]
        if not languages:
            return ""
        dominant_lang, _ = Counter(languages).most_common(1)[0]

        if dominant_lang in ("java", "kotlin"):
            if any(ann in _SPRING_ANNOTATIONS for e in group for ann in e.annotations):
                return "Spring"
            return dominant_lang.title()

        if dominant_lang == "csharp":
            has_aspnet = any(ann in _ASPNET_ANNOTATIONS for e in group for ann in e.annotations)
            has_dbcontext = any(_DBCONTEXT_BASE in bc for e in group for bc in e.base_classes)
            if has_dbcontext:
                return "ASP.NET / Entity Framework"
            if has_aspnet:
                return "ASP.NET"
            return "C#"

        if dominant_lang in ("typescript", "tsx"):
            if any(ann in _NESTJS_DECORATORS for e in group for ann in e.annotations):
                return "NestJS"
            return dominant_lang.title()

        if dominant_lang == "javascript":
            if any(_EXPRESS_IMPORT_RE.search(imp) for e in group for imp in e.imports):
                return "Express"
            return "JavaScript"

        if dominant_lang == "python":
            for element in group:
                if (os.path.basename(element.file_path) in _DJANGO_FILE_PATTERNS
                        and any(_DJANGO_IMPORT_RE.match(imp) for imp in element.imports)):
                    return "Django"
            for element in group:
                if any(imp in _FASTAPI_IMPORTS for imp in element.imports):
                    return "FastAPI"
            return "Python"

        return dominant_lang.title()

    def _infer_component_type(self, group: list[CodeElement]) -> ComponentType:
        votes: list[ComponentType] = []
        for element in group:
            ct = _LAYER_TO_COMPONENT_TYPE.get(element.layer)
            if ct is not None:
                votes.append(ct)
            if element.role in _ROLE_TO_COMPONENT_TYPE:
                votes.append(_ROLE_TO_COMPONENT_TYPE[element.role])
        if votes:
            dominant, _ = Counter(votes).most_common(1)[0]
            return dominant
        return ComponentType.COMPONENT

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
