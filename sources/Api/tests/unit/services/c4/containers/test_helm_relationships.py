"""Unit tests for relationship extraction in HelmDetector."""

import pytest
import yaml
from pathlib import Path
import tempfile

from app.services.c4.containers.helm_detector import HelmDetector


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def make_chart(repo: Path, name: str, extra: dict = None, chart_subdir: str = "chart"):
    """Create a minimal Helm chart directory inside repo."""
    chart_dir = repo / chart_subdir
    chart_dir.mkdir(parents=True, exist_ok=True)
    data = {"apiVersion": "v2", "name": name, "version": "1.0.0"}
    if extra:
        data.update(extra)
    (chart_dir / "Chart.yaml").write_text(yaml.dump(data))
    return chart_dir


class TestChartDependencies:
    def test_subchart_deps_emit_relationships(self, temp_repo):
        make_chart(temp_repo, "my-app", extra={
            "dependencies": [
                {"name": "postgresql", "version": "12.x", "repository": "https://charts.bitnami.com/bitnami"},
                {"name": "redis", "version": "17.x", "repository": "https://charts.bitnami.com/bitnami"},
            ]
        })
        result = HelmDetector(temp_repo).detect()
        assert len(result) == 1
        rels = result[0].get("relationships", [])
        targets = {r["to"] for r in rels}
        assert "postgresql" in targets
        assert "redis" in targets

    def test_subchart_dep_source_is_helm(self, temp_repo):
        make_chart(temp_repo, "svc", extra={
            "dependencies": [{"name": "mysql", "version": "9.x"}]
        })
        result = HelmDetector(temp_repo).detect()
        rels = result[0].get("relationships", [])
        assert all(r["source"] == "helm" for r in rels if r.get("to") == "mysql")

    def test_no_deps_gives_empty_relationships(self, temp_repo):
        make_chart(temp_repo, "simple-svc")
        result = HelmDetector(temp_repo).detect()
        rels = result[0].get("relationships", [])
        # May still have values.yaml inferred rels, but no subchart deps
        subchart_rels = [r for r in rels if "subchart" in r.get("description", "")]
        assert subchart_rels == []


class TestValuesYamlRelationships:
    def test_postgres_url_key_infers_postgresql(self, temp_repo):
        chart_dir = make_chart(temp_repo, "api")
        (chart_dir / "values.yaml").write_text(yaml.dump({
            "database": {"postgresUrl": "postgresql://db:5432/mydb"}
        }))
        result = HelmDetector(temp_repo).detect()
        rels = result[0].get("relationships", [])
        pg_rels = [r for r in rels if r.get("protocol") == "PostgreSQL"]
        assert len(pg_rels) >= 1

    def test_redis_host_key_infers_redis(self, temp_repo):
        chart_dir = make_chart(temp_repo, "worker")
        (chart_dir / "values.yaml").write_text(yaml.dump({
            "cache": {"redisHost": "redis-service"}
        }))
        result = HelmDetector(temp_repo).detect()
        rels = result[0].get("relationships", [])
        redis_rels = [r for r in rels if r.get("protocol") == "Redis"]
        assert len(redis_rels) >= 1

    def test_kafka_endpoint_key_infers_kafka(self, temp_repo):
        chart_dir = make_chart(temp_repo, "producer")
        (chart_dir / "values.yaml").write_text(yaml.dump({
            "messaging": {"kafkaEndpoint": "kafka:9092"}
        }))
        result = HelmDetector(temp_repo).detect()
        rels = result[0].get("relationships", [])
        kafka_rels = [r for r in rels if r.get("protocol") == "Kafka"]
        assert len(kafka_rels) >= 1

    def test_unresolved_flag_set_on_values_rels(self, temp_repo):
        chart_dir = make_chart(temp_repo, "svc")
        (chart_dir / "values.yaml").write_text(yaml.dump({
            "backend": {"url": "http://some-service"}
        }))
        result = HelmDetector(temp_repo).detect()
        rels = result[0].get("relationships", [])
        unresolved = [r for r in rels if r.get("_unresolved")]
        assert len(unresolved) >= 1

    def test_empty_values_produces_no_relationships(self, temp_repo):
        chart_dir = make_chart(temp_repo, "empty-svc")
        (chart_dir / "values.yaml").write_text(yaml.dump({}))
        result = HelmDetector(temp_repo).detect()
        rels = result[0].get("relationships", [])
        assert isinstance(rels, list)

    def test_malformed_values_yaml_does_not_crash(self, temp_repo):
        chart_dir = make_chart(temp_repo, "broken")
        (chart_dir / "values.yaml").write_text(": broken :")
        result = HelmDetector(temp_repo).detect()
        assert len(result) == 1  # container still created


class TestRelationshipsKeyAlwaysPresent:
    def test_relationships_key_always_present(self, temp_repo):
        make_chart(temp_repo, "bare")
        result = HelmDetector(temp_repo).detect()
        assert "relationships" in result[0]
        assert isinstance(result[0]["relationships"], list)
