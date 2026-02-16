"""Unit tests for ComposeDetector - C4 Level 2 container extraction from docker-compose files."""

import pytest
import yaml
from pathlib import Path
import tempfile

from app.services.c4.containers.compose_detector import ComposeDetector


@pytest.fixture
def temp_repo():
    """Create a temporary repository directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def simple_compose_repo(temp_repo):
    """Repo with a simple docker-compose.yml."""
    content = {
        "version": "3.8",
        "services": {
            "api": {
                "build": ".",
                "image": "my-api:latest",
                "ports": ["8000:8000"],
                "depends_on": ["db", "redis"],
                "environment": {"DATABASE_URL": "postgresql://db:5432/mydb"},
            },
            "db": {
                "image": "postgres:14",
                "ports": ["5432:5432"],
            },
            "redis": {
                "image": "redis:7",
                "ports": ["6379:6379"],
            },
        },
    }
    (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
    return temp_repo


@pytest.fixture
def multi_compose_repo(temp_repo):
    """Repo with multiple docker-compose files."""
    base = {
        "version": "3.8",
        "services": {
            "web": {"image": "nginx:latest", "ports": ["80:80"]},
        },
    }
    override = {
        "version": "3.8",
        "services": {
            "worker": {"image": "my-worker:latest"},
        },
    }
    (temp_repo / "docker-compose.yml").write_text(yaml.dump(base))
    (temp_repo / "docker-compose.override.yml").write_text(yaml.dump(override))
    return temp_repo


class TestComposeDetectorCanDetect:
    """Test can_detect() detection logic."""

    def test_can_detect_returns_true_when_compose_exists(self, simple_compose_repo):
        detector = ComposeDetector(simple_compose_repo)
        assert detector.can_detect() is True

    def test_can_detect_returns_false_when_no_compose(self, temp_repo):
        detector = ComposeDetector(temp_repo)
        assert detector.can_detect() is False

    def test_can_detect_finds_yaml_extension(self, temp_repo):
        (temp_repo / "docker-compose.yaml").write_text("version: '3'\nservices: {}")
        detector = ComposeDetector(temp_repo)
        assert detector.can_detect() is True


class TestComposeDetectorDetect:
    """Test detect() container extraction."""

    def test_detect_returns_list(self, simple_compose_repo):
        detector = ComposeDetector(simple_compose_repo)
        result = detector.detect()
        assert isinstance(result, list)

    def test_detect_finds_all_services(self, simple_compose_repo):
        detector = ComposeDetector(simple_compose_repo)
        result = detector.detect()
        names = [c["name"] for c in result]
        assert "api" in names
        assert "db" in names
        assert "redis" in names

    def test_detect_returns_c4_level_2(self, simple_compose_repo):
        detector = ComposeDetector(simple_compose_repo)
        result = detector.detect()
        for container in result:
            assert container["c4_level"] == 2

    def test_detect_container_has_required_fields(self, simple_compose_repo):
        detector = ComposeDetector(simple_compose_repo)
        result = detector.detect()
        assert len(result) > 0
        for container in result:
            assert "name" in container
            assert "type" in container
            assert container["type"] == "container"

    def test_detect_api_has_dependencies(self, simple_compose_repo):
        detector = ComposeDetector(simple_compose_repo)
        result = detector.detect()
        api = next((c for c in result if c["name"] == "api"), None)
        assert api is not None
        # Should have internal dependencies from depends_on
        deps = api.get("dependencies_internal", [])
        assert "db" in deps or "redis" in deps

    def test_detect_empty_when_no_compose(self, temp_repo):
        detector = ComposeDetector(temp_repo)
        result = detector.detect()
        assert result == []

    def test_detect_handles_malformed_compose(self, temp_repo):
        """Should not crash on malformed YAML."""
        (temp_repo / "docker-compose.yml").write_text("invalid: yaml: [unclosed")
        detector = ComposeDetector(temp_repo)
        result = detector.detect()
        assert isinstance(result, list)


class TestComposeDetectorContainerTypes:
    """Test container type classification."""

    def test_database_service_classified_correctly(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {
                "postgres": {"image": "postgres:14"},
                "mysql": {"image": "mysql:8"},
            },
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        detector = ComposeDetector(temp_repo)
        result = detector.detect()

        db_containers = [
            c for c in result
            if "Database" in c.get("container_type", "") or "database" in c.get("container_type", "").lower()
        ]
        # Postgres/MySQL should be classified as databases
        assert len(db_containers) >= 1

    def test_cache_service_classified_correctly(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {
                "redis": {"image": "redis:7"},
            },
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        detector = ComposeDetector(temp_repo)
        result = detector.detect()
        assert len(result) == 1
        # Redis should be classified as cache or message queue
        container_type = result[0].get("container_type", "").lower()
        assert any(k in container_type for k in ("cache", "redis", "message", "queue", "service"))
