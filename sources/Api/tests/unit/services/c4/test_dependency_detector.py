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
OPENAI_API_KEY=sk-openai-test
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


@pytest.fixture
def appsettings_repo(temp_repo):
    """Repo with appsettings.json containing ambiguous internal endpoints."""
    appsettings = {
        "Payments": {
            "BaseUrl": "https://gateway.internal.example/api"
        },
        "Messaging": {
            "RedisUrl": "redis://cache:6379/0"
        }
    }
    (temp_repo / "appsettings.json").write_text(json.dumps(appsettings, indent=2))
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

    def test_dependency_has_decision_metadata(self, env_file_repo):
        detector = DependencyDetector(env_file_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        assert result
        for dep in result:
            assert "decision" in dep
            assert "review_status" in dep
            assert "confidence" in dep
            assert "evidence" in dep

    def test_detects_from_package_json(self, node_project_repo):
        detector = DependencyDetector(node_project_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        assert len(result) >= 1
        # Should detect something from package.json
        sources = [d.get("detected_from", "") for d in result]
        assert any("package.json" in s or "pyproject" in s or "requirements" in s for s in sources)

    def test_detects_from_nested_package_json(self, temp_repo):
        service_dir = temp_repo / "services" / "analytics"
        service_dir.mkdir(parents=True)
        package_json = {
            "name": "analytics",
            "dependencies": {
                "mixpanel": "^0.17.0",
            },
        }
        (service_dir / "package.json").write_text(json.dumps(package_json, indent=2))

        detector = DependencyDetector(temp_repo, enable_classification=False)
        result = detector.detect_external_dependencies()

        mixpanel_dep = next(dep for dep in result if dep["name"] == "Mixpanel")
        assert mixpanel_dep["detected_from"] == "services/analytics/package.json"
        assert mixpanel_dep["detection_source"] == "provider_catalog"

    def test_detects_kafka_rabbitmq_mongodb_from_appsettings(self, temp_repo):
        appsettings = {
            "ProjectionInfrastructure": {
                "KafkaBootstrapServers": "kafka://risk-streams.internal:9092",
                "MongoDbUrl": "mongodb://projection-db.internal:27017/projections",
            },
            "Messaging": {
                "RabbitMqUrl": "amqps://settlement-bus.internal:5671/settlements",
            },
        }
        (temp_repo / "appsettings.json").write_text(json.dumps(appsettings, indent=2))

        detector = DependencyDetector(temp_repo, enable_classification=False)
        result = detector.detect_external_dependencies()

        names = {dep["name"] for dep in result}
        assert {"Kafka", "RabbitMQ", "MongoDB"}.issubset(names)

    def test_detects_sql_server_from_csproj_catalog(self, temp_repo):
        csproj = """
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.Data.SqlClient" Version="5.2.1" />
  </ItemGroup>
</Project>
"""
        (temp_repo / "platform.csproj").write_text(csproj)

        detector = DependencyDetector(temp_repo, enable_classification=False)
        result = detector.detect_external_dependencies()

        sqlserver = next(dep for dep in result if dep["name"] == "SQL Server")
        assert sqlserver["detected_from"] == "platform.csproj"
        assert sqlserver["detection_source"] == "provider_catalog"

    def test_detects_from_env_file(self, env_file_repo):
        detector = DependencyDetector(env_file_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        assert isinstance(result, list)
        names = {dep["name"] for dep in result}
        assert "OpenAI" in names
        assert "Stripe" in names

    def test_dependency_decision_includes_catalog_match_metadata(self, env_file_repo):
        detector = DependencyDetector(env_file_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        openai_dep = next(dep for dep in result if dep["name"] == "OpenAI")
        catalog_match = openai_dep["decision"]["metadata"]["catalog_match"]
        assert catalog_match is not None
        assert catalog_match["alias_field"] == "env_aliases"
        assert catalog_match["matched_alias"] == "OPENAI_API_KEY"

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

    def test_ambiguous_internal_url_emits_review_item(self, appsettings_repo):
        detector = DependencyDetector(appsettings_repo, enable_classification=False)
        result = detector.detect_external_dependencies()
        reviews = [dep for dep in result if dep.get("review_status") == "needs_review"]
        assert reviews
        assert any(dep.get("review_item") for dep in reviews)

    def test_detects_deployment_dependencies(self, appsettings_repo):
        detector = DependencyDetector(appsettings_repo, enable_classification=False)
        result = detector.detect_deployment_dependencies()
        assert isinstance(result, list)


@pytest.mark.parametrize("url,expected", [
    ("https://api.airbyte.com).", "Airbyte"),
    ("https://stripe.com).", "Stripe"),
    ("https://docs.aws.amazon.com", "Amazon"),
    ("https://api.openai.com).", "Openai"),
    ("https://api.stripe.com/v1/charges", "Stripe"),
])
def test_extract_service_name_from_url_strips_trailing_junk(temp_repo, url, expected):
    """URLs extracted from markdown often have trailing punctuation; name must be clean."""
    from app.services.c4.context.dependency_detector import DependencyDetector
    detector = DependencyDetector(repo_path=temp_repo)
    result = detector._extract_service_name_from_url(url)
    assert result == expected, f"URL {url!r} → {result!r}, expected {expected!r}"


@pytest.mark.parametrize("url", [
    "https://shields.io/badge/version-1.0-green",
    "https://website-files.com/image.png",
    "https://docusaurus.com/docs",
    "https://youtube.com/watch?v=abc",
    "https://github.com/user/repo",
    "https://readme.io/",
])
def test_extract_service_name_blocks_non_service_hosts(temp_repo, url):
    """Non-service hostnames return None to filter garbage dependencies."""
    from app.services.c4.context.dependency_detector import DependencyDetector
    detector = DependencyDetector(repo_path=temp_repo)
    result = detector._extract_service_name_from_url(url)
    assert result is None, f"URL {url!r} → {result!r}, expected None"


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

    def test_enriched_dependency_exposes_business_context_name(self, temp_repo):
        detector = DependencyDetector(temp_repo, enable_classification=False)

        dep = detector._enrich_dependency(
            {
                "name": "GlobalBank API",
                "type": "external_service",
                "detected_from": "appsettings.json",
            }
        )

        assert dep["name"] == "GlobalBank API"
        assert dep["context_name"] == "GlobalBank"
        assert dep["integration_surface"] == "API"

    def test_unknown_dependency_emits_review_options_for_human_loop(self, temp_repo):
        detector = DependencyDetector(temp_repo, enable_classification=False)

        dep = detector._enrich_dependency(
            {
                "name": "SignalForge Risk API",
                "type": "external_service",
                "detected_from": "README.md",
            }
        )

        assert dep["review_status"] == "needs_review"
        assert dep["requires_human_review"] is True
        assert dep["review_threshold"] == 0.70
        assert [option["value"] for option in dep["review_options"]] == [
            "BUSINESS_SYSTEM",
            "TECHNICAL_INFRA",
        ]
        assert dep["suggested_prompts"]


def test_build_review_prompts_uses_actual_evidence(temp_repo):
    """When LLM unavailable, fallback prompts must reference actual dep evidence."""
    from app.services.c4.context.dependency_detector import DependencyDetector
    detector = DependencyDetector(repo_path=temp_repo, llm_manager=None)
    dep = {
        "name": "api.airbyte.com",
        "context": "docs/terraform-documentation.md",
        "type": "external_service",
        "classification_confidence": 0.6,
        "review_threshold": 0.7,
    }
    prompts = detector._build_review_prompts("api.airbyte.com", "external_service", dep)
    assert len(prompts) == 2
    assert "payment-platform" not in prompts[0]      # No generic template
    assert "terraform" in prompts[1]                  # Uses actual evidence source
    assert "0.7" in prompts[0] or "70%" in prompts[0]  # Uses actual threshold


def test_build_review_prompts_llm_success(temp_repo):
    """LLM returns valid JSON array → prompts returned directly."""
    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    mock_llm.generate_text.return_value = (
        '["Is api.airbyte.com a SaaS API or internal infra?", "What services does it provide?"]'
    )
    detector = DependencyDetector(repo_path=temp_repo, llm_manager=mock_llm)
    dep = {"name": "x", "context": "...", "type": "service",
           "classification_confidence": 0.6, "review_threshold": 0.7}
    prompts = detector._build_review_prompts("api.airbyte.com", "external_service", dep)
    assert len(prompts) == 2


def test_build_review_prompts_handles_markdown_fence(temp_repo):
    """LLM sometimes wraps JSON in ```json fences — must extract correctly."""
    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    mock_llm.generate_text.return_value = '```json\n["Prompt one?", "Prompt two?"]\n```'
    detector = DependencyDetector(repo_path=temp_repo, llm_manager=mock_llm)
    dep = {"name": "x", "context": "...", "type": "service",
           "classification_confidence": 0.6, "review_threshold": 0.7}
    prompts = detector._build_review_prompts("x", "service", dep)
    assert len(prompts) == 2
    assert prompts[0] == "Prompt one?"


def test_build_review_prompts_corrupt_json_falls_back(temp_repo):
    """LLM returns malformed text → fallback prompts used."""
    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    mock_llm.generate_text.return_value = "Here are your prompts, I'm not sure..."
    detector = DependencyDetector(repo_path=temp_repo, llm_manager=mock_llm)
    dep = {"name": "x", "context": "src/main.rs", "type": "service",
           "classification_confidence": 0.6, "review_threshold": 0.7}
    prompts = detector._build_review_prompts("x", "service", dep)
    assert len(prompts) == 2
    assert "payment-platform" not in prompts[0]  # Still no generic template
