"""Tests for framework_detector.py — Spring pattern matcher and registry."""

from __future__ import annotations

import pytest

from app.services.c4.components.models import CodeElement, CodeElementKind, ExtractionMethod
from app.services.c4.components.grouping import (
    FrameworkDetectorRegistry,
    SpringPatternMatcher,
    DjangoPatternMatcher,
    FastAPIPatternMatcher,
)


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _spring_element(qualified_name: str, annotation: str, language: str = "java") -> CodeElement:
    return CodeElement(
        qualified_name=qualified_name,
        kind=CodeElementKind.CLASS,
        file_path=f"src/{qualified_name.replace('.', '/')}.java",
        language=language,
        annotations=[annotation],
    )


def _plain_element(qualified_name: str) -> CodeElement:
    return CodeElement(
        qualified_name=qualified_name,
        kind=CodeElementKind.CLASS,
        file_path=f"src/{qualified_name.replace('.', '/')}.java",
        language="java",
        annotations=[],
    )


@pytest.fixture
def user_elements() -> list[CodeElement]:
    return [
        _spring_element("com.example.UserController", "Controller"),
        _spring_element("com.example.UserService", "Service"),
        _spring_element("com.example.UserRepository", "Repository"),
    ]


@pytest.fixture
def order_elements() -> list[CodeElement]:
    return [
        _spring_element("com.example.OrderController", "Controller"),
        _spring_element("com.example.OrderService", "Service"),
        _spring_element("com.example.OrderRepository", "Repository"),
    ]


@pytest.fixture
def plain_element() -> CodeElement:
    return _plain_element("com.example.PlainHelper")


@pytest.fixture
def all_elements(user_elements, order_elements, plain_element) -> list[CodeElement]:
    return user_elements + order_elements + [plain_element]


# ---------------------------------------------------------------------------
# detect() — confidence / threshold
# ---------------------------------------------------------------------------


class TestSpringDetect:
    def test_all_spring_returns_1(self, user_elements):
        matcher = SpringPatternMatcher()
        assert matcher.detect(user_elements) == pytest.approx(1.0)

    def test_one_of_four_below_threshold(self, plain_element, user_elements):
        # 1 Spring out of 4 total → 0.25 < 0.3
        elements = [plain_element, _plain_element("com.example.Util"), _plain_element("com.example.Foo"),
                    _spring_element("com.example.FooController", "Controller")]
        assert matcher.detect(elements) == pytest.approx(0.25)

    def test_empty_returns_zero(self):
        matcher = SpringPatternMatcher()
        assert matcher.detect([]) == 0.0


# Standalone instance for the detect test above
matcher = SpringPatternMatcher()


# ---------------------------------------------------------------------------
# group() — domain grouping
# ---------------------------------------------------------------------------


class TestSpringGroup:
    def test_user_domain_grouped(self, user_elements):
        result = SpringPatternMatcher().group(user_elements)
        names = {c.name for c in result.components}
        assert "User" in names

    def test_order_domain_grouped(self, order_elements):
        result = SpringPatternMatcher().group(order_elements)
        names = {c.name for c in result.components}
        assert "Order" in names

    def test_user_component_has_all_three_elements(self, user_elements):
        result = SpringPatternMatcher().group(user_elements)
        user_comp = next(c for c in result.components if c.name == "User")
        assert len(user_comp.code_elements) == 3

    def test_order_component_has_three_elements(self, order_elements):
        result = SpringPatternMatcher().group(order_elements)
        order_comp = next(c for c in result.components if c.name == "Order")
        assert len(order_comp.code_elements) == 3

    def test_two_domains_yield_two_components(self, user_elements, order_elements):
        result = SpringPatternMatcher().group(user_elements + order_elements)
        assert len(result.components) == 2


# ---------------------------------------------------------------------------
# technology & extraction_method
# ---------------------------------------------------------------------------


class TestSpringMetadata:
    def test_technology_is_spring(self, user_elements):
        result = SpringPatternMatcher().group(user_elements)
        for comp in result.components:
            assert comp.technology == "Spring"

    def test_extraction_method_is_framework_detection(self, user_elements):
        result = SpringPatternMatcher().group(user_elements)
        for comp in result.components:
            assert comp.extraction_method == ExtractionMethod.FRAMEWORK_DETECTION


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


