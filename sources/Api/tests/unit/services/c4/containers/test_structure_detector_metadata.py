"""Unit tests for structure-detector metadata enrichment."""

from pathlib import Path
import tempfile

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
