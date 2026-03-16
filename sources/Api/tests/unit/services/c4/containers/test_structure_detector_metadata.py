"""Unit tests for structure-detector metadata enrichment."""

from pathlib import Path
import tempfile
import json

from app.services.c4.containers.structure_detector import StructureDetector


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_detects_python_service_owner_and_dockerfile_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        service_dir = repo / "fraud-ml"
        _write(service_dir / "Dockerfile", "FROM python:3.11-slim\n")
        _write(service_dir / "requirements.txt", "fastapi==0.115.0\n")
        _write(service_dir / "README.md", "# Fraud ML\n\nOwner: Risk AI Team\n")

        containers = StructureDetector(repo).detect()

        fraud = next(container for container in containers if container["name"] == "fraud-ml")
        assert fraud["technology"] == "Python"
        assert fraud["owner"] == "Risk AI Team"
        assert fraud["dockerfile"] == "fraud-ml/Dockerfile"


def test_detects_dotnet_service_owner_team_from_codeowners():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        service_dir = repo / "card-router"
        _write(service_dir / "Dockerfile", "FROM mcr.microsoft.com/dotnet/aspnet:8.0\n")
        _write(service_dir / "CardRouter.csproj", "<Project Sdk=\"Microsoft.NET.Sdk.Web\" />\n")
        _write(service_dir / "README.md", "# Card Router\n\nOwner: Platform Payments\n")
        _write(
            service_dir / "CODEOWNERS",
            "* @omnipay/vlad @omnipay/security-platform\n",
        )

        containers = StructureDetector(repo).detect()

        router = next(container for container in containers if container["name"] == "card-router")
        assert router["technology"] == ".NET"
        assert router["owner"] == "Platform Payments"
        assert router["team"] == "omnipay/security-platform"
        assert router["owner_team"] == "omnipay/security-platform"


def test_detects_infrastructure_metadata_from_terraform_and_helm():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        service_dir = repo / "infra"
        _write(service_dir / "main.tf", 'terraform {}\n')
        _write(service_dir / "README.md", "# Infra\n\nOwner: Platform\n")
        _write(service_dir / "chart" / "Chart.yaml", "apiVersion: v2\nname: infra\n")

        containers = StructureDetector(repo).detect()

        infra = next(container for container in containers if container["name"] == "infra")
        assert infra["technology"] == "Terraform"
        assert infra["deployment"] == "Helm"
        assert infra["runtime_environment"] == "Kubernetes"
        assert infra["terraform"] is True
        assert infra["helm"] is True
        assert infra["kubernetes"] is True


def test_infrastructure_only_flag_set_when_no_app_code():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        service_dir = repo / "platform"
        _write(service_dir / "main.tf", 'terraform {}\n')
        _write(service_dir / "chart" / "Chart.yaml", "apiVersion: v2\nname: platform\n")

        containers = StructureDetector(repo).detect()

        platform = next(c for c in containers if c["name"] == "platform")
        assert platform.get("is_infrastructure_only") is True


def test_infrastructure_only_flag_not_set_when_dockerfile_present():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        service_dir = repo / "my-api"
        _write(service_dir / "Dockerfile", "FROM python:3.11\n")
        _write(service_dir / "main.tf", 'terraform {}\n')

        containers = StructureDetector(repo).detect()

        api = next(c for c in containers if c["name"] == "my-api")
        assert not api.get("is_infrastructure_only")


def test_config_relationships_extracted_from_dotenv():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        service_dir = repo / "checkout"
        _write(service_dir / "Dockerfile", "FROM python:3.11\n")
        _write(service_dir / ".env", "DB_URL=postgresql://postgres:5432/checkout\n")

        containers = StructureDetector(repo).detect()

        checkout = next(c for c in containers if c["name"] == "checkout")
        rels = checkout.get("relationships", [])
        assert any(r.get("protocol") == "PostgreSQL" for r in rels)


def test_relationships_key_always_present():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        service_dir = repo / "simple-svc"
        _write(service_dir / "Dockerfile", "FROM node:20\n")

        containers = StructureDetector(repo).detect()

        svc = next(c for c in containers if c["name"] == "simple-svc")
        assert "relationships" in svc
        assert isinstance(svc["relationships"], list)
