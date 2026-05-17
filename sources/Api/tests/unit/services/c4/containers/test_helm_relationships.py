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


class TestLibraryChartSkipped:
    """Helm `type: library` charts are not deployable runtimes — they must
    not be registered as C4 containers."""

    def test_library_chart_omitted_from_detection(self, temp_repo):
        chart_dir = temp_repo / "shared-helpers"
        chart_dir.mkdir()
        (chart_dir / "Chart.yaml").write_text(yaml.dump({
            "apiVersion": "v2",
            "name": "shared-helpers",
            "type": "library",
            "version": "0.1.0",
        }))
        result = HelmDetector(temp_repo).detect()
        names = {c["name"] for c in result}
        assert "shared-helpers" not in names

    def test_application_chart_still_detected(self, temp_repo):
        chart_dir = temp_repo / "my-app"
        chart_dir.mkdir()
        (chart_dir / "Chart.yaml").write_text(yaml.dump({
            "apiVersion": "v2",
            "name": "my-app",
            "type": "application",  # explicitly an app
            "version": "1.0.0",
        }))
        result = HelmDetector(temp_repo).detect()
        names = {c["name"] for c in result}
        assert "my-app" in names

    def test_chart_without_type_field_still_detected(self, temp_repo):
        """Most charts omit the `type` field — they default to application."""
        chart_dir = temp_repo / "legacy-svc"
        chart_dir.mkdir()
        (chart_dir / "Chart.yaml").write_text(yaml.dump({
            "apiVersion": "v2",
            "name": "legacy-svc",
            "version": "1.0.0",
        }))
        result = HelmDetector(temp_repo).detect()
        names = {c["name"] for c in result}
        assert "legacy-svc" in names

    def test_mixed_charts_only_library_skipped(self, temp_repo):
        for name, type_ in [("svc", "application"), ("lib", "library")]:
            d = temp_repo / name
            d.mkdir()
            (d / "Chart.yaml").write_text(yaml.dump({
                "apiVersion": "v2",
                "name": name,
                "type": type_,
                "version": "1.0.0",
            }))
        result = HelmDetector(temp_repo).detect()
        names = {c["name"] for c in result}
        assert names == {"svc"}


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


class TestValuesImageInference:
    """Test container_type / protocol inference from image in values.yaml."""

    def test_postgres_image_repository_sets_container_type(self, temp_repo):
        chart_dir = make_chart(temp_repo, "db-svc")
        (chart_dir / "values.yaml").write_text(yaml.dump({
            "image": {"repository": "postgres", "tag": "14"}
        }))
        result = HelmDetector(temp_repo).detect()
        assert "PostgreSQL" in result[0].get("container_type", "")

    def test_redis_image_repository_sets_container_type(self, temp_repo):
        chart_dir = make_chart(temp_repo, "cache-svc")
        (chart_dir / "values.yaml").write_text(yaml.dump({
            "image": {"repository": "redis", "tag": "7"}
        }))
        result = HelmDetector(temp_repo).detect()
        assert "Redis" in result[0].get("container_type", "")

    def test_unknown_image_keeps_helm_deployed_service_type(self, temp_repo):
        chart_dir = make_chart(temp_repo, "custom-svc")
        (chart_dir / "values.yaml").write_text(yaml.dump({
            "image": {"repository": "my-custom-app", "tag": "1.0"}
        }))
        result = HelmDetector(temp_repo).detect()
        assert result[0].get("container_type") == "Helm Deployed Service"


class TestTemplateEnvVarRelationships:
    """Test env var relationship extraction from Deployment templates."""

    def test_deployment_env_vars_produce_relationships(self, temp_repo):
        chart_dir = make_chart(temp_repo, "api")
        templates_dir = chart_dir / "templates"
        templates_dir.mkdir()
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "api"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "api",
                            "image": "my-api:latest",
                            "env": [
                                {"name": "DB_URL", "value": "postgresql://postgres:5432/mydb"}
                            ],
                        }]
                    }
                }
            },
        }
        (templates_dir / "deployment.yaml").write_text(yaml.dump(deployment))
        result = HelmDetector(temp_repo).detect()
        rels = result[0].get("relationships", [])
        assert any(r.get("protocol") == "PostgreSQL" for r in rels)

    def test_statefulset_template_also_scanned(self, temp_repo):
        chart_dir = make_chart(temp_repo, "worker")
        templates_dir = chart_dir / "templates"
        templates_dir.mkdir()
        sts = {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {"name": "worker"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "worker",
                            "image": "my-worker:latest",
                            "env": [
                                {"name": "KAFKA_BROKER", "value": "kafka:9092"}
                            ],
                        }]
                    }
                }
            },
        }
        (templates_dir / "statefulset.yaml").write_text(yaml.dump(sts))
        result = HelmDetector(temp_repo).detect()
        rels = result[0].get("relationships", [])
        assert any(r.get("source") == "helm" for r in rels)

    def test_non_workload_templates_ignored(self, temp_repo):
        chart_dir = make_chart(temp_repo, "svc")
        templates_dir = chart_dir / "templates"
        templates_dir.mkdir()
        service_manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "svc"},
            "spec": {"ports": [{"port": 80}]},
        }
        (templates_dir / "service.yaml").write_text(yaml.dump(service_manifest))
        result = HelmDetector(temp_repo).detect()
        # Should not crash; relationships may be empty
        assert "relationships" in result[0]

    def test_malformed_template_does_not_crash(self, temp_repo):
        chart_dir = make_chart(temp_repo, "broken")
        templates_dir = chart_dir / "templates"
        templates_dir.mkdir()
        (templates_dir / "bad.yaml").write_text(": broken :")
        result = HelmDetector(temp_repo).detect()
        assert len(result) == 1