class TestSpringRelationships:
    def test_user_component_has_intra_domain_elements(self, user_elements):
        """When controller/service/repo are in the same domain group, all in one component."""
        result = SpringPatternMatcher().group(user_elements)
        user_comp = next(c for c in result.components if c.name == "User")
        # All three elements in one component
        kinds = {e.qualified_name for e in user_comp.code_elements}
        assert "com.example.UserController" in kinds
        assert "com.example.UserService" in kinds
        assert "com.example.UserRepository" in kinds

    def test_cross_domain_relationship_controller_to_service(self):
        """When controller and service are in different domains, relationship is added."""
        ctrl = _spring_element("com.example.FooController", "Controller")
        svc = _spring_element("com.example.BarService", "Service")
        result = SpringPatternMatcher().group([ctrl, svc])

        foo_comp = next(c for c in result.components if c.name == "Foo")
        rel_targets = {r.target_component for r in foo_comp.relationships}
        assert "Bar" in rel_targets

    def test_cross_domain_relationship_service_to_repository(self):
        """When service and repository are in different domains, relationship is added."""
        svc = _spring_element("com.example.FooService", "Service")
        repo = _spring_element("com.example.BarRepository", "Repository")
        result = SpringPatternMatcher().group([svc, repo])

        foo_comp = next(c for c in result.components if c.name == "Foo")
        rel_targets = {r.target_component for r in foo_comp.relationships}
        assert "Bar" in rel_targets

    def test_relationship_source_and_target_names(self):
        ctrl = _spring_element("com.example.FooController", "Controller")
        svc = _spring_element("com.example.BarService", "Service")
        result = SpringPatternMatcher().group([ctrl, svc])

        foo_comp = next(c for c in result.components if c.name == "Foo")
        assert any(
            r.source_component == "Foo" and r.target_component == "Bar"
            for r in foo_comp.relationships
        )


# ---------------------------------------------------------------------------
# Ungrouped elements
# ---------------------------------------------------------------------------


class TestUngrouped:
    def test_plain_helper_is_ungrouped(self, all_elements, plain_element):
        result = SpringPatternMatcher().group(all_elements)
        ungrouped_names = {e.qualified_name for e in result.ungrouped_elements}
        assert plain_element.qualified_name in ungrouped_names

    def test_spring_elements_not_in_ungrouped(self, user_elements):
        result = SpringPatternMatcher().group(user_elements)
        assert result.ungrouped_elements == []


# ---------------------------------------------------------------------------
# FrameworkDetectorRegistry
# ---------------------------------------------------------------------------


class TestFrameworkDetectorRegistry:
    def test_all_spring_returns_framework_result(self, user_elements):
        registry = FrameworkDetectorRegistry()
        result = registry.detect(user_elements)
        assert result is not None
        assert len(result.components) > 0

    def test_below_threshold_returns_none(self, plain_element):
        # 1 Spring element mixed with 3 plain → 0.25 < 0.5 threshold
        elements = [
            plain_element,
            _plain_element("com.example.Util"),
            _plain_element("com.example.Foo"),
            _spring_element("com.example.FooController", "Controller"),
        ]
        registry = FrameworkDetectorRegistry()
        result = registry.detect(elements)
        assert result is None

    def test_registry_has_three_default_matchers(self):
        registry = FrameworkDetectorRegistry()
        names = {m.name for m in registry._matchers}
        assert "SpringPatternMatcher" in names
        assert "DjangoPatternMatcher" in names
        assert "FastAPIPatternMatcher" in names

    def test_custom_matcher_higher_confidence_wins(self, user_elements):
        """Registry picks matcher with higher confidence."""
        from app.services.c4.components.grouping.framework_detector import FrameworkMatcher
        from app.services.c4.components.models import FrameworkResult

        class HighConfidenceMatcher(FrameworkMatcher):
            @property
            def name(self) -> str:
                return "High"

            def detect(self, elements):
                return 0.9

            def group(self, elements):
                return FrameworkResult(detector_name="High")

        class LowConfidenceMatcher(FrameworkMatcher):
            @property
            def name(self) -> str:
                return "Low"

            def detect(self, elements):
                return 0.6

            def group(self, elements):
                return FrameworkResult(detector_name="Low")

        registry = FrameworkDetectorRegistry(matchers=[LowConfidenceMatcher(), HighConfidenceMatcher()])
        result = registry.detect(user_elements)
        assert result is not None
        assert result.detector_name == "High"


# ---------------------------------------------------------------------------
# Django helpers
# ---------------------------------------------------------------------------


def _django_element(file_path: str, name: str = "MyModel") -> CodeElement:
    return CodeElement(
        qualified_name=name,
        kind=CodeElementKind.CLASS,
        file_path=file_path,
        language="Python",
        imports=["django.db.models"],
    )


def _fastapi_element(
    name: str,
    imports: list[str] | None = None,
    annotations: list[str] | None = None,
) -> CodeElement:
    return CodeElement(
        qualified_name=name,
        kind=CodeElementKind.CLASS,
        file_path=f"{name.lower()}.py",
        language="Python",
        imports=imports or [],
        annotations=annotations or [],
    )


# ---------------------------------------------------------------------------
# DjangoPatternMatcher — detect()
# ---------------------------------------------------------------------------


class TestDjangoDetect:
    def test_all_django_files_returns_1(self):
        elements = [
            _django_element("users/models.py"),
            _django_element("users/views.py"),
            _django_element("users/serializers.py"),
        ]
        assert DjangoPatternMatcher().detect(elements) == pytest.approx(1.0)

    def test_mixed_files_proportional(self):
        elements = [
            _django_element("users/models.py"),
            _django_element("utils/helpers.py"),  # not a Django-typical file
        ]
        assert DjangoPatternMatcher().detect(elements) == pytest.approx(0.5)

    def test_empty_returns_zero(self):
        assert DjangoPatternMatcher().detect([]) == 0.0


