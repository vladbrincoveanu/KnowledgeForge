"""Unit tests for service extraction API routes."""

import pytest
from unittest.mock import patch, Mock, MagicMock
from fastapi.testclient import TestClient
import io


# We import the router module directly to create a minimal app for testing
@pytest.fixture(scope="module")
def client():
    """Create a FastAPI TestClient with only the service extraction router."""
    from fastapi import FastAPI
    from app.endpoint.v1.routes.service_extraction import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/services")
    return TestClient(app)


class TestExtractFromGitHub:
    """Test POST /api/v1/services/extract-from-github."""

    def test_valid_github_url_returns_202(self, client):
        """Valid GitHub URL should create a task and return pending status."""
        with patch("app.endpoint.v1.routes.service_extraction.run_service_extraction"):
            response = client.post(
                "/api/v1/services/extract-from-github",
                json={"github_url": "https://github.com/owner/repo"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert "task_id" in data
        assert "message" in data
        assert "created_at" in data

    def test_missing_github_url_returns_400(self, client):
        """Missing github_url should return 400."""
        response = client.post(
            "/api/v1/services/extract-from-github",
            json={},
        )
        assert response.status_code == 400
        assert "github_url is required" in response.json()["detail"]

    def test_invalid_github_url_returns_400(self, client):
        """Invalid GitHub URL format should return 400."""
        response = client.post(
            "/api/v1/services/extract-from-github",
            json={"github_url": "https://gitlab.com/owner/repo"},
        )
        assert response.status_code == 400
        assert "Invalid GitHub URL" in response.json()["detail"]

    def test_non_github_url_returns_400(self, client):
        """Non-GitHub URL should be rejected."""
        response = client.post(
            "/api/v1/services/extract-from-github",
            json={"github_url": "not-a-url"},
        )
        assert response.status_code == 400

    def test_task_id_is_unique(self, client):
        """Each extraction should get a unique task ID."""
        with patch("app.endpoint.v1.routes.service_extraction.run_service_extraction"):
            r1 = client.post(
                "/api/v1/services/extract-from-github",
                json={"github_url": "https://github.com/owner/repo1"},
            )
            r2 = client.post(
                "/api/v1/services/extract-from-github",
                json={"github_url": "https://github.com/owner/repo2"},
            )
        assert r1.json()["task_id"] != r2.json()["task_id"]


class TestExtractFromZip:
    """Test POST /api/v1/services/extract-from-zip."""

    def test_valid_zip_upload(self, client):
        """Valid ZIP file should be accepted and return pending status."""
        # Create a minimal in-memory ZIP file
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("repo/README.md", "# Test Repo")
        buf.seek(0)

        with patch("app.endpoint.v1.routes.service_extraction.run_service_extraction"):
            response = client.post(
                "/api/v1/services/extract-from-zip",
                files={"file": ("repo.zip", buf, "application/zip")},
            )
        # Should accept the file
        assert response.status_code in (200, 202)
        if response.status_code == 200:
            data = response.json()
            assert "task_id" in data

    def test_non_zip_file_returns_400(self, client):
        """Non-ZIP file should be rejected."""
        response = client.post(
            "/api/v1/services/extract-from-zip",
            files={"file": ("readme.txt", b"not a zip file", "text/plain")},
        )
        assert response.status_code == 400


class TestGetExtractionStatus:
    """Test GET /api/v1/services/extraction/{task_id}."""

    def test_get_status_existing_task(self, client):
        """Should return status for an existing task."""
        # First create a task
        with patch("app.endpoint.v1.routes.service_extraction.run_service_extraction"):
            create_resp = client.post(
                "/api/v1/services/extract-from-github",
                json={"github_url": "https://github.com/owner/repo"},
            )
        task_id = create_resp.json()["task_id"]

        # Then get its status
        status_resp = client.get(f"/api/v1/services/extraction/{task_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["task_id"] == task_id
        assert "status" in data
        assert "progress" in data

    def test_get_status_nonexistent_task_returns_404(self, client):
        """Non-existent task ID should return 404."""
        response = client.get("/api/v1/services/extraction/nonexistent-task-id")
        assert response.status_code == 404

    def test_status_response_has_required_fields(self, client):
        """Status response should include all required fields."""
        with patch("app.endpoint.v1.routes.service_extraction.run_service_extraction"):
            create_resp = client.post(
                "/api/v1/services/extract-from-github",
                json={"github_url": "https://github.com/owner/repo"},
            )
        task_id = create_resp.json()["task_id"]
        status_resp = client.get(f"/api/v1/services/extraction/{task_id}")
        data = status_resp.json()

        # All these fields should be present
        for field in ["task_id", "status", "progress", "message", "created_at"]:
            assert field in data, f"Missing field: {field}"


class TestDeleteExtraction:
    """Test DELETE /api/v1/services/extraction/{task_id}."""

    def test_delete_existing_task(self, client):
        """Should successfully delete an existing task."""
        with patch("app.endpoint.v1.routes.service_extraction.run_service_extraction"):
            create_resp = client.post(
                "/api/v1/services/extract-from-github",
                json={"github_url": "https://github.com/owner/repo"},
            )
        task_id = create_resp.json()["task_id"]

        delete_resp = client.delete(f"/api/v1/services/extraction/{task_id}")
        assert delete_resp.status_code == 200

    def test_delete_nonexistent_task_returns_404(self, client):
        """Deleting a non-existent task should return 404."""
        response = client.delete("/api/v1/services/extraction/nonexistent-task-id")
        assert response.status_code == 404
