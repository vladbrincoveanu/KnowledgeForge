import time
from unittest.mock import patch, MagicMock
import pytest
from app.services.c4.enrichment.llm_client import (
    EnrichmentLLMClient, get_rate_counter, RateCounter,
)


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