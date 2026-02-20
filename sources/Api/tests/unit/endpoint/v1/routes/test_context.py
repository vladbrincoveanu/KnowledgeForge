"""Unit tests for context review API routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.endpoint.v1.dependencies import reset_level1_context_service_for_tests
from app.endpoint.v1.routes.context import router


@pytest.fixture
def client() -> TestClient:
    reset_level1_context_service_for_tests()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_viewer_can_read_generated_override_effective_and_provenance(client: TestClient) -> None:
    response = client.get(
        "/api/v1/context/wps/level1",
        params={"snapshot_id": "wps-snap-001", "min_confidence": 0.8},
        headers={"X-Role": "viewer"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["system_id"] == "wps"
    assert payload["snapshot_id"] == "wps-snap-001"
    assert "fields" in payload
    assert "provenance" in payload
    assert payload["fields"]["owner"]["generated"] == "platform-core"
    assert payload["fields"]["owner"]["effective"] == "platform-core"


def test_missing_snapshot_returns_404(client: TestClient) -> None:
    response = client.get(
        "/api/v1/context/wps/level1",
        params={"snapshot_id": "missing"},
        headers={"X-Role": "viewer"},
    )

    assert response.status_code == 404


def test_editor_can_create_override_and_effective_value_changes(client: TestClient) -> None:
    put_response = client.put(
        "/api/v1/context/wps/overrides",
        json={
            "field_path": "owner",
            "value": "payments-sme",
            "updated_by": "alice",
            "override_reason": "SME correction",
        },
        headers={"X-Role": "editor"},
    )

    assert put_response.status_code == 200

    get_response = client.get(
        "/api/v1/context/wps/level1",
        params={"snapshot_id": "wps-snap-001"},
        headers={"X-Role": "viewer"},
    )
    payload = get_response.json()

    assert payload["fields"]["owner"]["override"] == "payments-sme"
    assert payload["fields"]["owner"]["effective"] == "payments-sme"
    assert payload["fields"]["owner"]["state"] == "overridden"


def test_viewer_cannot_create_override(client: TestClient) -> None:
    response = client.put(
        "/api/v1/context/wps/overrides",
        json={
            "field_path": "owner",
            "value": "payments-sme",
            "updated_by": "alice",
            "override_reason": "SME correction",
        },
        headers={"X-Role": "viewer"},
    )

    assert response.status_code == 403


def test_editor_cannot_transition_review_status(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/context/wps/review-status",
        json={"status": "reviewed", "updated_by": "alice"},
        headers={"X-Role": "editor"},
    )

    assert response.status_code == 403


def test_approver_status_transition_flow(client: TestClient) -> None:
    first = client.patch(
        "/api/v1/context/wps/review-status",
        json={"status": "reviewed", "updated_by": "approver-user"},
        headers={"X-Role": "approver"},
    )
    second = client.patch(
        "/api/v1/context/wps/review-status",
        json={"status": "approved_for_publish", "updated_by": "approver-user"},
        headers={"X-Role": "approver"},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "reviewed"
    assert second.status_code == 200
    assert second.json()["status"] == "approved_for_publish"


def test_invalid_review_transition_is_rejected(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/context/wps/review-status",
        json={"status": "approved_for_publish", "updated_by": "approver-user"},
        headers={"X-Role": "approver"},
    )

    assert response.status_code == 400
    assert "Invalid transition" in response.json()["detail"]
