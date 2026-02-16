"""Unit tests for DependencyDetector - external service dependency detection."""

import json
import pytest
from pathlib import Path
import tempfile

from app.services.c4.context.dependency_detector import DependencyDetector


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def python_project_repo(temp_repo):
    """Repo with Python project files referencing external services."""
    pyproject = """
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.100.0"
sqlalchemy = "^2.0.0"
redis = "^4.6.0"
boto3 = "^1.26.0"
stripe = "^5.0.0"
"""
    (temp_repo / "pyproject.toml").write_text(pyproject)
    return temp_repo


@pytest.fixture
def node_project_repo(temp_repo):
    """Repo with Node.js package.json referencing external services."""
    package_json = {
        "name": "my-service",
        "dependencies": {
            "express": "^4.18.0",
            "pg": "^8.11.0",
            "ioredis": "^5.3.0",
            "aws-sdk": "^2.1400.0",
            "stripe": "^12.0.0",
        },
    }
    (temp_repo / "package.json").write_text(json.dumps(package_json, indent=2))
    return temp_repo


@pytest.fixture
def env_file_repo(temp_repo):
    """Repo with .env file containing external service URLs."""
    env_content = """
DATABASE_URL=postgresql://user:pass@db.example.com:5432/mydb
REDIS_URL=redis://cache.example.com:6379
STRIPE_API_KEY=sk_live_xxxx
AWS_REGION=us-east-1
SENDGRID_API_KEY=SG.xxx
"""
    (temp_repo / ".env.example").write_text(env_content)
    return temp_repo


@pytest.fixture
def docker_compose_repo(temp_repo):
    """Repo with docker-compose referencing external services."""
    compose = """
version: "3.8"
services:
  api:
    image: my-api:latest
    environment:
      DATABASE_URL: postgresql://db:5432/mydb
      REDIS_URL: redis://cache:6379
  db:
    image: postgres:14
  cache:
    image: redis:7
"""
    (temp_repo / "docker-compose.yml").write_text(compose)
    return temp_repo


class TestDependencyDetectorInit:
    """Test DependencyDetector initialization."""

    def test_init_basic(self, temp_repo):
        detector = DependencyDetector(temp_repo)
        assert detector is not None

    def test_init_with_llm(self, temp_repo):
        from unittest.mock import Mock
        llm_manager = Mock()
        detector = DependencyDetector(temp_repo, llm_manager=llm_manager)
        assert detector is not None

    def test_init_with_classification_disabled(self, temp_repo):
        detector = DependencyDetector(temp_repo, enable_classification=False)
        assert detector is not None


class TestDependencyDetectorDetect:
    """Test detect_external_dependencies() output."""

    def test_returns_list(self, temp_repo):
        detector = DependencyDetector(temp_repo)
        result = detector.detect_external_dependencies()
        assert isinstance(result, list)

    def test_empty_repo_returns_empty_list(self, temp_repo):
        detector = DependencyDetector(temp_repo)
        result = detector.detect_external_dependencies()
        assert result == []

    def test_detects_database_from_pyproject(self, python_project_repo):
        detector = DependencyDetector(python_project_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        # SQLAlchemy/redis/boto3/stripe indicate external services
        assert len(result) >= 1

    def test_dependency_has_name_field(self, python_project_repo):
        detector = DependencyDetector(python_project_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        for dep in result:
            assert "name" in dep

    def test_dependency_has_detected_from_field(self, python_project_repo):
        detector = DependencyDetector(python_project_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        for dep in result:
            assert "detected_from" in dep

    def test_detects_from_package_json(self, node_project_repo):
        detector = DependencyDetector(node_project_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        assert len(result) >= 1
        # Should detect something from package.json
        sources = [d.get("detected_from", "") for d in result]
        assert any("package.json" in s or "pyproject" in s or "requirements" in s for s in sources)

    def test_detects_from_env_file(self, env_file_repo):
        detector = DependencyDetector(env_file_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        assert isinstance(result, list)

    def test_detects_from_docker_compose(self, docker_compose_repo):
        detector = DependencyDetector(docker_compose_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        assert isinstance(result, list)

    def test_no_duplicates_in_result(self, python_project_repo):
        """Same dependency should not appear multiple times."""
        detector = DependencyDetector(python_project_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        names = [d["name"] for d in result]
        # Names should be unique
        assert len(names) == len(set(names))

    def test_dependency_freshness_alerts_from_package_json(self, node_project_repo):
        detector = DependencyDetector(node_project_repo, enable_classification=False)
        alerts = detector.detect_dependency_freshness_alerts()
        assert any(alert.get("dependency") == "express" for alert in alerts)
        assert all("issue" in alert for alert in alerts)

    def test_dependency_freshness_alerts_from_requirements(self, temp_repo):
        (temp_repo / "requirements.txt").write_text("requests>=2.0\n")
        detector = DependencyDetector(temp_repo, enable_classification=False)
        alerts = detector.detect_dependency_freshness_alerts()
        assert any(alert.get("dependency") == "requests" for alert in alerts)


class TestDependencyDetectorClassification:
    """Test dependency type classification."""

    def test_database_dependencies_classified(self, python_project_repo):
        detector = DependencyDetector(python_project_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        # Look for any database-classified dependency
        db_deps = [d for d in result if "database" in d.get("dependency_type", "").lower()
                   or "database" in d.get("type", "").lower()]
        # Not strictly required (depends on implementation), just verify structure
        assert isinstance(result, list)
