"""Unit tests for the /v1/llm-config endpoints, including POST /test-prompt SSE."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create a minimal FastAPI app with only the llm_config router.

    Mirrors the test_code_extraction.py pattern: avoid loading the full
    main.py app (which pulls in neo4j, postgres, etc.) and isolate
    the route under test.
    """
    from app.endpoint.v1.routes.llm_config import router

    application = FastAPI()
    application.include_router(router, prefix="/api/v1/config/llm")
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_enrichment_client():
    """Patch EnrichmentLLMClient.from_env to return a mock with messages_stream."""
    with patch("app.endpoint.v1.routes.llm_config.EnrichmentLLMClient") as MockCls:
        mock_instance = MagicMock()
        mock_instance.model = "MiniMax-M2.7"

        async def fake_stream(messages, system="", max_tokens=256):
            for d in ["p", "ong"]:
                yield {"type": "chunk", "delta": d}

        mock_instance.messages_stream = fake_stream
        MockCls.from_env.return_value = mock_instance
        yield mock_instance


def test_test_prompt_returns_sse_stream(client, mock_enrichment_client):
    response = client.post(
        "/api/v1/config/llm/test-prompt",
        json={"prompt": "Reply with: pong"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers.get("cache-control") == "no-cache"
    assert response.headers.get("x-accel-buffering") == "no"
    body = response.text
    # Expect at least one meta + two chunk + one done frame.
    # json.dumps() default formatting includes a space after the colon.
    assert '"type": "chunk"' in body
    assert '"delta": "p"' in body
    assert '"delta": "ong"' in body
    assert '"type": "done"' in body
    assert '"tps"' in body
    assert '"type": "meta"' in body


def test_test_prompt_rejects_empty_prompt(client, mock_enrichment_client):
    response = client.post(
        "/api/v1/config/llm/test-prompt", json={"prompt": ""}
    )
    # Pydantic validation rejects empty string at the schema level
    assert response.status_code == 422


def test_test_prompt_rejects_prompt_too_long(client, mock_enrichment_client):
    response = client.post(
        "/api/v1/config/llm/test-prompt", json={"prompt": "x" * 501}
    )
    assert response.status_code == 422


def test_test_prompt_rejects_invalid_model(client, mock_enrichment_client):
    response = client.post(
        "/api/v1/config/llm/test-prompt",
        json={"prompt": "hi", "model": "gpt-4"},
    )
    assert response.status_code == 422


def test_test_prompt_returns_401_when_no_client(client):
    with patch(
        "app.endpoint.v1.routes.llm_config.EnrichmentLLMClient.from_env"
    ) as mock_from_env:
        mock_from_env.return_value = None
        response = client.post(
            "/api/v1/config/llm/test-prompt", json={"prompt": "hi"}
        )
    assert response.status_code == 401


def test_test_prompt_emits_empty_response_error(client):
    """When the provider yields no chunks, route emits an empty_response error frame."""
    with patch("app.endpoint.v1.routes.llm_config.EnrichmentLLMClient") as MockCls:
        mock_instance = MagicMock()
        mock_instance.model = "MiniMax-M2.7"

        async def empty_stream(messages, system="", max_tokens=256):
            if False:  # pragma: no cover — make this a generator
                yield {}

        mock_instance.messages_stream = empty_stream
        MockCls.from_env.return_value = mock_instance

        response = client.post(
            "/api/v1/config/llm/test-prompt", json={"prompt": "hi"}
        )
    assert response.status_code == 200
    assert '"code": "empty_response"' in response.text


def test_test_prompt_handles_provider_error(client):
    """When the provider raises, route emits a provider_unavailable error frame."""
    with patch("app.endpoint.v1.routes.llm_config.EnrichmentLLMClient") as MockCls:
        mock_instance = MagicMock()
        mock_instance.model = "MiniMax-M2.7"

        async def raising_stream(messages, system="", max_tokens=256):
            raise RuntimeError("boom")
            yield  # pragma: no cover — make this a generator

        mock_instance.messages_stream = raising_stream
        MockCls.from_env.return_value = mock_instance

        response = client.post(
            "/api/v1/config/llm/test-prompt", json={"prompt": "hi"}
        )
    assert response.status_code == 200
    assert '"code": "provider_unavailable"' in response.text
    assert "boom" in response.text


def test_test_prompt_enforces_15s_timeout(client, mock_enrichment_client):
    """When the provider takes >15s, route emits provider_timeout error frame."""
    import asyncio

    async def slow_stream(messages, system="", max_tokens=256):
        await asyncio.sleep(20)
        yield {"type": "chunk", "delta": "late"}  # pragma: no cover

    mock_enrichment_client.messages_stream = slow_stream

    response = client.post(
        "/api/v1/config/llm/test-prompt", json={"prompt": "hi"}
    )
    assert response.status_code == 200
    assert '"code": "provider_timeout"' in response.text


def test_test_prompt_does_not_consume_rate_counter(client, mock_enrichment_client):
    """Manual test prompt must NOT count toward enrichment rate limit (spec §9.1)."""
    from app.services.c4.enrichment.llm_client import get_rate_counter

    counter = get_rate_counter()
    before = sum(1 for t in counter._timestamps)
    client.post("/api/v1/config/llm/test-prompt", json={"prompt": "hi"})
    after = sum(1 for t in counter._timestamps)
    assert after == before, "test-prompt must not increment the rate counter"
