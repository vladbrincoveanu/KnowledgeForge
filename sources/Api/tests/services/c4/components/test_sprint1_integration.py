"""Integration test: TreeSitterParser → PythonVisitor on a realistic mini project."""

import pytest

from app.services.c4.components.models import ArchitecturalLayer, CodeElementKind
from app.services.c4.components.parsing.tree_sitter_parser import TreeSitterParser
from app.services.c4.components.parsing.visitors.python_visitor import PythonVisitor


CONTROLLER_SRC = """
from flask import Blueprint
from myapp.services.user_service import UserService

user_bp = Blueprint('users', __name__)

@user_bp.route('/users', methods=['GET'])
def get_users():
    return UserService().get_all()

@user_bp.route('/users/<int:user_id>', methods=['POST'])
def create_user(user_id):
    return UserService().get_by_id(user_id)
"""

SERVICE_SRC = """
from myapp.repositories.user_repository import UserRepository

class UserService:
    def __init__(self):
        self._repo = UserRepository()

    def get_all(self):
        return self._repo.find_all()

    def get_by_id(self, user_id):
        return self._repo.find_by_id(user_id)
"""

REPO_SRC = """
class UserRepository:
    def find_all(self):
        return []

    def find_by_id(self, user_id):
        return None
"""

MODEL_SRC = """
from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    email: str
"""


def _write(base, rel, content):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


@pytest.fixture()
def mini_project(tmp_path):
    _write(tmp_path, "myapp/controllers/user_controller.py", CONTROLLER_SRC)
    _write(tmp_path, "myapp/services/user_service.py", SERVICE_SRC)
    _write(tmp_path, "myapp/repositories/user_repository.py", REPO_SRC)
    _write(tmp_path, "myapp/models/user.py", MODEL_SRC)
    # Dirs that must be skipped
    (tmp_path / "myapp/__pycache__").mkdir(parents=True, exist_ok=True)
    (tmp_path / "myapp/__pycache__/user_service.cpython-311.pyc").write_bytes(b"\x00\x01")
    (tmp_path / "myapp/.git").mkdir(parents=True, exist_ok=True)
    (tmp_path / "myapp/.git/config").write_text("[core]\n\trepositoryformatversion = 0\n")
    return tmp_path


def _collect_elements(root):
    parser = TreeSitterParser()
    visitor = PythonVisitor()
    elements = []
    for pf in parser.parse_directory(str(root)):
        source = open(pf.file_path, "rb").read()
        elements.extend(visitor.visit(pf.tree, pf.file_path, source))
    return elements


def test_elements_found(mini_project):
    elements = _collect_elements(mini_project)
    assert len(elements) >= 3


def test_layer_presentation(mini_project):
    elements = _collect_elements(mini_project)
    assert any(el.layer == ArchitecturalLayer.PRESENTATION for el in elements)


def test_layer_business(mini_project):
    elements = _collect_elements(mini_project)
    service_el = next((el for el in elements if "UserService" in el.qualified_name), None)
    assert service_el is not None
    assert service_el.layer == ArchitecturalLayer.BUSINESS


def test_layer_data_access(mini_project):
    elements = _collect_elements(mini_project)
    repo_el = next((el for el in elements if "UserRepository" in el.qualified_name), None)
    assert repo_el is not None
    assert repo_el.layer == ArchitecturalLayer.DATA_ACCESS


def test_imports_captured(mini_project):
    elements = _collect_elements(mini_project)
    service_el = next((el for el in elements if "UserService" in el.qualified_name), None)
    assert service_el is not None
    assert any("user_repository" in imp for imp in service_el.imports)


def test_skip_dirs(mini_project):
    elements = _collect_elements(mini_project)
    for el in elements:
        assert "__pycache__" not in el.file_path
        assert ".git" not in el.file_path


def test_only_python_files_parsed(mini_project):
    elements = _collect_elements(mini_project)
    assert len(elements) > 0
    assert all(el.language == "python" for el in elements)
