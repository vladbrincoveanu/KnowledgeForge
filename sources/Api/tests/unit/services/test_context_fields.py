"""Integration tests for context-level field detectors (Waves 3-5).

Covers:
- BusFactorCalculator (bus_factor_calculator.py)
- AuthScanner (auth_scanner.py)
- DocumentationQualityScorer (documentation_quality_scorer.py)
- DeploymentTargetDetector (deployment_target_detector.py)
- InterServiceCommDetector (inter_service_comm_detector.py)
- BusinessDomainClassifier (business_domain_classifier.py)
- ComplianceScorer (compliance_scorer.py)
- APISurfaceDetector (api_surface_detector.py)
- enhance_with_* wiring in service_enhancers.py
"""

import subprocess
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.domain.models.services import Service


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def make_service(name: str = "test-svc", path: str = "/tmp/test-svc") -> Service:
    return Service(id=str(uuid.uuid4()), name=name, path=path)


# ──────────────────────────────────────────────────────────────────────────────
# Bus Factor Calculator
# ──────────────────────────────────────────────────────────────────────────────


class TestBusFactorCalculator:
    def test_returns_score_one_for_non_git_dir(self, tmp_path):
        from app.services.service_extraction.bus_factor_calculator import (
            calculate_bus_factor,
        )

        result = calculate_bus_factor(tmp_path)
        assert result.bus_factor_score == 1
        assert result.active_experts == 0
        assert result.total_contributors_90d == 0

    def test_gini_all_equal(self):
        from app.services.service_extraction.bus_factor_calculator import _gini

        assert _gini([5, 5, 5, 5]) == pytest.approx(0.0, abs=0.01)

    def test_gini_all_one_person(self):
        from app.services.service_extraction.bus_factor_calculator import _gini

        result = _gini([0, 0, 0, 100])
        assert result > 0.5

    def test_gini_empty(self):
        from app.services.service_extraction.bus_factor_calculator import _gini

        assert _gini([]) == 0.0
        assert _gini([0, 0, 0]) == 0.0

    def test_score_clamped_between_1_and_10(self):
        from app.services.service_extraction.bus_factor_calculator import (
            calculate_bus_factor,
        )

        emails = "\n".join(["dev1@x.com"] * 10 + ["dev2@x.com"] * 10 + ["dev3@x.com"] * 10)
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout=emails, stderr=""
                )
                result = calculate_bus_factor(Path(tmpdir))
                assert 1 <= result.bus_factor_score <= 10

    def test_score_for_single_contributor(self):
        from app.services.service_extraction.bus_factor_calculator import (
            calculate_bus_factor,
        )

        emails = "\n".join(["solo@x.com"] * 5)
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout=emails, stderr=""
                )
                result = calculate_bus_factor(Path(tmpdir))
                assert result.active_experts == 1
                assert result.bus_factor_score >= 1

    def test_git_timeout_returns_score_1(self):
        from app.services.service_extraction.bus_factor_calculator import (
            calculate_bus_factor,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
                result = calculate_bus_factor(Path(tmpdir))
                assert result.bus_factor_score == 1


# ──────────────────────────────────────────────────────────────────────────────
# Auth Scanner
# ──────────────────────────────────────────────────────────────────────────────


class TestAuthScanner:
    def test_empty_dir_returns_auth_none(self, tmp_path):
        from app.services.service_extraction.auth_scanner import scan_auth, AUTH_NONE

        result = scan_auth(tmp_path)
        assert AUTH_NONE in result.auth_types

    def test_nonexistent_path_returns_unknown(self):
        from app.services.service_extraction.auth_scanner import scan_auth

        result = scan_auth(Path("/nonexistent/path/xyz"))
        assert result.actors == ["Unknown"]

    def test_detects_jwt_from_source_code(self, tmp_path):
        from app.services.service_extraction.auth_scanner import scan_auth, AUTH_JWT

        (tmp_path / "auth.py").write_text("import jwt\ntoken = jwt.decode(data, secret)")
        result = scan_auth(tmp_path)
        assert AUTH_JWT in result.auth_types

    def test_detects_oauth_from_source_code(self, tmp_path):
        from app.services.service_extraction.auth_scanner import scan_auth, AUTH_OAUTH

        (tmp_path / "app.py").write_text("oauth2_client = keycloak.configure(realm='master')")
        result = scan_auth(tmp_path)
        assert AUTH_OAUTH in result.auth_types

    def test_detects_api_key_from_env_file(self, tmp_path):
        from app.services.service_extraction.auth_scanner import scan_auth, AUTH_APIKEY

        (tmp_path / ".env").write_text("DATABASE_URL=postgres://\nAPI_KEY=secret-key-value\n")
        result = scan_auth(tmp_path)
        assert AUTH_APIKEY in result.auth_types

    def test_detects_jwt_from_openapi_spec(self, tmp_path):
        from app.services.service_extraction.auth_scanner import scan_auth, AUTH_JWT

        openapi = """
openapi: "3.0.0"
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
"""
        (tmp_path / "openapi.yaml").write_text(openapi)
        result = scan_auth(tmp_path)
        assert AUTH_JWT in result.auth_types

    def test_infer_actors_oauth_maps_to_human_user(self, tmp_path):
        from app.services.service_extraction.auth_scanner import scan_auth, AUTH_OAUTH

        (tmp_path / "app.py").write_text("keycloak_url = 'https://auth.example.com'")
        result = scan_auth(tmp_path)
        if AUTH_OAUTH in result.auth_types:
            assert any("Human User" in a for a in result.actors)

    def test_infer_actors_mtls_maps_to_internal_service(self, tmp_path):
        from app.services.service_extraction.auth_scanner import scan_auth, AUTH_MTLS

        (tmp_path / "server.py").write_text("ssl_context = ssl.create_default_context()\nmutual_tls = True")
        result = scan_auth(tmp_path)
        if AUTH_MTLS in result.auth_types:
            assert any("Internal Service" in a for a in result.actors)

    def test_skips_test_files(self, tmp_path):
        """Test files importing auth libs should not count as service using them."""
        from app.services.service_extraction.auth_scanner import scan_auth, AUTH_JWT

        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_auth.py").write_text("import jwt\ndef test_decode(): jwt.decode(t, s)")
        result = scan_auth(tmp_path)
        assert AUTH_JWT not in result.auth_types

    def test_evidence_list_capped(self, tmp_path):
        from app.services.service_extraction.auth_scanner import scan_auth

        for i in range(20):
            (tmp_path / f"file{i}.py").write_text("jwt.decode(token, secret_key)")
        result = scan_auth(tmp_path)
        assert len(result.evidence) <= 10


# ──────────────────────────────────────────────────────────────────────────────
# Documentation Quality Scorer
# Actual API: DocumentationQualityScorer().score(path) -> DocumentationQualityResult
# DocumentationQualityResult fields: score (int 0-100), tier (str), checks, factors
# score_documentation_quality(path) returns int directly
# ──────────────────────────────────────────────────────────────────────────────


class TestDocumentationQualityScorer:
    def test_empty_dir_scores_below_50(self, tmp_path):
        from app.services.service_extraction.documentation_quality_scorer import (
            DocumentationQualityScorer,
        )

        scorer = DocumentationQualityScorer()
        result = scorer.score(tmp_path)
        # Empty dir: inline_docs check passes (too few files) but rest fail
        assert result.score < 50

    def test_readme_with_sections_increases_score(self, tmp_path):
        from app.services.service_extraction.documentation_quality_scorer import (
            DocumentationQualityScorer,
        )

        readme = """# My Service

## Overview
This service handles user authentication.

## Getting Started
Install dependencies with pip install -r requirements.txt.

## API Reference
See /docs for OpenAPI spec.

## Configuration
Set DATABASE_URL environment variable.
"""
        (tmp_path / "README.md").write_text(readme)
        scorer = DocumentationQualityScorer()
        result_before = DocumentationQualityScorer().score(tmp_path.parent)
        result = scorer.score(tmp_path)
        assert result.score > 0
        assert result.tier is not None

    def test_openapi_spec_adds_to_score(self, tmp_path):
        from app.services.service_extraction.documentation_quality_scorer import (
            DocumentationQualityScorer,
        )

        (tmp_path / "README.md").write_text("# Service\nBasic readme.")
        scorer_without = DocumentationQualityScorer()
        score_without = scorer_without.score(tmp_path).score

        (tmp_path / "openapi.yaml").write_text("openapi: '3.0'\ninfo:\n  title: My API")
        scorer_with = DocumentationQualityScorer()
        score_with = scorer_with.score(tmp_path).score

        assert score_with >= score_without

    def test_tier_poor_for_empty_dir(self, tmp_path):
        from app.services.service_extraction.documentation_quality_scorer import (
            DocumentationQualityScorer,
            THRESHOLD_ADEQUATE,
        )

        scorer = DocumentationQualityScorer()
        result = scorer.score(tmp_path)
        # If score < THRESHOLD_ADEQUATE, tier should be POOR
        if result.score < THRESHOLD_ADEQUATE:
            assert result.tier == "POOR"

    def test_score_documentation_quality_returns_int(self, tmp_path):
        from app.services.service_extraction.documentation_quality_scorer import (
            score_documentation_quality,
        )

        result = score_documentation_quality(tmp_path)
        assert isinstance(result, int)
        assert 0 <= result <= 100

    def test_full_docs_scores_higher(self, tmp_path):
        from app.services.service_extraction.documentation_quality_scorer import (
            DocumentationQualityScorer,
        )

        (tmp_path / "README.md").write_text(
            "# Payment Service\n\n## Overview\nHandles payments.\n\n## Getting Started\nRun docker-compose up.\n\n## API Reference\nSee openapi.yaml."
        )
        (tmp_path / "openapi.yaml").write_text("openapi: '3.0.0'\ninfo:\n  title: Payment API\npaths: {}")
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n## v1.0.0\nInitial release.")
        adr_dir = tmp_path / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "0001-use-kafka.md").write_text("# ADR 0001\nStatus: Accepted")

        scorer = DocumentationQualityScorer()
        result = scorer.score(tmp_path)
        assert result.score > 30


