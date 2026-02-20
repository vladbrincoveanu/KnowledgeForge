"""Context review endpoints for C4 Level-1 output."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.endpoint.v1.dependencies import get_level1_context_service
from app.services.c4.context.level1_context_service import (
    Level1ContextResponse,
    Level1ContextService,
    OverrideRequest,
    ReviewStatusRequest,
    VALID_ROLES,
)

router = APIRouter(tags=["context"])


def get_role(x_role: str = Header("viewer", alias="X-Role")) -> str:
    """Resolve request role from headers."""
    role = x_role.strip().lower()
    if role not in VALID_ROLES:
        raise HTTPException(status_code=403, detail="Invalid role")
    return role


def require_any_role(role: str, allowed_roles: set[str]) -> None:
    """Enforce role permissions for endpoint action."""
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Role is not allowed for this action")


@router.get("/context/{system_id}/level1", response_model=Level1ContextResponse)
def get_context_level1(
    system_id: str,
    snapshot_id: str = Query(..., description="Explicit snapshot version"),
    min_confidence: float = Query(0.8, ge=0.0, le=1.0),
    role: str = Depends(get_role),
    service: Level1ContextService = Depends(get_level1_context_service),
) -> Level1ContextResponse:
    """Fetch generated, override, and effective Level-1 context with provenance."""
    require_any_role(role, {"viewer", "editor", "approver"})
    try:
        return service.render_level1_context(
            system_id=system_id,
            snapshot_id=snapshot_id,
            min_confidence=min_confidence,
        )
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "was not found" in detail else 400
        raise HTTPException(status_code=status, detail=detail) from exc


@router.put("/context/{system_id}/overrides")
def put_context_override(
    system_id: str,
    request: OverrideRequest,
    role: str = Depends(get_role),
    service: Level1ContextService = Depends(get_level1_context_service),
) -> dict[str, str]:
    """Create or update field-level override with audit metadata."""
    require_any_role(role, {"editor", "approver"})
    try:
        override = service.upsert_override(system_id=system_id, request=request)
        return {
            "field_path": override.field_path,
            "status": override.status,
            "updated_by": override.updated_by,
            "field_updated_at": override.field_updated_at,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/context/{system_id}/review-status")
def patch_review_status(
    system_id: str,
    request: ReviewStatusRequest,
    role: str = Depends(get_role),
    service: Level1ContextService = Depends(get_level1_context_service),
) -> dict[str, str]:
    """Transition context review state for publication workflow."""
    require_any_role(role, {"approver"})
    try:
        next_state = service.transition_review_status(system_id=system_id, request=request)
        return {
            "system_id": system_id,
            "status": next_state.status,
            "updated_by": next_state.updated_by,
            "updated_at": next_state.updated_at,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
