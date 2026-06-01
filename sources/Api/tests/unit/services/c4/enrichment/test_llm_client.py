import time
from unittest.mock import patch, MagicMock
import pytest
from app.services.c4.enrichment.llm_client import (
    EnrichmentLLMClient, get_rate_counter, RateCounter,
)


def _make_client_with_stream(chunks: list[dict]) -> MagicMock:
    """Build a mock Anthropic client whose messages.stream yields the given chunks."""
    mock_client = MagicMock()
    # anthropic SDK's stream returns a context manager; use MagicMock with __enter__/__exit__
    stream_cm = MagicMock()
    stream_cm.__enter__.return_value = iter(chunks)
    stream_cm.__exit__.return_value = False
    mock_client.messages.stream.return_value = stream_cm
    return mock_client


@pytest.mark.asyncio
async def test_messages_stream_yields_normalized_chunks():
    chunks = [
        {"type": "content_block_start"},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "p"}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "ong"}},
        {"type": "message_stop", "usage": {"input_tokens": 8, "output_tokens": 3}},
    ]
    mock_client = _make_client_with_stream(chunks)
    client = EnrichmentLLMClient(client=mock_client, model="MiniMax-M2.7")

    out = []
    async for ev in client.messages_stream(messages=[{"role": "user", "content": "ping"}]):
        out.append(ev)

    assert out == [
        {"type": "chunk", "delta": "p"},
        {"type": "chunk", "delta": "ong"},
    ]
    mock_client.messages.stream.assert_called_once()


@pytest.mark.asyncio
async def test_messages_stream_skips_non_delta_events():
    chunks = [
        {"type": "message_start"},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "ok"}},
        {"type": "content_block_stop"},
    ]
    mock_client = _make_client_with_stream(chunks)
    client = EnrichmentLLMClient(client=mock_client, model="MiniMax-M2.7")

    out = []
    async for ev in client.messages_stream(messages=[]):
        out.append(ev)

    assert out == [{"type": "chunk", "delta": "ok"}]


@pytest.mark.asyncio
async def test_from_env_returns_none_when_no_key(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    result = EnrichmentLLMClient.from_env()
    assert result is None


@pytest.mark.asyncio
async def test_from_env_returns_client_when_key_present(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    with patch("app.services.c4.enrichment.llm_client.Anthropic") as mock_anthropic:
        mock_anthropic.return_value = MagicMock()
        client = EnrichmentLLMClient.from_env()
        assert client is not None


@pytest.mark.asyncio
async def test_rate_counter_allows_within_limit():
    counter = RateCounter(max_per_window=10, window_s=3600)
    result = await counter.can_run(1)
    assert result is True


@pytest.mark.asyncio
async def test_rate_counter_rejects_over_limit():
    counter = RateCounter(max_per_window=2, window_s=3600)
    now = time.monotonic()
    counter._timestamps = [now - 100, now - 50]
    result = await counter.can_run(1)
    assert result is False