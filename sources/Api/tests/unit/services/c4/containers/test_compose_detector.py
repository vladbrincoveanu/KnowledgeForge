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


class TestComposeDetectorRecursion:
    """Compose detector must find files in subdirectories. Monorepos commonly
    place service-local compose files at services/<svc>/docker-compose.yml in
    addition to (or instead of) a top-level orchestration compose."""

    def test_finds_compose_in_subdirectory(self, temp_repo):
        sub = temp_repo / "services" / "api"
        sub.mkdir(parents=True)
        (sub / "docker-compose.yml").write_text(yaml.dump({
            "version": "3.8",
            "services": {"api": {"image": "myapi:latest", "ports": ["3000:3000"]}},
        }))
        detector = ComposeDetector(temp_repo)
        assert detector.can_detect() is True
        result = detector.detect()
        names = {c["name"] for c in result}
        assert "api" in names

    def test_finds_compose_in_root_and_subdirectory(self, temp_repo):
        (temp_repo / "docker-compose.yml").write_text(yaml.dump({
            "version": "3.8",
            "services": {"postgres": {"image": "postgres:15"}},
        }))
        sub = temp_repo / "services" / "worker"
        sub.mkdir(parents=True)
        (sub / "docker-compose.yml").write_text(yaml.dump({
            "version": "3.8",
            "services": {"worker": {"image": "myworker:latest"}},
        }))
        result = ComposeDetector(temp_repo).detect()
        names = {c["name"] for c in result}
        assert names == {"postgres", "worker"}

    def test_path_field_includes_subdirectory(self, temp_repo):
        sub = temp_repo / "services" / "api"
        sub.mkdir(parents=True)
        (sub / "docker-compose.yml").write_text(yaml.dump({
            "version": "3.8",
            "services": {"api": {"image": "myapi:latest"}},
        }))
        result = ComposeDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api")
        # path should reflect the actual compose file location, not just the basename
        assert "services/api" in api["path"]


class TestComposeDetectorExclusions:
    """Compose files inside vendored / test / build directories must be ignored —
    they are typically example fixtures or third-party dependencies, not real
    services of the system being analysed."""

    @pytest.mark.parametrize("excluded_dir", [
        "node_modules", "vendor", ".git", "dist", "build", "target",
        "tests", "test", "__pycache__", ".venv", "venv",
    ])
    def test_compose_in_excluded_dirs_is_ignored(self, temp_repo, excluded_dir):
        excluded = temp_repo / excluded_dir / "some-pkg"
        excluded.mkdir(parents=True)
        (excluded / "docker-compose.yml").write_text(yaml.dump({
            "version": "3.8",
            "services": {"vendored": {"image": "junk:latest"}},
        }))
        detector = ComposeDetector(temp_repo)
        # No real compose at root, so can_detect should be False
        assert detector.can_detect() is False, (
            f"compose file inside {excluded_dir}/ must not satisfy can_detect"
        )
        assert detector.detect() == []

    def test_real_service_alongside_excluded_compose(self, temp_repo):
        # Real top-level compose
        (temp_repo / "docker-compose.yml").write_text(yaml.dump({
            "version": "3.8",
            "services": {"api": {"image": "api:latest"}},
        }))
        # Junk inside node_modules — must be filtered out
        nm = temp_repo / "node_modules" / "some-pkg"
        nm.mkdir(parents=True)
        (nm / "docker-compose.yml").write_text(yaml.dump({
            "version": "3.8",
            "services": {"vendored-junk": {"image": "junk:latest"}},
        }))
        result = ComposeDetector(temp_repo).detect()
        names = {c["name"] for c in result}
        assert names == {"api"}
        assert "vendored-junk" not in names


class TestComposeDetectorProtocolInference:
    """Test protocol inference from image and ports."""

    def test_postgres_service_gets_postgresql_protocol(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {"db": {"image": "postgres:14", "ports": ["5432:5432"]}},
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        result = ComposeDetector(temp_repo).detect()
        db = next(c for c in result if c["name"] == "db")
        assert db["protocol"] == "PostgreSQL"

    def test_redis_service_gets_redis_protocol(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {"cache": {"image": "redis:7", "ports": ["6379:6379"]}},
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        result = ComposeDetector(temp_repo).detect()
        cache = next(c for c in result if c["name"] == "cache")
        assert cache["protocol"] == "Redis"

    def test_kafka_service_gets_kafka_protocol(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {"broker": {"image": "confluentinc/cp-kafka:7.0"}},
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        result = ComposeDetector(temp_repo).detect()
        broker = next(c for c in result if c["name"] == "broker")
        assert broker["protocol"] == "Kafka"

    def test_unknown_image_falls_back_to_http(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {"api": {"image": "my-custom-api:latest"}},
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        result = ComposeDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api")
        assert api["protocol"] == "HTTP"


class TestComposeDetectorEnvVarRelationships:
    """Test env var relationship extraction for compose services."""

    def test_env_dict_with_db_url_produces_relationship(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {
                "api": {
                    "image": "my-api:latest",
                    "environment": {"DATABASE_URL": "postgresql://db:5432/mydb"},
                },
                "db": {"image": "postgres:14"},
            },
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        result = ComposeDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api")
        rels = api.get("relationships", [])
        assert any(r.get("protocol") == "PostgreSQL" for r in rels)

    def test_env_list_format_produces_relationship(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {
                "worker": {
                    "image": "my-worker:latest",
                    "environment": ["REDIS_URL=redis://cache:6379/0"],
                },
                "cache": {"image": "redis:7"},
            },
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        result = ComposeDetector(temp_repo).detect()
        worker = next(c for c in result if c["name"] == "worker")
        rels = worker.get("relationships", [])
        assert any(r.get("protocol") == "Redis" for r in rels)

    def test_env_var_relationships_marked_unresolved(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {
                "svc": {
                    "image": "my-svc:latest",
                    "environment": {"KAFKA_BROKER": "kafka:9092"},
                },
            },
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        result = ComposeDetector(temp_repo).detect()
        svc = next(c for c in result if c["name"] == "svc")
        rels = svc.get("relationships", [])
        assert any(r.get("_unresolved") for r in rels)


class TestComposeDetectorLinksProtocol:
    """Test that links protocol is inferred from target image."""

    def test_link_to_kafka_gets_kafka_protocol(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {
                "consumer": {
                    "image": "my-consumer:latest",
                    "links": ["broker"],
                },
                "broker": {"image": "confluentinc/cp-kafka:7.0"},
            },
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        result = ComposeDetector(temp_repo).detect()
        consumer = next(c for c in result if c["name"] == "consumer")
        rels = consumer.get("relationships", [])
        link_rels = [r for r in rels if r.get("source") == "compose" and "links" in r.get("description", "")]
        assert any(r.get("protocol") == "Kafka" for r in link_rels)

    def test_link_to_unknown_image_defaults_to_http(self, temp_repo):
        content = {
            "version": "3.8",
            "services": {
                "frontend": {
                    "image": "my-frontend:latest",
                    "links": ["backend"],
                },
                "backend": {"image": "my-backend:latest"},
            },
        }
        (temp_repo / "docker-compose.yml").write_text(yaml.dump(content))
        result = ComposeDetector(temp_repo).detect()
        frontend = next(c for c in result if c["name"] == "frontend")
        rels = frontend.get("relationships", [])
        link_rels = [r for r in rels if r.get("to") == "backend"]
        assert any(r.get("protocol") == "HTTP" for r in link_rels)


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