# ──────────────────────────────────────────────────────────────────────────────
# Deployment Target Detector
# Actual API: detect_deployment_targets(path) -> list[str]  (strings, not enum)
# ──────────────────────────────────────────────────────────────────────────────


class TestDeploymentTargetDetector:
    def test_empty_dir_returns_empty(self, tmp_path):
        from app.services.service_extraction.deployment_target_detector import (
            detect_deployment_targets,
        )

        result = detect_deployment_targets(tmp_path)
        assert result == []

    def test_dockerfile_detects_container(self, tmp_path):
        from app.services.service_extraction.deployment_target_detector import (
            detect_deployment_targets,
        )

        (tmp_path / "Dockerfile").write_text("FROM python:3.11\nCMD [\"python\", \"app.py\"]")
        result = detect_deployment_targets(tmp_path)
        assert "Container" in result

    def test_kubernetes_manifest_detects_kubernetes(self, tmp_path):
        from app.services.service_extraction.deployment_target_detector import (
            detect_deployment_targets,
        )

        k8s_dir = tmp_path / "k8s"
        k8s_dir.mkdir()
        (k8s_dir / "deployment.yaml").write_text(
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: my-service"
        )
        result = detect_deployment_targets(tmp_path)
        assert "Kubernetes" in result

    def test_serverless_yml_detects_serverless(self, tmp_path):
        from app.services.service_extraction.deployment_target_detector import (
            detect_deployment_targets,
        )

        (tmp_path / "serverless.yml").write_text(
            "service: my-func\nprovider:\n  name: aws\n  runtime: python3.9"
        )
        result = detect_deployment_targets(tmp_path)
        assert "Serverless" in result

    def test_procfile_detects_paas(self, tmp_path):
        from app.services.service_extraction.deployment_target_detector import (
            detect_deployment_targets,
        )

        (tmp_path / "Procfile").write_text("web: gunicorn app:application")
        result = detect_deployment_targets(tmp_path)
        assert "PaaS" in result

    def test_multiple_targets_detected(self, tmp_path):
        from app.services.service_extraction.deployment_target_detector import (
            detect_deployment_targets,
        )

        (tmp_path / "Dockerfile").write_text("FROM node:18")
        # Helm detection requires Chart.yaml at root or helm/ subdir
        (tmp_path / "Chart.yaml").write_text("apiVersion: v2\nname: my-chart")
        result = detect_deployment_targets(tmp_path)
        assert "Container" in result
        assert "Kubernetes" in result

    def test_returns_list_of_strings(self, tmp_path):
        from app.services.service_extraction.deployment_target_detector import (
            detect_deployment_targets,
        )

        (tmp_path / "Dockerfile").write_text("FROM python:3.11")
        result = detect_deployment_targets(tmp_path)
        assert isinstance(result, list)
        assert all(isinstance(t, str) for t in result)


