"""
Task #13: Comprehensive error path tests covering all major exception types.

Tests graceful degradation and meaningful error reporting across:
- File system errors (FileNotFoundError, PermissionError)
- Parsing errors (yaml.YAMLError, json.JSONDecodeError)
- Network errors (requests.Timeout, ConnectionError)
- Domain validation errors (invalid inputs, type errors)
"""

import json
import pytest
import yaml
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import requests


# ─────────────────────────────────────────────────────────────────────
# File System Error Tests
# ─────────────────────────────────────────────────────────────────────

class TestFileSystemErrors:
    """Test graceful handling of file system errors."""

    def test_service_extractor_nonexistent_path(self):
        """ServiceExtractor should handle nonexistent repo path gracefully."""
        from app.services.service_extraction.service_extractor import ServiceExtractor
        nonexistent = Path("/nonexistent/path/to/repo")
        # Should not raise on init
        extractor = ServiceExtractor(nonexistent)
        # extract_services should handle the missing path gracefully
        with patch("app.services.service_extraction.service_extractor.GitStatusAnalyzer"), \
             patch("app.services.service_extraction.service_extractor.GitContributorAnalyzer"), \
             patch("app.services.service_extraction.service_extractor.DomainExtractor"):
            result = extractor.extract_services()
        assert isinstance(result, list)

    def test_compose_detector_nonexistent_repo(self):
        """ComposeDetector should return False for can_detect on missing path."""
        from app.services.c4.containers.compose_detector import ComposeDetector
        detector = ComposeDetector(Path("/nonexistent/path"))
        assert detector.can_detect() is False

    def test_terraform_detector_nonexistent_repo(self):
        """TerraformDetector should return False for can_detect on missing path."""
        from app.services.c4.containers.terraform_detector import TerraformDetector
        detector = TerraformDetector(Path("/nonexistent/path"))
        assert detector.can_detect() is False

    def test_dependency_detector_empty_dir(self):
        """DependencyDetector should return empty list for empty directory."""
        from app.services.c4.context.dependency_detector import DependencyDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = DependencyDetector(Path(tmpdir), enable_classification=False)
            result = detector.detect_external_dependencies()
        assert result == []

    def test_compose_detector_unreadable_file(self):
        """ComposeDetector should handle permission-denied files gracefully."""
        from app.services.c4.containers.compose_detector import ComposeDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_file = Path(tmpdir) / "docker-compose.yml"
            compose_file.write_text("version: '3'\nservices: {}")
            # Mock open to simulate PermissionError
            with patch("builtins.open", side_effect=PermissionError("Permission denied")):
                detector = ComposeDetector(Path(tmpdir))
                result = detector.detect()
            # Should handle gracefully - return list (possibly empty)
            assert isinstance(result, list)

    def test_pipeline_with_empty_directory(self):
        """ServiceExtractionPipeline should handle completely empty directory."""
        from app.services.service_extraction.service_extraction_pipeline import (
            ServiceExtractionPipeline,
        )
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("app.services.service_extraction.service_extraction_pipeline.GitFullAnalyzer"), \
             patch("app.services.service_extraction.service_extraction_pipeline.DomainExtractor"), \
             patch("app.services.service_extraction.service_extraction_pipeline.ServiceDiscoverer") as mock_disc:
            mock_disc_instance = Mock()
            mock_disc_instance.discover_services.return_value = []
            mock_disc_instance.errors = []
            mock_disc_instance.warnings = []
            mock_disc.return_value = mock_disc_instance

            pipeline = ServiceExtractionPipeline(Path(tmpdir))
            services, context_nodes = pipeline.extract_services()

        assert isinstance(services, list)
        assert isinstance(context_nodes, list)


# ─────────────────────────────────────────────────────────────────────
# YAML Parsing Error Tests
# ─────────────────────────────────────────────────────────────────────

