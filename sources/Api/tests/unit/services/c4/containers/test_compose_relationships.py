"""Unit tests for relationship extraction in ComposeDetector."""

import pytest
import yaml
from pathlib import Path
import tempfile

from app.services.c4.containers.compose_detector import ComposeDetector


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def write_compose(repo: Path, content: dict, filename: str = "docker-compose.yml"):
    (repo / filename).write_text(yaml.dump(content))


class TestDependsOnRelationships:
    def test_list_format_depends_on(self, temp_repo):
        write_compose(temp_repo, {
            "services": {
                "api": {"image": "api:latest", "depends_on": ["db", "redis"]},
                "db": {"image": "postgres:14"},
                "redis": {"image": "redis:7"},
            }
        })
        result = ComposeDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api")
        rels = api.get("relationships", [])
        targets = {r["to"] for r in rels}
        assert "db" in targets
        assert "redis" in targets

    def test_dict_format_depends_on(self, temp_repo):
        """depends_on in dict form (service_healthy condition) must be parsed correctly."""
        write_compose(temp_repo, {
            "services": {
                "api": {
                    "image": "api:latest",
                    "depends_on": {"db": {"condition": "service_healthy"}},
                },
                "db": {"image": "postgres:14"},
            }
        })
        result = ComposeDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api")
        assert any(r["to"] == "db" for r in api.get("relationships", []))

    def test_dict_format_updates_dependencies_internal(self, temp_repo):
        """dependencies_internal must include entries from dict-form depends_on."""
        write_compose(temp_repo, {
            "services": {
                "svc": {
                    "image": "svc:latest",
                    "depends_on": {"backend": {"condition": "service_started"}},
                },
                "backend": {"image": "backend:latest"},
            }
        })
        result = ComposeDetector(temp_repo).detect()
        svc = next(c for c in result if c["name"] == "svc")
        assert "backend" in svc.get("dependencies_internal", [])

    def test_self_reference_excluded(self, temp_repo):
        """A service must not emit a relationship to itself."""
        write_compose(temp_repo, {
            "services": {
                "api": {"image": "api:latest", "depends_on": ["api"]},
            }
        })
        result = ComposeDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api")
        assert not any(r["to"] == "api" for r in api.get("relationships", []))

    def test_relationship_source_is_compose(self, temp_repo):
        write_compose(temp_repo, {
            "services": {
                "web": {"image": "web:latest", "depends_on": ["api"]},
                "api": {"image": "api:latest"},
            }
        })
        result = ComposeDetector(temp_repo).detect()
        web = next(c for c in result if c["name"] == "web")
        rels = web.get("relationships", [])
        assert all(r["source"] == "compose" for r in rels)


class TestLinksRelationships:
    def test_plain_link(self, temp_repo):
        write_compose(temp_repo, {
            "services": {
                "app": {"image": "app:latest", "links": ["db"]},
                "db": {"image": "postgres:14"},
            }
        })
        result = ComposeDetector(temp_repo).detect()
        app = next(c for c in result if c["name"] == "app")
        assert any(r["to"] == "db" for r in app.get("relationships", []))

    def test_link_with_alias(self, temp_repo):
        """links: ["service:alias"] — target is the service name, not the alias."""
        write_compose(temp_repo, {
            "services": {
                "app": {"image": "app:latest", "links": ["db:database"]},
                "db": {"image": "postgres:14"},
            }
        })
        result = ComposeDetector(temp_repo).detect()
        app = next(c for c in result if c["name"] == "app")
        assert any(r["to"] == "db" for r in app.get("relationships", []))


class TestSharedVolumeRelationships:
    def test_shared_named_volume(self, temp_repo):
        write_compose(temp_repo, {
            "services": {
                "writer": {"image": "writer:latest", "volumes": ["data:/data"]},
                "reader": {"image": "reader:latest", "volumes": ["data:/data:ro"]},
            },
            "volumes": {"data": None},
        })
        result = ComposeDetector(temp_repo).detect()
        writer = next(c for c in result if c["name"] == "writer")
        reader = next(c for c in result if c["name"] == "reader")

        writer_rels = writer.get("relationships", [])
        reader_rels = reader.get("relationships", [])

        all_rels = writer_rels + reader_rels
        vol_rels = [r for r in all_rels if r["type"] == "shares-volume"]
        assert len(vol_rels) >= 1
        participants = {r["from"] for r in vol_rels} | {r["to"] for r in vol_rels}
        assert "writer" in participants
        assert "reader" in participants

    def test_bind_mount_not_treated_as_shared_volume(self, temp_repo):
        write_compose(temp_repo, {
            "services": {
                "a": {"image": "a:latest", "volumes": ["./local:/data"]},
                "b": {"image": "b:latest", "volumes": ["./local:/data"]},
            }
        })
        result = ComposeDetector(temp_repo).detect()
        all_rels = [r for c in result for r in c.get("relationships", [])]
        assert not any(r["type"] == "shares-volume" for r in all_rels)


class TestEventBusProtocol:
    def test_kafka_image_sets_publishes_to(self, temp_repo):
        write_compose(temp_repo, {
            "services": {
                "app": {"image": "app:latest", "depends_on": ["kafka"]},
                "kafka": {"image": "confluentinc/cp-kafka:7.0"},
            }
        })
        result = ComposeDetector(temp_repo).detect()
        app = next(c for c in result if c["name"] == "app")
        kafka_rels = [r for r in app.get("relationships", []) if r["to"] == "kafka"]
        assert len(kafka_rels) == 1
        assert kafka_rels[0]["protocol"] == "Kafka"
        assert kafka_rels[0]["type"] == "publishes-to"

    def test_rabbitmq_image_sets_amqp(self, temp_repo):
        write_compose(temp_repo, {
            "services": {
                "worker": {"image": "worker:latest", "depends_on": ["rabbit"]},
                "rabbit": {"image": "rabbitmq:3-management"},
            }
        })
        result = ComposeDetector(temp_repo).detect()
        worker = next(c for c in result if c["name"] == "worker")
        rel = next((r for r in worker.get("relationships", []) if r["to"] == "rabbit"), None)
        assert rel is not None
        assert rel["protocol"] == "AMQP"


class TestMalformedCompose:
    def test_malformed_yaml_returns_empty_list(self, temp_repo):
        (temp_repo / "docker-compose.yml").write_text("invalid: yaml: [unclosed")
        result = ComposeDetector(temp_repo).detect()
        assert isinstance(result, list)

    def test_no_relationships_key_when_parse_fails(self, temp_repo):
        (temp_repo / "docker-compose.yml").write_text(": broken :")
        result = ComposeDetector(temp_repo).detect()
        assert result == []