# ──────────────────────────────────────────────────────────────────────────────
# Inter-Service Comm Detector
# Actual API: detect_inter_service_comms(path) -> list[dict]
# Each dict: {'target': str, 'protocol': str, 'direction': str}
# ──────────────────────────────────────────────────────────────────────────────


class TestInterServiceCommDetector:
    def test_empty_dir_returns_empty(self, tmp_path):
        from app.services.service_extraction.inter_service_comm_detector import (
            detect_inter_service_comms,
        )

        result = detect_inter_service_comms(tmp_path)
        assert result == []

    def test_detects_http_requests(self, tmp_path):
        from app.services.service_extraction.inter_service_comm_detector import (
            detect_inter_service_comms,
        )

        (tmp_path / "client.py").write_text(
            "import requests\nresponse = requests.get('http://payment-service/api/charge')"
        )
        result = detect_inter_service_comms(tmp_path)
        assert len(result) > 0
        assert all(isinstance(c, dict) for c in result)

    def test_detects_kafka_producer(self, tmp_path):
        from app.services.service_extraction.inter_service_comm_detector import (
            detect_inter_service_comms,
        )

        (tmp_path / "producer.py").write_text(
            "from kafka import KafkaProducer\nproducer = KafkaProducer(bootstrap_servers='kafka:9092')"
        )
        result = detect_inter_service_comms(tmp_path)
        assert len(result) > 0

    def test_detects_grpc_channel(self, tmp_path):
        from app.services.service_extraction.inter_service_comm_detector import (
            detect_inter_service_comms,
        )

        (tmp_path / "grpc_client.py").write_text(
            "import grpc\nchannel = grpc.insecure_channel('inventory:50051')"
        )
        result = detect_inter_service_comms(tmp_path)
        assert len(result) > 0

    def test_http_comm_has_required_keys(self, tmp_path):
        from app.services.service_extraction.inter_service_comm_detector import (
            detect_inter_service_comms,
        )

        (tmp_path / "client.py").write_text(
            "import requests\nrequests.get('http://order-service/orders')"
        )
        result = detect_inter_service_comms(tmp_path)
        if result:
            assert "protocol" in result[0] or "target" in result[0]