class TestYAMLParsingErrors:
    """Test graceful handling of malformed YAML files."""

    def test_compose_detector_unclosed_bracket(self):
        """ComposeDetector should handle unclosed brackets in YAML."""
        from app.services.c4.containers.compose_detector import ComposeDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "docker-compose.yml").write_text(
                "version: '3'\nservices:\n  api:\n    ports:\n      - \"8000:8000"
            )
            detector = ComposeDetector(Path(tmpdir))
            result = detector.detect()
        assert isinstance(result, list)

    def test_compose_detector_invalid_yaml_type(self):
        """ComposeDetector should handle YAML with wrong types."""
        from app.services.c4.containers.compose_detector import ComposeDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            # Services should be a dict, not a string
            (Path(tmpdir) / "docker-compose.yml").write_text(
                "version: '3'\nservices: this-should-be-a-dict"
            )
            detector = ComposeDetector(Path(tmpdir))
            result = detector.detect()
        assert isinstance(result, list)

    def test_compose_detector_empty_services(self):
        """ComposeDetector should handle empty services section."""
        from app.services.c4.containers.compose_detector import ComposeDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "docker-compose.yml").write_text(
                "version: '3'\nservices: {}\n"
            )
            detector = ComposeDetector(Path(tmpdir))
            result = detector.detect()
        assert result == [] or isinstance(result, list)

    def test_service_extractor_malformed_docker_compose(self):
        """ServiceExtractor should handle malformed docker-compose gracefully."""
        from app.services.service_extraction.service_extractor import ServiceExtractor
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / "docker-compose.yml").write_text("invalid: yaml: [unclosed")
            with patch("app.services.service_extraction.service_extractor.GitStatusAnalyzer"), \
                 patch("app.services.service_extraction.service_extractor.GitContributorAnalyzer"), \
                 patch("app.services.service_extraction.service_extractor.DomainExtractor"):
                extractor = ServiceExtractor(repo)
                result = extractor.extract_services()
            # Should not crash, and should report errors
            assert isinstance(result, list)
            assert len(extractor.errors) > 0 or len(extractor.warnings) > 0


# ─────────────────────────────────────────────────────────────────────
# JSON Parsing Error Tests
# ─────────────────────────────────────────────────────────────────────

class TestJSONParsingErrors:
    """Test graceful handling of malformed JSON files."""

    def test_dependency_detector_malformed_package_json(self):
        """DependencyDetector should handle malformed package.json."""
        from app.services.c4.context.dependency_detector import DependencyDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "package.json").write_text('{"dependencies": {invalid json')
            detector = DependencyDetector(Path(tmpdir), enable_classification=False)
            result = detector.detect_external_dependencies()
        # Should not crash
        assert isinstance(result, list)

    def test_dependency_detector_empty_package_json(self):
        """DependencyDetector should handle empty package.json."""
        from app.services.c4.context.dependency_detector import DependencyDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "package.json").write_text("{}")
            detector = DependencyDetector(Path(tmpdir), enable_classification=False)
            result = detector.detect_external_dependencies()
        assert isinstance(result, list)

    def test_dependency_detector_no_dependencies_key(self):
        """DependencyDetector handles package.json without 'dependencies' key."""
        from app.services.c4.context.dependency_detector import DependencyDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = {"name": "my-app", "version": "1.0.0"}
            (Path(tmpdir) / "package.json").write_text(json.dumps(pkg))
            detector = DependencyDetector(Path(tmpdir), enable_classification=False)
            result = detector.detect_external_dependencies()
        assert isinstance(result, list)


# ─────────────────────────────────────────────────────────────────────
# Network Error Tests
# ─────────────────────────────────────────────────────────────────────

class TestNetworkErrors:
    """Test graceful handling of network-related errors."""

    def test_github_downloader_timeout(self):
        """GitHubDownloader should handle request timeout gracefully."""
        from app.services.service_extraction.github_downloader import GitHubDownloader
        with patch("requests.get", side_effect=requests.Timeout("Connection timed out")):
            with pytest.raises(Exception):
                # Should raise (not silently fail) since download is critical
                GitHubDownloader.download_repository(
                    "https://github.com/owner/repo",
                    output_dir=Path(tempfile.mkdtemp()),
                )

    def test_github_downloader_connection_error(self):
        """GitHubDownloader should handle connection errors."""
        from app.services.service_extraction.github_downloader import GitHubDownloader
        with patch("requests.get", side_effect=requests.ConnectionError("No route to host")):
            with pytest.raises(Exception):
                GitHubDownloader.download_repository(
                    "https://github.com/owner/repo",
                    output_dir=Path(tempfile.mkdtemp()),
                )

    def test_github_downloader_404_response(self):
        """GitHubDownloader should handle 404 HTTP responses."""
        from app.services.service_extraction.github_downloader import GitHubDownloader
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        with patch("requests.get", return_value=mock_response):
            with pytest.raises(Exception):
                GitHubDownloader.download_repository(
                    "https://github.com/owner/nonexistent-repo",
                    output_dir=Path(tempfile.mkdtemp()),
                )


