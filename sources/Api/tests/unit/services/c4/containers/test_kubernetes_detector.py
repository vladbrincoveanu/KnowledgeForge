"""Unit tests for KubernetesDetector - C4 Level 2 container extraction from K8s manifests."""

import tempfile

import pytest
import yaml
from pathlib import Path

from app.services.c4.containers.kubernetes_detector import KubernetesDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data))


# ---------------------------------------------------------------------------
# Shared manifest data
# ---------------------------------------------------------------------------

DEPLOYMENT_DOC = {
    "apiVersion": "apps/v1",
    "kind": "Deployment",
    "metadata": {"name": "api-service", "namespace": "default"},
    "spec": {
        "template": {
            "spec": {
                "containers": [
                    {
                        "name": "api",
                        "image": "my-org/api-service:1.0",
                        "ports": [{"containerPort": 8080}],
                        "env": [{"name": "DB_URL", "value": "postgresql://postgres:5432/mydb"}],
                        "readinessProbe": {"httpGet": {"path": "/health", "port": 8080}},
                    }
                ],
                "initContainers": [
                    {"name": "db-migrator", "image": "my-org/migrator:1.0"}
                ],
            }
        }
    },
}

STATEFULSET_KAFKA_DOC = {
    "apiVersion": "apps/v1",
    "kind": "StatefulSet",
    "metadata": {"name": "kafka", "namespace": "default"},
    "spec": {
        "template": {
            "spec": {
                "containers": [
                    {
                        "name": "kafka",
                        "image": "confluentinc/cp-kafka:7.0",
                        "ports": [{"containerPort": 9092}],
                    }
                ]
            }
        }
    },
}

STATEFULSET_MONGO_DOC = {
    "apiVersion": "apps/v1",
    "kind": "StatefulSet",
    "metadata": {"name": "mongodb"},
    "spec": {
        "template": {
            "spec": {
                "containers": [
                    {
                        "name": "mongo",
                        "image": "mongo:6",
                        "ports": [{"containerPort": 27017}],
                    }
                ]
            }
        }
    },
}

DAEMONSET_DOC = {
    "apiVersion": "apps/v1",
    "kind": "DaemonSet",
    "metadata": {"name": "log-collector"},
    "spec": {
        "template": {
            "spec": {
                "containers": [{"name": "fluentd", "image": "fluent/fluentd:v1.16"}]
            }
        }
    },
}

JOB_DOC = {
    "apiVersion": "batch/v1",
    "kind": "Job",
    "metadata": {"name": "db-seed"},
    "spec": {
        "template": {
            "spec": {
                "containers": [{"name": "seeder", "image": "my-org/seeder:1.0"}]
            }
        }
    },
}

CRONJOB_DOC = {
    "apiVersion": "batch/v1",
    "kind": "CronJob",
    "metadata": {"name": "cleanup-job"},
    "spec": {
        "schedule": "0 * * * *",
        "jobTemplate": {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"name": "cleaner", "image": "my-org/cleaner:1.0"}]
                    }
                }
            }
        },
    },
}


# ---------------------------------------------------------------------------
# can_detect()
# ---------------------------------------------------------------------------

