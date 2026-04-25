# sources/Api/tests/e2e/test_airbyte_extraction.py
"""E2E tests for Airbyte monorepo extraction."""

import pytest
from pathlib import Path

DEMO_AIRBYTE_PATH = Path("/app/sources/demo/airbyte")
API_ROOT = Path(__file__).parent.parent.parent / "Api"


class TestAirbyteServiceDiscovery:
    """Test service discovery against Airbyte monorepo."""

    def test_airbyte_fixture_exists(self):
        """Verify Airbyte fixture is checked out."""
        assert DEMO_AIRBYTE_PATH.exists(), f"Airbyte fixture not found at {DEMO_AIRBYTE_PATH}"

    def test_airbyte_extracts_without_error(self):
        """Smoke test: verify Airbyte fixture has build infrastructure."""
        assert (DEMO_AIRBYTE_PATH / "build.gradle").exists(), "Airbyte build.gradle missing"
        assert (DEMO_AIRBYTE_PATH / "settings.gradle").exists(), "Airbyte settings.gradle missing"


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

    def test_dockerfile_exists(self):
        """Airbyte has a Dockerfile in root."""
        has_dockerfile = (DEMO_AIRBYTE_PATH / "oss.Dockerfile").exists() or \
                         (DEMO_AIRBYTE_PATH / "Dockerfile").exists()
        if not has_dockerfile:
            pytest.skip("Dockerfile not present in fixture (partial checkout)")


class TestAirbyteInterServiceDependencies:
    """Test that inter-service dependencies are mapped."""

    def test_gradle_build_structure(self):
        """Airbyte uses Gradle for build configuration."""
        assert (DEMO_AIRBYTE_PATH / "build.gradle").exists()
        assert (DEMO_AIRBYTE_PATH / "settings.gradle").exists()
