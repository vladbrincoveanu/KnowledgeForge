"""Unit tests for PythonVisitor."""

from __future__ import annotations

import pytest
from tree_sitter_language_pack import get_parser

from app.services.c4.components.models import ArchitecturalLayer
from app.services.c4.components.parsing.visitors.python_visitor import PythonVisitor

_parser = get_parser("python")


def _visit(source: bytes, file_path: str = "app/module.py"):
    tree = _parser.parse(source)
    return PythonVisitor().visit(tree, file_path, source)


FLASK_SOURCE = b"""
from flask import Blueprint
bp = Blueprint('users', __name__)

@bp.route('/users', methods=['GET'])
def list_users():
    pass

class UserController:
    pass
"""

FASTAPI_SOURCE = b"""
from fastapi import APIRouter
router = APIRouter()

@router.get('/items')
async def get_items():
    pass
"""

DJANGO_SOURCE = b"""
from rest_framework.views import APIView

class OrderAPIView(APIView):
    pass

class ProductViewSet(ModelViewSet):
    pass
"""

SERVICE_SOURCE = b"""
class UserService:
    def create_user(self):
        pass
"""

REPO_SOURCE = b"""
class UserRepository:
    def find_by_id(self, id):
        pass
"""


def test_supported_languages():
    assert PythonVisitor().supported_languages == ["python"]


def test_flask_route_function_is_presentation():
    elements = _visit(FLASK_SOURCE)
    el = next(e for e in elements if e.qualified_name.endswith("list_users"))
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_controller_class_name_is_presentation():
    elements = _visit(FLASK_SOURCE)
    el = next(e for e in elements if e.qualified_name.endswith("UserController"))
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_fastapi_route_is_presentation():
    elements = _visit(FASTAPI_SOURCE)
    el = next(e for e in elements if e.qualified_name.endswith("get_items"))
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_django_apiview_is_presentation():
    elements = _visit(DJANGO_SOURCE)
    el = next(e for e in elements if e.qualified_name.endswith("OrderAPIView"))
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_django_viewset_is_presentation():
    elements = _visit(DJANGO_SOURCE)
    el = next(e for e in elements if e.qualified_name.endswith("ProductViewSet"))
    assert el.layer == ArchitecturalLayer.PRESENTATION


def test_service_class_is_business():
    elements = _visit(SERVICE_SOURCE)
    el = next(e for e in elements if e.qualified_name.endswith("UserService"))
    assert el.layer == ArchitecturalLayer.BUSINESS


def test_repository_class_is_data_access():
    elements = _visit(REPO_SOURCE)
    el = next(e for e in elements if e.qualified_name.endswith("UserRepository"))
    assert el.layer == ArchitecturalLayer.DATA_ACCESS


def test_qualified_name_python():
    elements = _visit(SERVICE_SOURCE, file_path="app/service.py")
    el = next(e for e in elements if e.qualified_name.endswith("UserService"))
    assert el.qualified_name == "app.service.UserService"


def test_imports_captured():
    elements = _visit(FLASK_SOURCE)
    el = next(e for e in elements if e.qualified_name.endswith("UserController"))
    assert any("flask" in imp for imp in el.imports)


def test_empty_file_returns_empty_list():
    elements = _visit(b"")
    assert elements == []


def test_syntax_error_returns_partial():
    broken = b"""
class GoodClass:
    pass

def broken_func(
    # missing closing paren
"""
    elements = _visit(broken)
    assert isinstance(elements, list)
    names = [e.qualified_name for e in elements]
    assert any("GoodClass" in n for n in names)