class TestKubernetesDetectorCanDetect:

    def test_can_detect_true_with_kustomization_yaml(self, temp_repo):
        (temp_repo / "kustomization.yaml").write_text("resources: []")
        assert KubernetesDetector(temp_repo).can_detect() is True

    def test_can_detect_true_with_kustomization_yml(self, temp_repo):
        (temp_repo / "kustomization.yml").write_text("resources: []")
        assert KubernetesDetector(temp_repo).can_detect() is True

    def test_can_detect_true_with_deployment_yaml(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        assert KubernetesDetector(temp_repo).can_detect() is True

    def test_can_detect_true_with_statefulset(self, temp_repo):
        write_yaml(temp_repo / "sts.yaml", STATEFULSET_KAFKA_DOC)
        assert KubernetesDetector(temp_repo).can_detect() is True

    def test_can_detect_false_when_no_k8s_files(self, temp_repo):
        (temp_repo / "README.md").write_text("hello")
        assert KubernetesDetector(temp_repo).can_detect() is False

    def test_can_detect_false_with_non_k8s_yaml(self, temp_repo):
        (temp_repo / "config.yaml").write_text("key: value\nother: data\n")
        assert KubernetesDetector(temp_repo).can_detect() is False


# ---------------------------------------------------------------------------
# detect() — core extraction
# ---------------------------------------------------------------------------

class TestKubernetesDetectorDetect:

    def test_detect_returns_list(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        assert isinstance(KubernetesDetector(temp_repo).detect(), list)

    def test_detect_empty_when_no_manifests(self, temp_repo):
        assert KubernetesDetector(temp_repo).detect() == []

    def test_detect_deployment_extracts_name(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        assert any(c["name"] == "api-service" for c in result)

    def test_detect_returns_c4_level_2(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        for c in KubernetesDetector(temp_repo).detect():
            assert c["c4_level"] == 2
            assert c["type"] == "container"

    def test_detect_runtime_environment_is_kubernetes(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        for c in KubernetesDetector(temp_repo).detect():
            assert c["runtime_environment"] == "Kubernetes"

    def test_detect_has_required_fields(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        assert result
        required = {
            "name", "type", "c4_level", "container_type", "technology",
            "protocol", "runtime_environment", "deployment", "relationships",
            "health_endpoint", "dependencies_internal",
        }
        for c in result:
            for field in required:
                assert field in c, f"Missing field '{field}' in {c['name']}"

    def test_detect_protocol_inferred_from_port_8080(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api-service")
        assert api["protocol"] == "HTTP"

    def test_detect_health_endpoint_from_readiness_probe(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api-service")
        assert api["health_endpoint"] == "/health"

    def test_detect_liveness_probe_used_as_fallback(self, temp_repo):
        doc = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "svc"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "app",
                                "image": "myapp:1.0",
                                "livenessProbe": {"httpGet": {"path": "/ping", "port": 8080}},
                            }
                        ]
                    }
                }
            },
        }
        write_yaml(temp_repo / "deploy.yaml", doc)
        result = KubernetesDetector(temp_repo).detect()
        svc = next(c for c in result if c["name"] == "svc")
        assert svc["health_endpoint"] == "/ping"


# ---------------------------------------------------------------------------
# StatefulSet extraction
# ---------------------------------------------------------------------------

class TestKubernetesDetectorStatefulSet:

    def test_kafka_classified_as_message_broker(self, temp_repo):
        write_yaml(temp_repo / "kafka.yaml", STATEFULSET_KAFKA_DOC)
        result = KubernetesDetector(temp_repo).detect()
        kafka = next((c for c in result if c["name"] == "kafka"), None)
        assert kafka is not None
        assert kafka["container_type"] == "Message Broker"

    def test_kafka_technology_label(self, temp_repo):
        write_yaml(temp_repo / "kafka.yaml", STATEFULSET_KAFKA_DOC)
        result = KubernetesDetector(temp_repo).detect()
        kafka = next(c for c in result if c["name"] == "kafka")
        assert kafka["technology"] == "Kafka"

    def test_kafka_protocol_from_port_9092(self, temp_repo):
        write_yaml(temp_repo / "kafka.yaml", STATEFULSET_KAFKA_DOC)
        result = KubernetesDetector(temp_repo).detect()
        kafka = next(c for c in result if c["name"] == "kafka")
        assert kafka["protocol"] == "Kafka"

    def test_mongo_classified_as_database(self, temp_repo):
        write_yaml(temp_repo / "mongo.yaml", STATEFULSET_MONGO_DOC)
        result = KubernetesDetector(temp_repo).detect()
        mongo = next((c for c in result if c["name"] == "mongodb"), None)
        assert mongo is not None
        assert mongo["container_type"] == "Database"

    def test_mongo_protocol_from_port_27017(self, temp_repo):
        write_yaml(temp_repo / "mongo.yaml", STATEFULSET_MONGO_DOC)
        result = KubernetesDetector(temp_repo).detect()
        mongo = next(c for c in result if c["name"] == "mongodb")
        assert mongo["protocol"] == "MongoDB"


# ---------------------------------------------------------------------------
# Kind-based type overrides
# ---------------------------------------------------------------------------

class TestKubernetesDetectorKindTypes:

    def test_daemonset_classified_as_system_agent(self, temp_repo):
        write_yaml(temp_repo / "ds.yaml", DAEMONSET_DOC)
        result = KubernetesDetector(temp_repo).detect()
        ds = next((c for c in result if c["name"] == "log-collector"), None)
        assert ds is not None
        assert ds["container_type"] == "System Agent"

    def test_job_classified_as_batch_job(self, temp_repo):
        write_yaml(temp_repo / "job.yaml", JOB_DOC)
        result = KubernetesDetector(temp_repo).detect()
        job = next((c for c in result if c["name"] == "db-seed"), None)
        assert job is not None
        assert job["container_type"] == "Batch Job"

    def test_cronjob_classified_as_scheduled_job(self, temp_repo):
        write_yaml(temp_repo / "cron.yaml", CRONJOB_DOC)
        result = KubernetesDetector(temp_repo).detect()
        cron = next((c for c in result if c["name"] == "cleanup-job"), None)
        assert cron is not None
        assert cron["container_type"] == "Scheduled Job"


# ---------------------------------------------------------------------------
# initContainers skipped
# ---------------------------------------------------------------------------

class TestKubernetesDetectorInitContainersSkipped:

    def test_init_container_not_extracted_as_separate_container(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        names = [c["name"] for c in result]
        assert "db-migrator" not in names
        assert "api-service" in names

    def test_workload_with_only_init_containers_skipped(self, temp_repo):
        doc = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "init-only"},
            "spec": {
                "template": {
                    "spec": {
                        "initContainers": [{"name": "init", "image": "busybox:latest"}]
                        # no "containers" key
                    }
                }
            },
        }
        write_yaml(temp_repo / "deploy.yaml", doc)
        result = KubernetesDetector(temp_repo).detect()
        assert not any(c["name"] == "init-only" for c in result)


# ---------------------------------------------------------------------------
# Multi-document YAML
# ---------------------------------------------------------------------------

class TestKubernetesDetectorMultiDocYaml:

    def test_multi_doc_yaml_extracts_all_workloads(self, temp_repo):
        multi = "---\n" + yaml.dump(DEPLOYMENT_DOC) + "\n---\n" + yaml.dump(STATEFULSET_MONGO_DOC)
        (temp_repo / "all.yaml").write_text(multi)
        result = KubernetesDetector(temp_repo).detect()
        names = [c["name"] for c in result]
        assert "api-service" in names
        assert "mongodb" in names

    def test_multi_doc_non_workload_docs_ignored(self, temp_repo):
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "my-config"},
            "data": {"key": "value"},
        }
        multi = "---\n" + yaml.dump(DEPLOYMENT_DOC) + "\n---\n" + yaml.dump(configmap)
        (temp_repo / "mixed.yaml").write_text(multi)
        result = KubernetesDetector(temp_repo).detect()
        names = [c["name"] for c in result]
        assert "my-config" not in names
        assert "api-service" in names


