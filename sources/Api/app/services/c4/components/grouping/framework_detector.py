"""Framework-based component detection registry and matchers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import Counter, defaultdict

from app.services.c4.components.models import (
    CodeElement,
    ComponentObject,
    ComponentRelationship,
    ComponentType,
    ExtractionMethod,
    FrameworkResult,
)

SPRING_ANNOTATIONS: frozenset[str] = frozenset({
    "Controller", "RestController", "Service",
    "Repository", "Component", "Autowired",
    "SpringBootApplication", "Configuration", "Bean",
})

_ROLE_SUFFIXES = re.compile(
    r"(Controller|Service|Repository|Dao|Impl|Component)$", re.IGNORECASE
)

_CONTROLLER_ANNOTATIONS = frozenset({"Controller", "RestController"})
_SERVICE_ANNOTATIONS = frozenset({"Service"})
_REPOSITORY_ANNOTATIONS = frozenset({"Repository"})

_ROLE_TO_COMPONENT_TYPE: dict[str, ComponentType] = {
    "controller": ComponentType.CONTROLLER,
    "service": ComponentType.SERVICE,
    "repository": ComponentType.REPOSITORY,
}


def _domain(qualified_name: str) -> str:
    simple = qualified_name.rsplit(".", 1)[-1]
    stripped = _ROLE_SUFFIXES.sub("", simple)
    return stripped or simple


def _element_role(element: CodeElement) -> str:
    ann = set(element.annotations)
    name = element.qualified_name.rsplit(".", 1)[-1]

    if ann & _CONTROLLER_ANNOTATIONS or name.endswith("Controller"):
        return "controller"
    if ann & _SERVICE_ANNOTATIONS or name.endswith("Service"):
        return "service"
    if ann & _REPOSITORY_ANNOTATIONS or name.endswith("Repository") or name.endswith("Dao"):
        return "repository"
    return "other"


def _has_spring(element: CodeElement) -> bool:
    if element.language not in ("java", "kotlin"):
        return False
    return bool(set(element.annotations) & SPRING_ANNOTATIONS)


# ---------------------------------------------------------------------------
# Django helpers
# ---------------------------------------------------------------------------

_DJANGO_FILE_PATTERN = re.compile(r'(models|views|serializers)\.py$')
_DJANGO_IMPORT_PATTERN = re.compile(r'^django\b|^rest_framework\b')
_FASTAPI_IMPORT_PATTERN = re.compile(r'APIRouter|fastapi')
_FASTAPI_ROUTER_ANNOTATION = re.compile(r'^router\.')


def _django_app_dir(file_path: str) -> str:
    """Return the parent directory name (the Django app name)."""
    import os
    return os.path.basename(os.path.dirname(file_path)) or file_path


def _is_django_element(element: CodeElement) -> bool:
    if not _DJANGO_FILE_PATTERN.search(element.file_path):
        return False
    return any(_DJANGO_IMPORT_PATTERN.match(imp) for imp in element.imports)


def _is_fastapi_element(element: CodeElement) -> bool:
    has_import = any(_FASTAPI_IMPORT_PATTERN.search(imp) for imp in element.imports)
    has_annotation = any(_FASTAPI_ROUTER_ANNOTATION.match(ann) for ann in element.annotations)
    return has_import or has_annotation


def _fastapi_group_key(element: CodeElement) -> str:
    """Return a meaningful group key for FastAPI elements.

    Uses the file stem (without extension) rather than the directory name
    when the parent directory looks like a project root (contains hyphens).
    """
    import os
    dir_name = os.path.basename(os.path.dirname(element.file_path))
    file_stem = os.path.splitext(os.path.basename(element.file_path))[0]
    if not dir_name or "-" in dir_name:
        return file_stem
    return dir_name


class FrameworkMatcher(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def detect(self, elements: list[CodeElement]) -> float:
        """Return confidence score 0.0–1.0 for this framework."""

    @abstractmethod
    def group(self, elements: list[CodeElement]) -> FrameworkResult:
        """Group elements into ComponentObjects."""


class SpringPatternMatcher(FrameworkMatcher):
    @property
    def name(self) -> str:
        return "SpringPatternMatcher"

    def detect(self, elements: list[CodeElement]) -> float:
        if not elements:
            return 0.0
        spring_count = sum(1 for e in elements if _has_spring(e))
        return spring_count / len(elements)

    def group(self, elements: list[CodeElement]) -> FrameworkResult:
        # Group elements by domain prefix
        domain_elements: dict[str, list[CodeElement]] = defaultdict(list)
        for element in elements:
            domain_elements[_domain(element.qualified_name)].append(element)

        # Determine which domains have at least one Spring-annotated element
        spring_domains: set[str] = set()
        for domain, elems in domain_elements.items():
            if any(_has_spring(e) for e in elems):
                spring_domains.add(domain)

        components: list[ComponentObject] = []
        ungrouped: list[CodeElement] = []

        # Build domain→role map for relationship wiring
        domain_roles: dict[str, set[str]] = {}
        domain_to_component: dict[str, ComponentObject] = {}

        for domain, elems in domain_elements.items():
            if domain not in spring_domains:
                ungrouped.extend(elems)
                continue

            roles = {_element_role(e) for e in elems}
            domain_roles[domain] = roles

            role_counts = Counter(_element_role(e) for e in elems)
            dominant_role, _ = role_counts.most_common(1)[0]
            component_type = _ROLE_TO_COMPONENT_TYPE.get(dominant_role, ComponentType.COMPONENT)

            local_confidence = self.detect(elems)
            component = ComponentObject(
                component_id=f"spring_{domain.lower()}",
                name=domain,
                technology="Spring",
                component_type=component_type,
                extraction_method=ExtractionMethod.FRAMEWORK_DETECTION,
                confidence=local_confidence,
                code_elements=elems,
            )
            components.append(component)
            domain_to_component[domain] = component

        # Build relationships
        for domain, component in domain_to_component.items():
            roles = domain_roles[domain]

            if "controller" in roles:
                # controller → service (same or any service domain)
                if "service" in roles:
                    # Both in same component — no cross-component relationship needed
                    pass
                else:
                    for other_domain, other_comp in domain_to_component.items():
                        if other_domain != domain and "service" in domain_roles[other_domain]:
                            component.relationships.append(ComponentRelationship(
                                source_component=domain,
                                target_component=other_domain,
                                label="uses",
                            ))
                            break

            if "service" in roles:
                if "repository" not in roles:
                    for other_domain, other_comp in domain_to_component.items():
                        if other_domain != domain and "repository" in domain_roles[other_domain]:
                            component.relationships.append(ComponentRelationship(
                                source_component=domain,
                                target_component=other_domain,
                                label="uses",
                            ))
                            break

        return FrameworkResult(
            detector_name="SpringPatternMatcher",
            components=components,
            ungrouped_elements=ungrouped,
        )


class DjangoPatternMatcher(FrameworkMatcher):
    @property
    def name(self) -> str:
        return "DjangoPatternMatcher"

    def detect(self, elements: list[CodeElement]) -> float:
        if not elements:
            return 0.0
        return sum(1 for e in elements if _is_django_element(e)) / len(elements)

    def group(self, elements: list[CodeElement]) -> FrameworkResult:
        # Find which directories contain a models.py → those are Django apps
        app_dirs_with_models: set[str] = set()
        for e in elements:
            if e.file_path.endswith("models.py"):
                app_dirs_with_models.add(_django_app_dir(e.file_path))

        dir_elements: dict[str, list[CodeElement]] = defaultdict(list)
        for e in elements:
            if _is_django_element(e):
                dir_elements[_django_app_dir(e.file_path)].append(e)

        components: list[ComponentObject] = []
        ungrouped: list[CodeElement] = []

        for app_dir, elems in dir_elements.items():
            if app_dir not in app_dirs_with_models:
                ungrouped.extend(elems)
                continue
            local_confidence = self.detect(elems)
            components.append(ComponentObject(
                component_id=f"django_{app_dir.lower()}",
                name=app_dir.capitalize(),
                technology="Django",
                extraction_method=ExtractionMethod.FRAMEWORK_DETECTION,
                confidence=local_confidence,
                code_elements=elems,
            ))

        # Elements not in Django-typical files go to ungrouped
        django_file_paths = {e.file_path for elems in dir_elements.values() for e in elems}
        for e in elements:
            if e.file_path not in django_file_paths:
                ungrouped.append(e)

        return FrameworkResult(
            detector_name="DjangoPatternMatcher",
            components=components,
            ungrouped_elements=ungrouped,
        )


class FastAPIPatternMatcher(FrameworkMatcher):
    @property
    def name(self) -> str:
        return "FastAPIPatternMatcher"

    def detect(self, elements: list[CodeElement]) -> float:
        if not elements:
            return 0.0
        return sum(1 for e in elements if _is_fastapi_element(e)) / len(elements)

    def group(self, elements: list[CodeElement]) -> FrameworkResult:
        group_elements: dict[str, list[CodeElement]] = defaultdict(list)
        for e in elements:
            if _is_fastapi_element(e):
                group_elements[_fastapi_group_key(e)].append(e)

        components: list[ComponentObject] = []
        ungrouped: list[CodeElement] = []

        for key, elems in group_elements.items():
            local_confidence = self.detect(elems)
            components.append(ComponentObject(
                component_id=f"fastapi_{key.lower()}",
                name=key.capitalize(),
                technology="FastAPI",
                extraction_method=ExtractionMethod.FRAMEWORK_DETECTION,
                confidence=local_confidence,
                code_elements=elems,
            ))

        fastapi_paths = {e.file_path for elems in group_elements.values() for e in elems}
        for e in elements:
            if e.file_path not in fastapi_paths:
                ungrouped.append(e)

        return FrameworkResult(
            detector_name="FastAPIPatternMatcher",
            components=components,
            ungrouped_elements=ungrouped,
        )


# ---------------------------------------------------------------------------
# NestJS / Express helpers
# ---------------------------------------------------------------------------

_NESTJS_DECORATORS: frozenset[str] = frozenset({
    "Controller", "Injectable", "Guard", "Interceptor", "Pipe",
})

_EXPRESS_IMPORT_PATTERN = re.compile(r'\bexpress\b')

_TS_JS_LANGUAGES = frozenset({"typescript", "tsx", "javascript"})


def _is_nestjs_element(element: CodeElement) -> bool:
    if element.language not in _TS_JS_LANGUAGES:
        return False
    return bool(set(element.annotations) & _NESTJS_DECORATORS)


def _is_express_element(element: CodeElement) -> bool:
    if element.language not in _TS_JS_LANGUAGES:
        return False
    return any(_EXPRESS_IMPORT_PATTERN.search(imp) for imp in element.imports)


def _nestjs_role(element: CodeElement) -> str:
    ann = set(element.annotations)
    name = element.qualified_name.rsplit(".", 1)[-1]
    if "Controller" in ann:
        return "controller"
    if "Injectable" in ann:
        if name.endswith("Service"):
            return "service"
        if name.endswith("Repository"):
            return "repository"
    return "other"


class NestJSExpressPatternMatcher(FrameworkMatcher):
    @property
    def name(self) -> str:
        return "NestJSExpressPatternMatcher"

    def detect(self, elements: list[CodeElement]) -> float:
        if not elements:
            return 0.0
        ts_js = [e for e in elements if e.language in _TS_JS_LANGUAGES]
        if not ts_js:
            return 0.0
        matching = sum(
            1 for e in ts_js if _is_nestjs_element(e) or _is_express_element(e)
        )
        return matching / len(ts_js)

    def group(self, elements: list[CodeElement]) -> FrameworkResult:
        import os

        nestjs_elements = [e for e in elements if _is_nestjs_element(e)]
        express_elements = [
            e for e in elements
            if _is_express_element(e) and not _is_nestjs_element(e)
        ]
        matched_paths = (
            {e.file_path for e in nestjs_elements} |
            {e.file_path for e in express_elements}
        )
        ungrouped = [e for e in elements if e.file_path not in matched_paths]

        components: list[ComponentObject] = []

        # NestJS: group by directory
        dir_elements: dict[str, list[CodeElement]] = defaultdict(list)
        for e in nestjs_elements:
            dir_name = os.path.basename(os.path.dirname(e.file_path))
            file_stem = os.path.splitext(os.path.basename(e.file_path))[0]
            key = file_stem if (not dir_name or "-" in dir_name) else dir_name
            dir_elements[key].append(e)

        for key, elems in dir_elements.items():
            local_confidence = sum(
                1 for e in elems if _is_nestjs_element(e)
            ) / len(elems)
            role_counts = Counter(_nestjs_role(e) for e in elems)
            dominant_role, _ = role_counts.most_common(1)[0]
            component_type = _ROLE_TO_COMPONENT_TYPE.get(dominant_role, ComponentType.COMPONENT)
            components.append(ComponentObject(
                component_id=f"nestjs_{key.lower()}",
                name=key.capitalize(),
                technology="NestJS",
                component_type=component_type,
                extraction_method=ExtractionMethod.FRAMEWORK_DETECTION,
                confidence=local_confidence,
                code_elements=elems,
            ))

        # Express: group by file
        file_elements: dict[str, list[CodeElement]] = defaultdict(list)
        for e in express_elements:
            key = os.path.splitext(os.path.basename(e.file_path))[0]
            file_elements[key].append(e)

        for key, elems in file_elements.items():
            local_confidence = sum(
                1 for e in elems if _is_express_element(e)
            ) / len(elems)
            components.append(ComponentObject(
                component_id=f"express_{key.lower()}",
                name=key.capitalize(),
                technology="Express",
                component_type=ComponentType.COMPONENT,
                extraction_method=ExtractionMethod.FRAMEWORK_DETECTION,
                confidence=local_confidence,
                code_elements=elems,
            ))

        return FrameworkResult(
            detector_name="NestJSExpressPatternMatcher",
            components=components,
            ungrouped_elements=ungrouped,
        )


class FrameworkDetectorRegistry:
    _CONFIDENCE_THRESHOLD = 0.5

    def __init__(self, matchers: list[FrameworkMatcher] | None = None) -> None:
        self._matchers = matchers or [
            SpringPatternMatcher(),
            DjangoPatternMatcher(),
            FastAPIPatternMatcher(),
            NestJSExpressPatternMatcher(),
        ]

    def detect(self, elements: list[CodeElement]) -> FrameworkResult | None:
        best: tuple[float, FrameworkResult] | None = None
        for matcher in self._matchers:
            confidence = matcher.detect(elements)
            if confidence > self._CONFIDENCE_THRESHOLD:
                if best is None or confidence > best[0]:
                    best = (confidence, matcher.group(elements))
        return best[1] if best else None

    def detect_with_confidence(
        self, elements: list[CodeElement]
    ) -> tuple[float, FrameworkResult] | None:
        best: tuple[float, FrameworkResult] | None = None
        for matcher in self._matchers:
            confidence = matcher.detect(elements)
            if confidence > self._CONFIDENCE_THRESHOLD:
                if best is None or confidence > best[0]:
                    best = (confidence, matcher.group(elements))
        return best
