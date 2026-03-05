"""Tests for BaseVisitor ABC and its helper methods."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.c4.components.models import ArchitecturalLayer
from app.services.c4.components.parsing.visitors import BaseVisitor


# ---------------------------------------------------------------------------
# Concrete stub
# ---------------------------------------------------------------------------


class _StubVisitor(BaseVisitor):
    @property
    def supported_languages(self) -> list[str]:
        return ["stub"]

    def visit(self, tree, file_path, source):
        return []


# ---------------------------------------------------------------------------
# ABC enforcement
# ---------------------------------------------------------------------------


def test_abc_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseVisitor()  # type: ignore[abstract]


def test_stub_visitor_instantiates():
    v = _StubVisitor()
    assert v.supported_languages == ["stub"]


# ---------------------------------------------------------------------------
# _node_text
# ---------------------------------------------------------------------------


def test_node_text():
    source = b"hello world"
    node = MagicMock()
    node.start_byte = 6
    node.end_byte = 11
    assert _StubVisitor._node_text(node, source) == "world"


def test_node_text_with_utf8():
    source = "café".encode("utf-8")
    node = MagicMock()
    node.start_byte = 0
    node.end_byte = len(source)
    assert _StubVisitor._node_text(node, source) == "café"


# ---------------------------------------------------------------------------
# _qualified_name — Python
# ---------------------------------------------------------------------------


def test_qualified_name_python():
    result = _StubVisitor._qualified_name("src/app/service.py", "MyClass")
    assert result == "src.app.service.MyClass"


def test_qualified_name_python_root():
    result = _StubVisitor._qualified_name("module.py", "Foo")
    assert result == "module.Foo"


# ---------------------------------------------------------------------------
# _qualified_name — Java
# ---------------------------------------------------------------------------


def test_qualified_name_java_with_package():
    result = _StubVisitor._qualified_name("com/example/Svc.java", "Svc", package="com.example")
    assert result == "com.example.Svc"


def test_qualified_name_java_no_package():
    result = _StubVisitor._qualified_name("com/example/Svc.java", "Svc")
    assert result == "com.example.Svc.Svc"


# ---------------------------------------------------------------------------
# _qualified_name — default (other extensions)
# ---------------------------------------------------------------------------


def test_qualified_name_default():
    result = _StubVisitor._qualified_name("src/utils/helpers.go", "Foo")
    assert result == "src.utils.helpers.Foo"


# ---------------------------------------------------------------------------
# _detect_layer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "annotations,name,expected",
    [
        # annotation-driven
        (["@Controller"], "SomeClass", ArchitecturalLayer.PRESENTATION),
        (["@Handler"], "SomeClass", ArchitecturalLayer.PRESENTATION),
        (["@Service"], "SomeClass", ArchitecturalLayer.BUSINESS),
        (["@Repository"], "SomeClass", ArchitecturalLayer.DATA_ACCESS),
        (["@Config"], "SomeClass", ArchitecturalLayer.INFRASTRUCTURE),
        # name-driven
        ([], "UserController", ArchitecturalLayer.PRESENTATION),
        ([], "OrderEndpoint", ArchitecturalLayer.PRESENTATION),
        ([], "PaymentService", ArchitecturalLayer.BUSINESS),
        ([], "ProductUseCase", ArchitecturalLayer.BUSINESS),
        ([], "UserRepository", ArchitecturalLayer.DATA_ACCESS),
        ([], "OrderDao", ArchitecturalLayer.DATA_ACCESS),
        ([], "AppConfig", ArchitecturalLayer.INFRASTRUCTURE),
        ([], "AuthMiddleware", ArchitecturalLayer.INFRASTRUCTURE),
        # unknown
        ([], "Helper", ArchitecturalLayer.UNKNOWN),
        ([], "Utils", ArchitecturalLayer.UNKNOWN),
    ],
)
def test_detect_layer(annotations, name, expected):
    assert _StubVisitor._detect_layer(annotations, name) == expected
