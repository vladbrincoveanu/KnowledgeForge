"""Shared schemas for LLM-related endpoints."""

import re
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, Field

_MODEL_RE = re.compile(r"^(anthropic/[A-Za-z0-9._-]+|MiniMax-[A-Za-z0-9._-]+)$")


def _validate_model_name(v: str) -> str:
    if not _MODEL_RE.match(v):
        raise ValueError(
            "Model must match 'anthropic/<name>' or 'MiniMax-<version>'"
        )
    return v


ModelName = Annotated[str, AfterValidator(_validate_model_name)]


class TestPromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    model: Optional[ModelName] = None