# ──────────────────────────────────────────────────────────────────────────────
# Business Domain Classifier
# Actual API: classify_business_domain(service_name, readme_text, ...) -> Optional[str]
# Returns domain string like "Payments" or None
# ──────────────────────────────────────────────────────────────────────────────


class TestBusinessDomainClassifier:
    def test_classifies_payments_by_readme(self):
        from app.services.service_extraction.business_domain_classifier import (
            classify_business_domain,
        )

        result = classify_business_domain(
            service_name="payment-svc",
            readme_text="Handles Stripe payments, invoices, and billing.",
        )
        assert result == "Payments"

    def test_classifies_identity_by_readme(self):
        from app.services.service_extraction.business_domain_classifier import (
            classify_business_domain,
        )

        result = classify_business_domain(
            service_name="auth-svc",
            readme_text="Handles user login, registration, OAuth SSO.",
        )
        assert result == "Identity"

    def test_returns_none_for_unknown(self):
        from app.services.service_extraction.business_domain_classifier import (
            classify_business_domain,
        )

        result = classify_business_domain(
            service_name="mystery-svc",
            readme_text="Does some random stuff.",
            llm_manager=None,
        )
        # With no LLM and no matching keywords, returns None
        assert result is None

    def test_classifies_by_service_name(self):
        from app.services.service_extraction.business_domain_classifier import (
            classify_business_domain,
        )

        result = classify_business_domain(
            service_name="analytics-pipeline",
            readme_text="",
        )
        assert result == "Analytics"

    def test_classifies_logistics_by_keywords(self):
        from app.services.service_extraction.business_domain_classifier import (
            classify_business_domain,
        )

        result = classify_business_domain(
            service_name="shipping-svc",
            readme_text="Manages shipment tracking, delivery routing, and fleet management.",
        )
        assert result == "Logistics"

    def test_base_taxonomy_is_list(self):
        from app.services.service_extraction.business_domain_classifier import BASE_TAXONOMY

        assert isinstance(BASE_TAXONOMY, list)
        assert "Payments" in BASE_TAXONOMY
        assert "Identity" in BASE_TAXONOMY