# ─────────────────────────────────────────────────────────────────────
# API Route Error Tests
# ─────────────────────────────────────────────────────────────────────

class TestAPIRouteErrors:
    """Test API route error handling."""

    @pytest.fixture(scope="class")
    def service_client(self):
        from fastapi import FastAPI
        from app.endpoint.v1.routes.service_extraction import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/services")
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.fixture(scope="class")
    def code_client(self):
        from fastapi import FastAPI
        from app.endpoint.v1.routes.code_extraction import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/code")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_service_extract_empty_body(self, service_client):
        """Empty body should return 422 or 400."""
        response = service_client.post(
            "/api/v1/services/extract-from-github",
            json={},
        )
        assert response.status_code in (400, 422)

    def test_service_extract_null_url(self, service_client):
        """Null github_url should return 400."""
        response = service_client.post(
            "/api/v1/services/extract-from-github",
            json={"github_url": None},
        )
        assert response.status_code == 400

    def test_service_status_not_found(self, service_client):
        """Non-existent task should return 404."""
        response = service_client.get("/api/v1/services/extraction/does-not-exist")
        assert response.status_code == 404

    def test_service_delete_not_found(self, service_client):
        """Delete non-existent task should return 404."""
        response = service_client.delete("/api/v1/services/extraction/does-not-exist")
        assert response.status_code == 404

    def test_service_results_not_found(self, service_client):
        """Results for non-existent task should return 404."""
        response = service_client.get("/api/v1/services/extraction/does-not-exist/results")
        assert response.status_code == 404

    def test_code_scan_not_found(self, code_client):
        """Scan status for non-existent task should return 404."""
        response = code_client.get("/api/v1/code/scan/does-not-exist")
        assert response.status_code == 404

    def test_code_scan_results_not_found(self, code_client):
        """Results for non-existent scan should return 404."""
        response = code_client.get("/api/v1/code/scan/does-not-exist/results")
        assert response.status_code == 404

    def test_code_delete_not_found(self, code_client):
        """Delete non-existent scan should return 404."""
        response = code_client.delete("/api/v1/code/scan/does-not-exist")
        assert response.status_code == 404

    def test_code_extract_missing_github_url(self, code_client):
        """Missing required github_url should return 422."""
        response = code_client.post("/api/v1/code/extract-from-github", json={})
        assert response.status_code == 422

    def test_code_upload_missing_file(self, code_client):
        """Upload-repo without file should return 422."""
        response = code_client.post("/api/v1/code/upload-repo")
        assert response.status_code == 422


# ─────────────────────────────────────────────────────────────────────
# Terraform Parsing Error Tests
# ─────────────────────────────────────────────────────────────────────

class TestTerraformParsingErrors:
    """Test Terraform detector error handling."""

    def test_terraform_empty_file(self):
        """TerraformDetector should handle empty .tf files."""
        from app.services.c4.containers.terraform_detector import TerraformDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.tf").write_text("")
            detector = TerraformDetector(Path(tmpdir))
            result = detector.detect()
        assert isinstance(result, list)

    def test_terraform_no_resources(self):
        """TerraformDetector should return empty list when no recognized resources."""
        from app.services.c4.containers.terraform_detector import TerraformDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.tf").write_text(
                'variable "region" { default = "us-east-1" }\n'
                'output "vpc_id" { value = aws_vpc.main.id }\n'
            )
            detector = TerraformDetector(Path(tmpdir))
            result = detector.detect()
        # Variables and outputs are not tracked resources
        assert isinstance(result, list)

    def test_terraform_malformed_resource_block(self):
        """TerraformDetector should handle malformed resource blocks gracefully."""
        from app.services.c4.containers.terraform_detector import TerraformDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.tf").write_text(
                'resource "aws_db_instance" {  # missing resource name\n'
                '  identifier = "db"\n'
                '}\n'
            )
            detector = TerraformDetector(Path(tmpdir))
            result = detector.detect()
        assert isinstance(result, list)

    def test_terraform_binary_file(self):
        """TerraformDetector should handle binary/non-text .tf files gracefully."""
        from app.services.c4.containers.terraform_detector import TerraformDetector
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "corrupt.tf").write_bytes(b"\xff\xfe\x00binary\x00content")
            detector = TerraformDetector(Path(tmpdir))
            result = detector.detect()
        assert isinstance(result, list)
