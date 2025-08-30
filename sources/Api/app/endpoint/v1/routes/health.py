"""Health and monitoring endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict, Any

from utils.config import config

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint for Kubernetes deployment."""
    try:
        # Check dependencies
        dependencies = {
            "neo4j": "healthy",  # Placeholder - implement actual health checks
            "llm_server": "healthy",  # Placeholder - implement actual health checks
            "duckdb": "healthy"   # Placeholder - implement actual health checks
        }
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(),
            "version": "1.0.0",
            "dependencies": dependencies
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(),
            "version": "1.0.0",
            "dependencies": {"error": str(e)}
        }


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint for Kubernetes deployment."""
    try:
        # Check if the service is ready to handle requests
        if not config:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": "Configuration not loaded"}
            )
        
        return {"status": "ready"}
        
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": str(e)}
        )


@router.get("/public")
async def public_health_check():
    """Public health check endpoint (no authentication required)."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "message": "KnowledgeForge API is running"
    }


@router.get("/metrics")
async def get_system_metrics():
    """Get system performance and extraction metrics."""
    try:
        # This would be moved from main.py and properly implemented
        return {
            "system_metrics": {
                "total_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "success_rate": 0
            },
            "extraction_metrics": {
                "average_processing_time": 0,
                "total_entities_extracted": 0,
                "total_relationships_discovered": 0
            },
            "quality_metrics": {
                "average_entity_confidence": config.extraction.confidence_threshold,
                "average_relationship_confidence": config.extraction.relationship_threshold,
                "data_coverage": 0.92
            },
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")