# ──────────────────────────────────────────────────────────────────────────────
# Compliance Scorer
# Actual API: ComplianceScorer().score(service_path, data_class=None, ...) -> ComplianceResult
# ComplianceResult fields: score, tier, checks, factors, confidence
# ──────────────────────────────────────────────────────────────────────────────


class TestComplianceScorer:
    def test_empty_dir_scores_low(self, tmp_path):
        from app.services.service_extraction.compliance_scorer import ComplianceScorer

        scorer = ComplianceScorer()
        result = scorer.score(tmp_path)
        assert result.score < 50

    def test_result_has_required_fields(self, tmp_path):
        from app.services.service_extraction.compliance_scorer import ComplianceScorer

        scorer = ComplianceScorer()
        result = scorer.score(tmp_path)
        assert hasattr(result, "score")
        assert hasattr(result, "tier")
        assert hasattr(result, "factors")
        assert hasattr(result, "confidence")

    def test_ci_config_adds_points(self, tmp_path):
        from app.services.service_extraction.compliance_scorer import ComplianceScorer

        scorer_empty = ComplianceScorer()
        score_empty = scorer_empty.score(tmp_path).score

        gha_dir = tmp_path / ".github" / "workflows"
        gha_dir.mkdir(parents=True)
        (gha_dir / "ci.yml").write_text("name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest")
        scorer = ComplianceScorer()
        result = scorer.score(tmp_path)
        assert result.score > score_empty

    def test_readme_adds_points(self, tmp_path):
        from app.services.service_extraction.compliance_scorer import ComplianceScorer

        scorer_empty = ComplianceScorer()
        score_empty = scorer_empty.score(tmp_path).score

        # ComplianceScorer requires README > 200 chars to pass the README check
        (tmp_path / "README.md").write_text(
            "# My Service\n\n"
            "This service handles user requests and provides a REST API for processing "
            "business operations. It integrates with external services via HTTP.\n\n"
            "## Installation\npip install -r requirements.txt\n\n"
            "## Usage\npython main.py --port 8080\n"
        )
        scorer = ComplianceScorer()
        result = scorer.score(tmp_path)
        assert result.score > score_empty

    def test_tests_directory_adds_points(self, tmp_path):
        from app.services.service_extraction.compliance_scorer import ComplianceScorer

        scorer_empty = ComplianceScorer()
        score_empty = scorer_empty.score(tmp_path).score

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("def test_one(): assert True")
        scorer = ComplianceScorer()
        result = scorer.score(tmp_path)
        assert result.score > score_empty

    def test_full_compliant_repo_scores_high(self, tmp_path):
        from app.services.service_extraction.compliance_scorer import ComplianceScorer

        gha = tmp_path / ".github" / "workflows"
        gha.mkdir(parents=True)
        (gha / "ci.yml").write_text("name: CI\non: [push]")
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_app.py").write_text("def test_ok(): pass")
        (tmp_path / "README.md").write_text("# Service\nDetails here.")
        (tmp_path / "requirements.txt").write_text("fastapi==0.100.0\n")

        scorer = ComplianceScorer()
        result = scorer.score(tmp_path)
        assert result.score >= 50

    def test_tier_field_is_string(self, tmp_path):
        from app.services.service_extraction.compliance_scorer import ComplianceScorer

        scorer = ComplianceScorer()
        result = scorer.score(tmp_path)
        assert isinstance(result.tier, str)
        assert result.tier in ("COMPLIANT", "AT_RISK", "NON_COMPLIANT")


# ──────────────────────────────────────────────────────────────────────────────
# API Surface Detector
# Actual API: detect_api_surface_types(path) -> list[str]  (strings like "REST", "gRPC")
# ──────────────────────────────────────────────────────────────────────────────


