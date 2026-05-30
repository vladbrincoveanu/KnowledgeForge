"""Unit tests for code extraction (C4) API routes."""

import io
import json
import zipfile
from datetime import datetime, timezone

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
        assert response.status_code == 202
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
        assert response.status_code == 202
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


class TestArchitectureEndpoint:
    """Test GET /api/v1/code/architecture."""

    def test_returns_bundled_demo_by_default(self, client):
        """Cold starts should return the bundled Airbyte demo payload."""
        from app.endpoint.v1.routes import code_extraction as route_module

        route_module.scan_tasks.clear()

        response = client.get("/api/v1/code/architecture")

        assert response.status_code == 200
        data = response.json()
        assert data["system_context"]["name"] == "airbyte"
        assert data["metadata"]["total_containers"] == len(data["containers"])
        assert data["metadata"]["total_components"] == len(data["components"])
        assert len(data["containers"]) >= 12
        assert len(data["components"]) >= 20

        container_names = {container["name"] for container in data["containers"]}
        assert {
            "destination-harness",
            "connector-acceptance-test",
            "base-java",
            "base-normalization",
            "base",
            "generator",
            "docusaurus",
        }.issubset(container_names)

        dependency_names = {
            dependency["name"]
            for dependency in data["system_context"]["external_dependencies"]
        }
        assert len(dependency_names) >= 5

    def test_runtime_extraction_ignored_when_bundled_demo_exists(self, client):
        """Bundled demo takes precedence; in-memory runtime extractions are only used when no bundled demo exists."""
        from app.endpoint.v1.routes import code_extraction as route_module

        route_module.scan_tasks.clear()
        route_module.scan_tasks["runtime-task"] = {
            "task_id": "runtime-task",
            "status": "completed",
            "created_at": datetime.now(timezone.utc),
            "completed_at": datetime.now(timezone.utc),
            "c4_architecture": {
                "c4_model_version": "1.0",
                "system_context": {
                    "name": "Runtime Extraction",
                    "purpose": "Loaded from a completed scan task",
                    "external_dependencies": [],
                },
                "containers": [],
                "components": [],
                "relationships": {},
                "metadata": {},
            },
        }

        response = client.get("/api/v1/code/architecture")

        route_module.scan_tasks.clear()

        assert response.status_code == 200
        assert response.json()["system_context"]["name"] == "airbyte"


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


