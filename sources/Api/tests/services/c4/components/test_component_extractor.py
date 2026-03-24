import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.c4.components.component_extractor import ComponentExtractor
from app.services.c4.components.models import ComponentObject

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


def _write(base: Path, rel: str, content: str) -> None:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


@pytest.fixture()
def mini_project(tmp_path):
    _write(tmp_path, "myapp/controllers/user_controller.py", CONTROLLER_SRC)
    _write(tmp_path, "myapp/services/user_service.py", SERVICE_SRC)
    _write(tmp_path, "myapp/repositories/user_repository.py", REPO_SRC)
    return tmp_path


def test_extract_returns_components_no_llm(mini_project):
    result = ComponentExtractor().extract(str(mini_project))
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(c, ComponentObject) for c in result)


def test_extract_deduplicates_elements(mini_project):
    result = ComponentExtractor().extract(str(mini_project))
    all_qnames = [
        el.qualified_name
        for comp in result
        for el in comp.code_elements
    ]
    assert len(all_qnames) == len(set(all_qnames)), "Duplicate qualified_names found across components"


def test_extract_empty_dir_returns_empty(tmp_path):
    result = ComponentExtractor().extract(str(tmp_path))
    assert result == []


def test_extract_with_mock_llm(mini_project):
    mock_llm = MagicMock()
    mock_llm.classify_elements.side_effect = lambda els: els
    mock_llm.group_elements.return_value = []
    mock_llm.identify_components_and_contracts_from_source.return_value = ([], [])

    result = ComponentExtractor(llm_service=mock_llm).extract(str(mini_project))

    mock_llm.identify_components_and_contracts_from_source.assert_called()
    assert isinstance(result, list)


def test_extract_logs_phases(mini_project, caplog):
    with caplog.at_level(logging.INFO, logger="app.services.c4.components.component_extractor"):
        ComponentExtractor().extract(str(mini_project))

    messages = caplog.text
    assert "Phase A" in messages
    assert "Phase B" in messages
    assert "Phase C" in messages
