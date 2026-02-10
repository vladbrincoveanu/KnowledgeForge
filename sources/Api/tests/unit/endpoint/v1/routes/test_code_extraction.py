"""Unit tests for code extraction (C4) API routes."""

import io
import json
import zipfile
import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a FastAPI TestClient with only the code extraction router."""
    from fastapi import FastAPI
    from app.endpoint.v1.routes.code_extraction import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/code")
    return TestClient(app)


def _make_zip(files: dict) -> bytes:
    """Build an in-memory ZIP with given file contents."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf.read()


class TestExtractFromGitHub:
    """Test POST /api/v1/code/extract-from-github."""

    def test_valid_github_url_returns_pending(self, client, tmp_path):
        """Valid GitHub URL should create scan task and return pending."""
        # The route downloads synchronously then queues background extraction
        with patch(
            "app.endpoint.v1.routes.code_extraction.GitHubDownloader.download_repository",
            return_value=tmp_path,
        ), patch("app.endpoint.v1.routes.code_extraction.run_c4_extraction"):
            response = client.post(
                "/api/v1/code/extract-from-github",
                json={"github_url": "https://github.com/owner/repo"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert "task_id" in data

    def test_invalid_github_url_returns_400(self, client):
        """Non-GitHub URL should return 400."""
        response = client.post(
            "/api/v1/code/extract-from-github",
            json={"github_url": "https://bitbucket.org/owner/repo"},
        )
        assert response.status_code == 400

    def test_github_url_required(self, client):
        """github_url is a required field."""
        response = client.post(
            "/api/v1/code/extract-from-github",
            json={},
        )
        # FastAPI will return 422 (unprocessable entity) for missing required fields
        assert response.status_code == 422


class TestUploadRepo:
    """Test POST /api/v1/code/upload-repo."""

    def test_valid_zip_upload_returns_pending(self, client):
        """Valid ZIP upload should create scan task and return pending."""
        zip_bytes = _make_zip({
            "repo/README.md": "# My Repo",
            "repo/main.py": "from fastapi import FastAPI\napp = FastAPI()",
        })
        with patch("app.endpoint.v1.routes.code_extraction.run_c4_extraction"):
            response = client.post(
                "/api/v1/code/upload-repo",
                files={"file": ("project.zip", zip_bytes, "application/zip")},
            )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"

    def test_non_zip_file_returns_400(self, client):
        """Non-ZIP file should be rejected with 400."""
        response = client.post(
            "/api/v1/code/upload-repo",
            files={"file": ("readme.md", b"# README", "text/plain")},
        )
        assert response.status_code == 400


class TestScanStatus:
    """Test GET /api/v1/code/scan/{task_id}."""

    def test_get_status_existing_task(self, client, tmp_path):
        """Should return status for an existing task."""
        with patch(
            "app.endpoint.v1.routes.code_extraction.GitHubDownloader.download_repository",
            return_value=tmp_path,
        ), patch("app.endpoint.v1.routes.code_extraction.run_c4_extraction"):
            create_resp = client.post(
                "/api/v1/code/extract-from-github",
                json={"github_url": "https://github.com/owner/repo"},
            )
        task_id = create_resp.json()["task_id"]

        # Get status
        status_resp = client.get(f"/api/v1/code/scan/{task_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["task_id"] == task_id
        assert "status" in data
        assert "progress" in data

    def test_get_status_nonexistent_returns_404(self, client):
        """Non-existent task ID should return 404."""
        response = client.get("/api/v1/code/scan/nonexistent-task-id")
        assert response.status_code == 404

    def test_status_response_has_required_fields(self, client, tmp_path):
        """All required fields should be present in status response."""
        with patch(
            "app.endpoint.v1.routes.code_extraction.GitHubDownloader.download_repository",
            return_value=tmp_path,
        ), patch("app.endpoint.v1.routes.code_extraction.run_c4_extraction"):
            create_resp = client.post(
                "/api/v1/code/extract-from-github",
                json={"github_url": "https://github.com/owner/repo"},
            )
        task_id = create_resp.json()["task_id"]
        data = client.get(f"/api/v1/code/scan/{task_id}").json()

        for field in ["task_id", "status", "progress", "message", "created_at"]:
            assert field in data, f"Missing required field: {field}"


class TestDeleteScan:
    """Test DELETE /api/v1/code/scan/{task_id}."""

    def test_delete_existing_task(self, client, tmp_path):
        """Should successfully delete an existing scan task."""
        with patch(
            "app.endpoint.v1.routes.code_extraction.GitHubDownloader.download_repository",
            return_value=tmp_path,
        ), patch("app.endpoint.v1.routes.code_extraction.run_c4_extraction"):
            create_resp = client.post(
                "/api/v1/code/extract-from-github",
                json={"github_url": "https://github.com/owner/repo"},
            )
        task_id = create_resp.json()["task_id"]

        delete_resp = client.delete(f"/api/v1/code/scan/{task_id}")
        assert delete_resp.status_code == 200

    def test_delete_nonexistent_task_returns_404(self, client):
        """Deleting a non-existent task should return 404."""
        response = client.delete("/api/v1/code/scan/nonexistent-id")
        assert response.status_code == 404


class TestNodeDescription:
    """Test POST /api/v1/code/describe/node."""

    def test_describe_node_without_llm(self, client):
        """Should return a fallback response when LLM is unavailable."""
        with patch(
            "app.endpoint.v1.routes.code_extraction.get_llm_manager",
            return_value=None,
        ):
            response = client.post(
                "/api/v1/code/describe/node",
                json={
                    "id": "node-1",
                    "name": "UserService",
                    "type": "service",
                    "level": "container",
                },
            )
        # Should respond (either with fallback message or an error)
        assert response.status_code in (200, 503)

    def test_describe_node_with_llm(self, client):
        """Should return LLM-generated description when LLM is available."""
        mock_llm = Mock()
        mock_llm.generate_text.return_value = "This is a user service."
        with patch(
            "app.endpoint.v1.routes.code_extraction.get_llm_manager",
            return_value=mock_llm,
        ):
            response = client.post(
                "/api/v1/code/describe/node",
                json={"name": "UserService", "type": "service"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "description" in data