# ---------------------------------------------------------------------------
# DjangoPatternMatcher — group()
# ---------------------------------------------------------------------------


class TestDjangoGroup:
    def test_app_with_models_creates_component(self):
        elements = [
            _django_element("users/models.py", "UserModel"),
            _django_element("users/views.py", "UserView"),
        ]
        result = DjangoPatternMatcher().group(elements)
        names = {c.name for c in result.components}
        assert "Users" in names

    def test_app_without_models_goes_to_ungrouped(self):
        elements = [
            _django_element("orders/views.py", "OrderView"),
            _django_element("orders/serializers.py", "OrderSerializer"),
        ]
        result = DjangoPatternMatcher().group(elements)
        assert result.components == []
        assert len(result.ungrouped_elements) == 2

    def test_non_django_files_go_to_ungrouped(self):
        non_django = _django_element("utils/helpers.py", "HelperClass")
        django = _django_element("users/models.py", "UserModel")
        result = DjangoPatternMatcher().group([non_django, django])
        ungrouped_names = {e.qualified_name for e in result.ungrouped_elements}
        assert "HelperClass" in ungrouped_names

    def test_technology_is_django(self):
        elements = [_django_element("users/models.py", "UserModel")]
        result = DjangoPatternMatcher().group(elements)
        for comp in result.components:
            assert comp.technology == "Django"

    def test_extraction_method_is_framework_detection(self):
        elements = [_django_element("users/models.py", "UserModel")]
        result = DjangoPatternMatcher().group(elements)
        for comp in result.components:
            assert comp.extraction_method == ExtractionMethod.FRAMEWORK_DETECTION

    def test_two_apps_yield_two_components(self):
        elements = [
            _django_element("users/models.py", "UserModel"),
            _django_element("orders/models.py", "OrderModel"),
        ]
        result = DjangoPatternMatcher().group(elements)
        assert len(result.components) == 2


# ---------------------------------------------------------------------------
# FastAPIPatternMatcher — detect()
# ---------------------------------------------------------------------------


class TestFastAPIDetect:
    def test_apiRouter_import_detected(self):
        elements = [_fastapi_element("UsersRouter", imports=["from fastapi import APIRouter"])]
        assert FastAPIPatternMatcher().detect(elements) == pytest.approx(1.0)

    def test_router_annotation_detected(self):
        elements = [_fastapi_element("UsersRouter", annotations=["router.get('/users')"])]
        assert FastAPIPatternMatcher().detect(elements) == pytest.approx(1.0)

    def test_fastapi_import_detected(self):
        elements = [_fastapi_element("App", imports=["import fastapi"])]
        assert FastAPIPatternMatcher().detect(elements) == pytest.approx(1.0)

    def test_mixed_proportional(self):
        elements = [
            _fastapi_element("Router", imports=["from fastapi import APIRouter"]),
            _fastapi_element("Plain"),
        ]
        assert FastAPIPatternMatcher().detect(elements) == pytest.approx(0.5)

    def test_empty_returns_zero(self):
        assert FastAPIPatternMatcher().detect([]) == 0.0


# ---------------------------------------------------------------------------
# FastAPIPatternMatcher — group()
# ---------------------------------------------------------------------------


class TestFastAPIGroup:
    def test_groups_by_directory(self):
        import os
        # Two elements in the same directory (same key)
        e1 = CodeElement(
            qualified_name="UsersRouter",
            kind=CodeElementKind.CLASS,
            file_path="routers/users.py",
            language="Python",
            imports=["from fastapi import APIRouter"],
        )
        e2 = CodeElement(
            qualified_name="UsersEndpoint",
            kind=CodeElementKind.CLASS,
            file_path="routers/users.py",
            language="Python",
            imports=["from fastapi import APIRouter"],
        )
        result = FastAPIPatternMatcher().group([e1, e2])
        assert len(result.components) == 1
        assert result.components[0].name == "Routers"

    def test_technology_is_fastapi(self):
        elements = [_fastapi_element("Router", imports=["from fastapi import APIRouter"])]
        result = FastAPIPatternMatcher().group(elements)
        for comp in result.components:
            assert comp.technology == "FastAPI"

    def test_extraction_method_is_framework_detection(self):
        elements = [_fastapi_element("Router", imports=["from fastapi import APIRouter"])]
        result = FastAPIPatternMatcher().group(elements)
        for comp in result.components:
            assert comp.extraction_method == ExtractionMethod.FRAMEWORK_DETECTION

    def test_non_fastapi_elements_ungrouped(self):
        plain = _fastapi_element("PlainClass")  # no imports or annotations
        fastapi = _fastapi_element("RouterClass", imports=["from fastapi import APIRouter"])
        result = FastAPIPatternMatcher().group([plain, fastapi])
        ungrouped_names = {e.qualified_name for e in result.ungrouped_elements}
        assert "PlainClass" in ungrouped_names

    def test_no_fastapi_elements_all_ungrouped(self):
        elements = [_fastapi_element("Plain1"), _fastapi_element("Plain2")]
        result = FastAPIPatternMatcher().group(elements)
        assert result.components == []
        assert len(result.ungrouped_elements) == 2
