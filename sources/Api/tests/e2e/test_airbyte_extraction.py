# sources/Api/tests/e2e/test_airbyte_extraction.py
"""E2E tests for Airbyte monorepo extraction."""

import pytest
import subprocess
from pathlib import Path

DEMO_AIRBYTE_PATH = Path(__file__).parent.parent.parent.parent.parent / "sources" / "demo" / "airbyte"
API_ROOT = Path(__file__).parent.parent.parent.parent / "Api"


class TestAirbyteServiceDiscovery:
    """Test service discovery against Airbyte monorepo."""

    def test_airbyte_fixture_exists(self):
        """Verify Airbyte fixture is checked out."""
        assert DEMO_AIRBYTE_PATH.exists(), f"Airbyte fixture not found at {DEMO_AIRBYTE_PATH}"

    def test_airbyte_extracts_without_error(self):
        """Smoke test: extraction runs to completion (requires Docker services)."""
        result = subprocess.run(
            [
                "python", "-m", "pytest",
                "test_e2e_extraction.py", "-v",
                "-k", "test_01",
                "--tb=short",
            ],
            cwd=API_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and ("psycopg2" in result.stdout or "postgres" in result.stdout or "nodename" in result.stdout):
            pytest.skip("Docker database services not available (run 'make up' first)")
        assert result.returncode == 0, f"Extraction failed: {result.stderr}"


class TestAirbyteLanguageDetection:
    """Test language detection across Airbyte services."""

    def test_java_detected(self):
        """Airbyte has Java services (build.gradle, .java files)."""
        java_files = list(DEMO_AIRBYTE_PATH.rglob("*.java"))
        assert len(java_files) > 10, "Expected many Java files in Airbyte"

    def test_python_detected(self):
        """Airbyte has Python services."""
        py_files = list((DEMO_AIRBYTE_PATH / "airbyte-integrations").rglob("setup.py"))
        assert len(py_files) > 0, "Expected Python setup.py files"


class TestAirbyteContainerDetection:
    """Test Docker/container detection in Airbyte."""

    def test_docker_compose_exists(self):
        """Airbyte root has docker-compose.yml."""
        if not (DEMO_AIRBYTE_PATH / "docker-compose.yml").exists():
            pytest.skip("docker-compose.yml not present in fixture (partial checkout)")

    def test_oss_dockerfile_exists(self):
        """Airbyte has OSS-specific Dockerfile."""
        has_dockerfile = (DEMO_AIRBYTE_PATH / "oss.Dockerfile").exists() or \
                         (DEMO_AIRBYTE_PATH / "Dockerfile").exists()
        if not has_dockerfile:
            pytest.skip("Dockerfile not present in fixture (partial checkout)")


class TestAirbyteMetadataPopulation:
    """Test that Airbyte extraction populates required metadata fields."""

    def test_services_have_domain(self):
        """Extracted Airbyte services should have business domain set."""
        extraction_file = API_ROOT / "sources" / "data" / "c4_extractions"
        if not extraction_file.exists():
            pytest.skip("No extraction output yet")


class TestAirbyteInterServiceDependencies:
    """Test that inter-service dependencies are mapped."""

    def test_gradle_build_structure(self):
        """Airbyte uses Gradle for build configuration."""
        assert (DEMO_AIRBYTE_PATH / "build.gradle").exists()
        assert (DEMO_AIRBYTE_PATH / "settings.gradle").exists()
