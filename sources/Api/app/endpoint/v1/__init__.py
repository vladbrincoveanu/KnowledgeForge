"""API v1 router configuration."""

from fastapi import APIRouter

from .routes import health, extraction, data, semantic_queries

# Create the main API router
api_router = APIRouter(prefix="/api/v1")

# Include all route modules
api_router.include_router(health.router)
api_router.include_router(extraction.router)
api_router.include_router(data.router)
api_router.include_router(semantic_queries.router)

__all__ = ["api_router"]