# ---------------------------------------------------------------------------
# Kustomize resource following
# ---------------------------------------------------------------------------

class TestKubernetesDetectorKustomize:

    def test_kustomize_referenced_file_marked_as_kustomize(self, temp_repo):
        deploy_path = temp_repo / "deployment.yaml"
        write_yaml(deploy_path, DEPLOYMENT_DOC)
        (temp_repo / "kustomization.yaml").write_text(yaml.dump({"resources": ["deployment.yaml"]}))
        result = KubernetesDetector(temp_repo).detect()
        api = next((c for c in result if c["name"] == "api-service"), None)
        assert api is not None
        assert api["deployment"] == "Kustomize"

    def test_unreferenced_file_marked_as_manifest(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api-service")
        assert api["deployment"] == "Manifest"

    def test_kustomize_with_empty_resources_still_processes_yaml(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        (temp_repo / "kustomization.yaml").write_text(yaml.dump({"resources": []}))
        result = KubernetesDetector(temp_repo).detect()
        # File exists but is not referenced → Manifest
        api = next((c for c in result if c["name"] == "api-service"), None)
        assert api is not None
        assert api["deployment"] == "Manifest"


# ---------------------------------------------------------------------------
# Helm directory exclusion
# ---------------------------------------------------------------------------

class TestKubernetesDetectorHelmExclusion:

    def test_templates_inside_helm_chart_excluded(self, temp_repo):
        chart_dir = temp_repo / "mychart"
        templates_dir = chart_dir / "templates"
        templates_dir.mkdir(parents=True)
        (chart_dir / "Chart.yaml").write_text("name: mychart\nversion: 1.0.0\n")
        write_yaml(templates_dir / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        assert not any(c["name"] == "api-service" for c in result)

    def test_manifest_outside_helm_dir_included(self, temp_repo):
        chart_dir = temp_repo / "mychart"
        chart_dir.mkdir()
        (chart_dir / "Chart.yaml").write_text("name: mychart\nversion: 1.0.0\n")
        # Sibling directory — not inside a Helm chart
        k8s_dir = temp_repo / "k8s"
        k8s_dir.mkdir()
        write_yaml(k8s_dir / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        assert any(c["name"] == "api-service" for c in result)


# ---------------------------------------------------------------------------
# Malformed YAML handling
# ---------------------------------------------------------------------------

class TestKubernetesDetectorMalformedYaml:

    def test_malformed_yaml_does_not_crash(self, temp_repo):
        (temp_repo / "bad.yaml").write_text("invalid: yaml: [unclosed\n{broken")
        result = KubernetesDetector(temp_repo).detect()
        assert isinstance(result, list)

    def test_empty_yaml_file_handled(self, temp_repo):
        (temp_repo / "empty.yaml").write_text("")
        result = KubernetesDetector(temp_repo).detect()
        assert result == []

    def test_workload_without_containers_key_skipped(self, temp_repo):
        doc = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "no-containers"},
            "spec": {"template": {"spec": {}}},
        }
        write_yaml(temp_repo / "deploy.yaml", doc)
        result = KubernetesDetector(temp_repo).detect()
        assert not any(c["name"] == "no-containers" for c in result)

    def test_workload_without_name_skipped(self, temp_repo):
        doc = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {},
            "spec": {
                "template": {
                    "spec": {"containers": [{"name": "app", "image": "myapp:1.0"}]}
                }
            },
        }
        write_yaml(temp_repo / "deploy.yaml", doc)
        result = KubernetesDetector(temp_repo).detect()
        assert result == []


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestKubernetesDetectorDeduplication:

    def test_same_workload_in_two_files_deduplicated(self, temp_repo):
        write_yaml(temp_repo / "deploy1.yaml", DEPLOYMENT_DOC)
        write_yaml(temp_repo / "deploy2.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        assert len([c for c in result if c["name"] == "api-service"]) == 1


# ---------------------------------------------------------------------------
# Env var relationships
# ---------------------------------------------------------------------------

class TestKubernetesDetectorEnvVarRelationships:

    def test_db_url_env_var_extracts_relationship(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api-service")
        rels = api.get("relationships", [])
        assert len(rels) > 0

    def test_relationship_target_is_postgres_host(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api-service")
        rels = api.get("relationships", [])
        assert any(r.get("to") == "postgres" for r in rels)

    def test_relationship_protocol_is_postgresql(self, temp_repo):
        write_yaml(temp_repo / "deployment.yaml", DEPLOYMENT_DOC)
        result = KubernetesDetector(temp_repo).detect()
        api = next(c for c in result if c["name"] == "api-service")
        db_rel = next(r for r in api["relationships"] if r.get("to") == "postgres")
        assert db_rel["protocol"] == "PostgreSQL"

    def test_multi_container_pod_env_vars_all_extracted(self, temp_repo):
        doc = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "multi-svc"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "app",
                                "image": "myapp:1.0",
                                "env": [
                                    {"name": "DB_HOST", "value": "postgres:5432"},
                                    {"name": "CACHE_HOST", "value": "redis:6379"},
                                ],
                            },
                            {
                                "name": "sidecar",
                                "image": "sidecar:1.0",
                                "env": [{"name": "BROKER_URL", "value": "kafka:9092"}],
                            },
                        ]
                    }
                }
            },
        }
        write_yaml(temp_repo / "deploy.yaml", doc)
        result = KubernetesDetector(temp_repo).detect()
        svc = next(c for c in result if c["name"] == "multi-svc")
        targets = {r["to"] for r in svc["relationships"]}
        assert "postgres" in targets
        assert "redis" in targets
        assert "kafka" in targets
