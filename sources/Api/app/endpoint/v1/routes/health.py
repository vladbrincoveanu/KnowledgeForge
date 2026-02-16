"""Health and monitoring endpoints."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.infrastructure.llm.llm_manager import LLMManager
from app.endpoint.v1.dependencies import get_llm_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    dependencies: dict[str, str] = {}


@router.get("/", response_model=HealthResponse)
async def health_check(
    llm_manager: LLMManager = Depends(get_llm_manager),
):
    """Health check endpoint for Kubernetes deployment."""
    try:
        # Check LLM service
        llm_status = "not_configured"
        if llm_manager:
            try:
                models = llm_manager.list_models()
                llm_status = "healthy" if models else "no_models"
            except (ConnectionError, RuntimeError) as e:
                llm_status = f"unhealthy: {str(e)}"
                logger.error(f"LLM health check failed: {e}")

        dependencies = {
            "llm_server": llm_status,
        }

        overall_status = "healthy" if llm_status in ["healthy", "not_configured"] else "degraded"

        return HealthResponse(
            status=overall_status,
            timestamp=datetime.now(),
            version="1.0.0",
            dependencies=dependencies,
        )

    except (ConnectionError, RuntimeError) as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now(),
            version="1.0.0",
            dependencies={"error": str(e)},
        )


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint for Kubernetes deployment."""
    return {
        "status": "ready",
        "timestamp": datetime.now().isoformat(),
        "message": "API is ready to accept requests",
    }


@router.get("/public")
async def public_health_check():
    """Public health check endpoint (no authentication required)."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "message": "KnowledgeForge API is running",
    }


@router.get("/metrics")
async def get_system_metrics():
    """Get system performance metrics."""
    return {
        "system_metrics": {
            "uptime_seconds": 0,  # Would track actual uptime
            "active_tasks": 0,
        },
        "extraction_metrics": {
            "total_extractions": 0,  # Would track from JSON files
            "successful_extractions": 0,
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/detailed")
async def detailed_health_check(
    llm_manager: LLMManager = Depends(get_llm_manager),
):
    """Detailed health check with service-specific information."""
    try:
        detailed_status = {}

        # LLM detailed check
        if llm_manager:
            try:
                models = llm_manager.list_models()
                detailed_status["llm"] = {
                    "status": "healthy",
                    "available_models": len(models) if models else 0,
                    "base_url": llm_manager.base_url,
                }
            except (ConnectionError, RuntimeError) as e:
                detailed_status["llm"] = {"status": "unhealthy", "error": str(e)}
        else:
            detailed_status["llm"] = {"status": "not_configured"}

        return {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "services": detailed_status,
        }

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "services": {"error": str(e)},
        }
