"""Unit tests for NestJSExpressPatternMatcher and Spring language gating."""

from __future__ import annotations

import pytest

from app.services.c4.components.grouping.framework_detector import (
    NestJSExpressPatternMatcher,
    SpringPatternMatcher,
)
from app.services.c4.components.models import CodeElement, CodeElementKind


def _make(
    qualified_name: str,
    file_path: str,
    language: str,
    annotations: list[str] | None = None,
    imports: list[str] | None = None,
) -> CodeElement:
    return CodeElement(
        qualified_name=qualified_name,
        kind=CodeElementKind.CLASS,
        file_path=file_path,
        language=language,
        annotations=annotations or [],
        imports=imports or [],
    )


# ---------------------------------------------------------------------------
# NestJS detection
# ---------------------------------------------------------------------------

NESTJS_ELEMENTS = [
    _make("UserController", "src/users/user.controller.ts", "typescript", ["Controller"]),
    _make("UserService", "src/users/user.service.ts", "typescript", ["Injectable"]),
    _make("UserRepository", "src/users/user.repository.ts", "typescript", ["Injectable"]),
    _make("AuthGuard", "src/auth/auth.guard.ts", "typescript", ["Guard"]),
]


def test_nestjs_detect_confidence_all_match():
    matcher = NestJSExpressPatternMatcher()
    confidence = matcher.detect(NESTJS_ELEMENTS)
    assert confidence == 1.0


def test_nestjs_detect_confidence_partial():
    matcher = NestJSExpressPatternMatcher()
    elements = NESTJS_ELEMENTS + [
        _make("SomeUtil", "src/utils/util.ts", "typescript"),
    ]
    confidence = matcher.detect(elements)
    assert confidence == pytest.approx(4 / 5)


def test_nestjs_detect_ignores_non_ts_js():
    matcher = NestJSExpressPatternMatcher()
    java_element = _make("UserController", "src/UserController.java", "java", ["Controller"])
    confidence = matcher.detect([java_element])
    assert confidence == 0.0


def test_nestjs_group_by_directory():
    matcher = NestJSExpressPatternMatcher()
    result = matcher.group(NESTJS_ELEMENTS)
    names = {c.name for c in result.components}
    assert "Users" in names
    assert "Auth" in names


def test_nestjs_technology():
    matcher = NestJSExpressPatternMatcher()
    result = matcher.group(NESTJS_ELEMENTS)
    for component in result.components:
        assert component.technology == "NestJS"


def test_nestjs_detector_name():
    matcher = NestJSExpressPatternMatcher()
    result = matcher.group(NESTJS_ELEMENTS)
    assert result.detector_name == "NestJSExpressPatternMatcher"


def test_nestjs_unmatched_elements_go_to_ungrouped():
    matcher = NestJSExpressPatternMatcher()
    unmatched = _make("SomeUtil", "src/utils/util.ts", "typescript")
    result = matcher.group(NESTJS_ELEMENTS + [unmatched])
    assert unmatched in result.ungrouped_elements


# ---------------------------------------------------------------------------
# Express detection
# ---------------------------------------------------------------------------

EXPRESS_ELEMENTS = [
    _make("getUser", "src/routes/users.js", "javascript", [], ["express"]),
    _make("createUser", "src/routes/users.js", "javascript", [], ["express"]),
]


def test_express_detect_confidence():
    matcher = NestJSExpressPatternMatcher()
    assert matcher.detect(EXPRESS_ELEMENTS) == 1.0


def test_express_group_by_file():
    matcher = NestJSExpressPatternMatcher()
    result = matcher.group(EXPRESS_ELEMENTS)
    assert len(result.components) == 1
    assert result.components[0].name == "Users"
    assert result.components[0].technology == "Express"


def test_express_no_nestjs_decorators_gives_express_technology():
    matcher = NestJSExpressPatternMatcher()
    element = _make("handler", "src/routes/orders.js", "javascript", [], ["express"])
    result = matcher.group([element])
    assert result.components[0].technology == "Express"


# ---------------------------------------------------------------------------
# Spring language gating
# ---------------------------------------------------------------------------

def test_spring_ignores_typescript_controller():
    matcher = SpringPatternMatcher()
    ts_element = _make("UserController", "src/user.controller.ts", "typescript", ["Controller"])
    assert matcher.detect([ts_element]) == 0.0


def test_spring_ignores_javascript_service():
    matcher = SpringPatternMatcher()
    js_element = _make("UserService", "src/user.service.js", "javascript", ["Service"])
    assert matcher.detect([js_element]) == 0.0


def test_spring_detects_java_controller():
    matcher = SpringPatternMatcher()
    java_element = _make("UserController", "src/UserController.java", "java", ["Controller"])
    assert matcher.detect([java_element]) == 1.0


def test_spring_detects_kotlin_service():
    matcher = SpringPatternMatcher()
    kotlin_element = _make("UserService", "src/UserService.kt", "kotlin", ["Service"])
    assert matcher.detect([kotlin_element]) == 1.0


def test_spring_mixed_ts_and_java_only_counts_java():
    matcher = SpringPatternMatcher()
    elements = [
        _make("UserController", "src/UserController.java", "java", ["Controller"]),
        _make("UserController", "src/user.controller.ts", "typescript", ["Controller"]),
    ]
    # Only the java element counts, so 1/2
    assert matcher.detect(elements) == pytest.approx(0.5)