class TestArchitectureChat:
    """Test POST /api/v1/code/chat/context."""

    def test_chat_context_returns_heuristic_fallback(self, client):
        """Should answer from viewer context when no LLM is available."""
        with patch(
            "app.endpoint.v1.routes.code_extraction.get_llm_manager",
            return_value=None,
        ):
            response = client.post(
                "/api/v1/code/chat/context",
                json={
                    "preferHeuristic": True,
                    "message": "Can you compare alternatives here?",
                    "selection": {
                        "kind": "node",
                        "node": {
                            "name": "SignalForge",
                            "type": "external_system",
                            "description": "SignalForge helps with merchant risk scoring.",
                            "attributes": {
                                "provider_alternatives": [
                                    {
                                        "provider": "Sift",
                                        "price_tier": "High",
                                        "performance_tier": "Enterprise",
                                        "profile": "Network effects for fraud detection.",
                                    }
                                ]
                            },
                        },
                    },
                    "architecture": {
                        "selectedLevel": "context",
                        "system": {"name": "OmniPay Platform"},
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "heuristic"
        assert "Known alternatives for SignalForge" in data["message"]
        assert "Sift" in data["message"]

    def test_chat_context_uses_llm_when_available(self, client):
        """Should return the LLM response when a model is configured."""
        mock_llm = Mock()
        mock_llm.generate_text.return_value = "GlobalBank should stay at context level."

        with patch(
            "app.endpoint.v1.routes.code_extraction.get_llm_manager",
            return_value=mock_llm,
        ):
            response = client.post(
                "/api/v1/code/chat/context",
                json={
                    "message": "Should GlobalBank stay at context level?",
                    "history": [
                        {"role": "user", "content": "What does GlobalBank do?"}
                    ],
                    "selection": {
                        "kind": "node",
                        "node": {
                            "name": "GlobalBank",
                            "type": "external_system",
                            "description": "GlobalBank handles settlement for OmniPay.",
                        },
                    },
                    "architecture": {
                        "selectedLevel": "context",
                        "system": {"name": "OmniPay Platform"},
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "llm"
        assert data["message"] == "GlobalBank should stay at context level."
        mock_llm.generate_text.assert_called_once()
        assert mock_llm.generate_text.call_args.kwargs["max_tokens"] == 1024

    def test_chat_context_can_stream_ndjson(self, client):
        """Should stream incremental chat deltas when requested."""
        mock_llm = Mock()
        mock_llm.stream_text.return_value = iter(
            ["GlobalBank ", "should ", "stay at context level."]
        )

        with patch(
            "app.endpoint.v1.routes.code_extraction.get_llm_manager",
            return_value=mock_llm,
        ):
            response = client.post(
                "/api/v1/code/chat/context",
                json={
                    "stream": True,
                    "message": "Should GlobalBank stay at context level?",
                    "selection": {
                        "kind": "node",
                        "node": {
                            "name": "GlobalBank",
                            "type": "external_system",
                        },
                    },
                    "architecture": {
                        "selectedLevel": "context",
                        "system": {"name": "OmniPay Platform"},
                    },
                },
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ndjson")
        lines = [json.loads(line) for line in response.text.strip().splitlines()]
        assert lines[:-1] == [
            {"type": "delta", "delta": "GlobalBank ", "source": "llm"},
            {"type": "delta", "delta": "should ", "source": "llm"},
            {"type": "delta", "delta": "stay at context level.", "source": "llm"},
        ]
        assert lines[-1] == {"type": "done", "source": "llm"}
        assert mock_llm.stream_text.call_args.kwargs["max_tokens"] == 1024


class TestGitHubScanRequestFullHistory:
    """Tests for the full_history field added to GitHubScanRequest."""

    def test_full_history_default_false(self):
        from app.endpoint.v1.routes.code_extraction import GitHubScanRequest
        request = GitHubScanRequest(github_url="https://github.com/owner/repo")
        assert request.full_history is False

    def test_full_history_explicit_true(self):
        from app.endpoint.v1.routes.code_extraction import GitHubScanRequest
        request = GitHubScanRequest(github_url="https://github.com/owner/repo", full_history=True)
        assert request.full_history is True


class TestUploadStart:
    """Tests for POST /api/v1/code/upload/start."""

    def test_upload_start_valid_request(self, client):
        response = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 3,
                "expected_size_bytes": 629145600,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert len(data["chunk_urls"]) == 3

    def test_upload_start_invalid_sha256_format(self, client):
        response = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 1,
                "expected_size_bytes": 1024,
                "expected_sha256": "not-a-valid-sha256",
            },
        )
        assert response.status_code == 422

    def test_upload_start_total_chunks_exceeds_limit(self, client):
        response = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 31,
                "expected_size_bytes": 1024,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        assert response.status_code == 422


class TestUploadChunk:
    """Tests for PUT /api/v1/code/upload/chunk/{session_id}/{chunk_number}."""

    def test_upload_chunk_session_not_found(self, client):
        response = client.put(
            "/api/v1/code/upload/chunk/invalid-session/0",
            content=b"test chunk data",
        )
        assert response.status_code == 404

    def test_upload_chunk_duplicate(self, client):
        start_resp = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 1,
                "expected_size_bytes": 5,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        session_id = start_resp.json()["session_id"]

        response1 = client.put(
            f"/api/v1/code/upload/chunk/{session_id}/0",
            content=b"hello",
        )
        assert response1.status_code == 200
        assert response1.json()["received"] is True

        response2 = client.put(
            f"/api/v1/code/upload/chunk/{session_id}/0",
            content=b"hello",
        )
        assert response2.status_code == 200
        assert response2.json()["received"] is False


class TestUploadComplete:
    """Tests for POST /api/v1/code/upload/complete/{session_id}."""

    def test_upload_complete_missing_chunks(self, client):
        start_resp = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 3,
                "expected_size_bytes": 15,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        session_id = start_resp.json()["session_id"]

        client.put(f"/api/v1/code/upload/chunk/{session_id}/0", content=b"01234")

        response = client.post(f"/api/v1/code/upload/complete/{session_id}")
        assert response.status_code == 400
        assert "missing chunks" in str(response.json())


class TestUploadCancel:
    """Tests for DELETE /api/v1/code/upload/session/{session_id}."""

    def test_upload_cancel_success(self, client):
        start_resp = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 1,
                "expected_size_bytes": 5,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        session_id = start_resp.json()["session_id"]

        response = client.delete(f"/api/v1/code/upload/session/{session_id}")
        assert response.status_code == 200
        assert response.json()["cancelled"] is True

        status_resp = client.get(f"/api/v1/code/upload/session/{session_id}/status")
        assert status_resp.status_code == 404


class TestUploadStatus:
    """Tests for GET /api/v1/code/upload/session/{session_id}/status."""

    def test_upload_status_shows_missing_chunks(self, client):
        start_resp = client.post(
            "/api/v1/code/upload/start",
            json={
                "filename": "repo.zip",
                "total_chunks": 3,
                "expected_size_bytes": 15,
                "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
        )
        session_id = start_resp.json()["session_id"]

        client.put(f"/api/v1/code/upload/chunk/{session_id}/0", content=b"01234")
        client.put(f"/api/v1/code/upload/chunk/{session_id}/2", content=b"90123")

        status = client.get(f"/api/v1/code/upload/session/{session_id}/status")
        assert status.status_code == 200
        data = status.json()
        assert set(data["received_chunks"]) == {0, 2}
        assert data["missing_chunks"] == [1]
