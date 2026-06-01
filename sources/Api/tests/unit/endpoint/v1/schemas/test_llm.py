"""Unit tests for LLM-related Pydantic schemas."""

import pytest
from pydantic import BaseModel, ValidationError
from app.endpoint.v1.schemas.llm import ModelName


class _Holder(BaseModel):
    model: ModelName


def test_model_name_accepts_anthropic_format():
    """Anthropic-style model names (anthropic/<name>) should validate."""
    h = _Holder(model="anthropic/claude-sonnet-4-20250514")
    assert h.model == "anthropic/claude-sonnet-4-20250514"


def test_model_name_accepts_anthropic_with_dots():
    """Anthropic model names with dots and dashes in the version should validate."""
    h = _Holder(model="anthropic/claude-3.5-sonnet")
    assert h.model == "anthropic/claude-3.5-sonnet"


def test_model_name_accepts_minimax_format():
    """MiniMax-style model names (MiniMax-<version>) should validate."""
    h = _Holder(model="MiniMax-M2.7")
    assert h.model == "MiniMax-M2.7"


@pytest.mark.parametrize("bad", ["gpt-4", "claude", "", "anthropic/", "MiniMax", "openai/gpt-4"])
def test_model_name_rejects_unknown(bad):
    """Non-conforming model strings should raise a ValidationError."""
    with pytest.raises(ValidationError):
        _Holder(model=bad)
