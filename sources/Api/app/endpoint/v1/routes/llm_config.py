"""LLM configuration and stats endpoints."""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.services.c4.enrichment.llm_client import get_rate_counter

router = APIRouter(tags=["llm_config"])

DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"
VALID_MODELS = {
    "anthropic/claude-sonnet-4-20250514",
    "anthropic/claude-haiku-4-5-20251001",
}


class LLMConfigPatch(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None

    @field_validator("model")
    @classmethod
    def model_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith("anthropic/"):
            raise ValueError("model must be 'anthropic/<version>'")
        return v


class LLMConfigResponse(BaseModel):
    model: str
    api_key_set: bool
    api_key_source: str
    rate_limit_used: int
    rate_limit_max: int


def _read_env_config() -> tuple[str, bool, str]:
    model = os.getenv("ENRICHMENT_MODEL", DEFAULT_MODEL)
    api_key = os.getenv("MINIMAX_API_KEY", "")
    api_key_set = bool(api_key)
    api_key_source = "env"
    return model, api_key_set, api_key_source


def _compute_rate_used() -> int:
    rate = get_rate_counter()
    now = __import__("time").monotonic()
    cutoff = now - rate.window_s
    return sum(1 for t in rate._timestamps if t > cutoff)


@router.get("/", response_model=LLMConfigResponse)
async def get_llm_config():
    model, api_key_set, api_key_source = _read_env_config()
    rate_used = _compute_rate_used()
    rate_max = get_rate_counter().max_per_window
    return LLMConfigResponse(
        model=model,
        api_key_set=api_key_set,
        api_key_source=api_key_source,
        rate_limit_used=rate_used,
        rate_limit_max=rate_max,
    )


@router.put("/", response_model=LLMConfigResponse)
async def update_llm_config(patch: LLMConfigPatch):
    if patch.api_key is not None:
        os.environ["MINIMAX_API_KEY"] = patch.api_key
    if patch.model is not None:
        if patch.model not in VALID_MODELS:
            raise HTTPException(
                status_code=400,
                detail=f"model must be one of: {', '.join(sorted(VALID_MODELS))}",
            )
        os.environ["ENRICHMENT_MODEL"] = patch.model
    model, api_key_set, api_key_source = _read_env_config()
    rate_used = _compute_rate_used()
    rate_max = get_rate_counter().max_per_window
    return LLMConfigResponse(
        model=model,
        api_key_set=api_key_set,
        api_key_source=api_key_source,
        rate_limit_used=rate_used,
        rate_limit_max=rate_max,
    )