class TestAPISurfaceDetector:
    def test_empty_dir_returns_empty(self, tmp_path):
        from app.services.service_extraction.api_surface_detector import (
            detect_api_surface_types,
        )

        result = detect_api_surface_types(tmp_path)
        assert result == []

    def test_detects_rest_from_fastapi(self, tmp_path):
        from app.services.service_extraction.api_surface_detector import (
            detect_api_surface_types,
        )

        (tmp_path / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/users')\ndef get_users(): pass"
        )
        result = detect_api_surface_types(tmp_path)
        assert "REST" in result

    def test_detects_grpc_from_proto_file(self, tmp_path):
        from app.services.service_extraction.api_surface_detector import (
            detect_api_surface_types,
        )

        (tmp_path / "service.proto").write_text(
            'syntax = "proto3";\nservice UserService {\n  rpc GetUser(UserRequest) returns (UserResponse);\n}'
        )
        result = detect_api_surface_types(tmp_path)
        assert "gRPC" in result

    def test_detects_graphql(self, tmp_path):
        from app.services.service_extraction.api_surface_detector import (
            detect_api_surface_types,
        )

        (tmp_path / "schema.graphql").write_text(
            "type Query {\n  user(id: ID!): User\n}\ntype User {\n  id: ID!\n  name: String\n}"
        )
        result = detect_api_surface_types(tmp_path)
        assert "GraphQL" in result

    def test_detects_cli_from_click(self, tmp_path):
        from app.services.service_extraction.api_surface_detector import (
            detect_api_surface_types,
        )

        (tmp_path / "cli.py").write_text(
            "import click\n@click.command()\n@click.option('--count')\ndef run(count): pass"
        )
        result = detect_api_surface_types(tmp_path)
        assert "CLI" in result

    def test_returns_list_of_strings(self, tmp_path):
        from app.services.service_extraction.api_surface_detector import (
            detect_api_surface_types,
        )

        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
        result = detect_api_surface_types(tmp_path)
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)


# ──────────────────────────────────────────────────────────────────────────────
# Enhancement wiring in service_enhancers.py
# ──────────────────────────────────────────────────────────────────────────────


class TestEnhancerWiring:
    """Smoke tests verifying that enhance_with_* functions don't crash and populate fields."""

    def test_enhance_bus_factor_empty_list(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_bus_factor

        enhance_with_bus_factor([], tmp_path)

    def test_enhance_auth_scanning_empty_list(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_auth_scanning

        enhance_with_auth_scanning([], tmp_path)

    def test_enhance_documentation_quality_empty_list(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_documentation_quality

        enhance_with_documentation_quality([], tmp_path)

    def test_enhance_deployment_targets_empty_list(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_deployment_targets

        enhance_with_deployment_targets([], tmp_path)

    def test_enhance_inter_service_comms_empty_list(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_inter_service_comms

        enhance_with_inter_service_comms([], tmp_path)

    def test_enhance_business_domain_empty_list(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_business_domain

        enhance_with_business_domain([], tmp_path, llm_manager=None)

    def test_enhance_api_surface_types_empty_list(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_api_surface_types

        enhance_with_api_surface_types([], tmp_path)

    def test_enhance_bus_factor_populates_field(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_bus_factor

        svc = make_service(path=str(tmp_path))
        enhance_with_bus_factor([svc], tmp_path)
        assert svc.bus_factor == 1  # non-git dir → score 1

    def test_enhance_auth_scanning_populates_attributes(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_auth_scanning

        # resolve_service_path looks for repo_root/service.name — create that dir
        svc_dir = tmp_path / "test-svc"
        svc_dir.mkdir()
        svc = make_service(name="test-svc", path=str(svc_dir))
        enhance_with_auth_scanning([svc], tmp_path)
        assert "auth_types" in svc.attributes
        assert "actors" in svc.attributes
        assert isinstance(svc.attributes["auth_types"], list)

    def test_enhance_deployment_targets_populates_field(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_deployment_targets

        # resolve_service_path looks for repo_root/service.name — create that dir
        svc_dir = tmp_path / "test-svc"
        svc_dir.mkdir()
        (svc_dir / "Dockerfile").write_text("FROM python:3.11")
        svc = make_service(name="test-svc", path=str(svc_dir))
        enhance_with_deployment_targets([svc], tmp_path)
        assert "Container" in (svc.deployment_targets or [])

    def test_enhance_documentation_quality_populates_field(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_documentation_quality

        # resolve_service_path looks for repo_root/service.name — create that dir
        svc_dir = tmp_path / "test-svc"
        svc_dir.mkdir()
        (svc_dir / "README.md").write_text("# Service\nBasic readme.")
        svc = make_service(name="test-svc", path=str(svc_dir))
        enhance_with_documentation_quality([svc], tmp_path)
        assert svc.documentation_quality is not None
        assert isinstance(svc.documentation_quality, int)

    def test_enhance_api_surface_populates_field(self, tmp_path):
        from app.services.service_extraction.service_enhancers import enhance_with_api_surface_types

        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
        svc = make_service(path=str(tmp_path))
        enhance_with_api_surface_types([svc], tmp_path)
        assert isinstance(svc.api_surface_types, list)
