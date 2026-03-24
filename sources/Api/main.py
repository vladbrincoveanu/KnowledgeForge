"""Main entry point for the KnowledgeForge API."""

import logging
import sys
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add the current directory (sources/api) to the Python path so routes can access utils
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
app_dir = current_dir / "app"
sys.path.insert(0, str(app_dir))

# Lifespan context manager
from contextlib import asynccontextmanager

from app.utils.logging_setup import setup_logging
from app.utils.request_id_middleware import RequestIDFilter, RequestIDMiddleware
from utils.config import get_config

# Configure logging from config.yaml as early as possible
_config = get_config()
setup_logging(_config)

# Attach the request-ID filter to the root logger so all handlers emit it
_rid_filter = RequestIDFilter()
logging.getLogger().addFilter(_rid_filter)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("KnowledgeForge API starting up...")
    logger.info(f"Current directory: {current_dir}")
    logger.info("FastAPI app created successfully")

    yield

    logger.info("KnowledgeForge API shutting down...")


openapi_tags = [
    {
        "name": "code-extraction",
        "description": (
            "Extract C4 architecture model (Context, Container, Component levels) "
            "from source repositories. Returns an architecture graph for visualization."
        ),
    },
    {
        "name": "health",
        "description": "Liveness and readiness probes for the API and its dependencies.",
    },
    {
        "name": "websocket",
        "description": "WebSocket endpoint for real-time task progress updates.",
    },
]

# Create FastAPI app instance
app = FastAPI(
    title="KnowledgeForge API",
    description=(
        "**KnowledgeForge** automatically extracts C4 architecture models "
        "from source code repositories.\n\n"
        "## Key capabilities\n"
        "- **C4 extraction**: builds Context → Container → Component levels from "
        "GitHub repos or uploaded ZIP archives\n"
        "- **Real-time updates**: WebSocket channel streams extraction progress\n\n"
        "## Authentication\n"
        "No authentication required for local / dev deployments. "
        "Set `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY` environment variables to enable LLM enrichment."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request-ID middleware (must be added after CORS so it wraps all requests)
app.add_middleware(RequestIDMiddleware)

# Import and include all route modules
try:
    from app.endpoint.v1.routes import (
        health,
        websocket,
        code_extraction,
    )

    app.include_router(health.router, prefix="/api/v1/health")
    app.include_router(code_extraction.router, prefix="/api/v1/code")
    app.include_router(websocket.router)  # WebSocket doesn't need prefix

    logger.info("All route modules loaded successfully")

except ImportError as e:
    logger.error(f"Failed to import route modules: {e}")
    logger.error("Please check that all route files exist and import paths are correct")
    raise
except Exception as e:
    logger.error(f"Unexpected error loading routes: {e}")
    raise


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat(),
        },
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "KnowledgeForge API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs",
        "health": "/api/v1/health/",
    }


# Health check endpoint (additional to the routes)
@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    try:
        # Load configuration
        config = get_config()

        # Run the application
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            reload=False,  # Disable reload for now to avoid import issues
            log_level=config.logging.level.lower(),
            access_log=True,
        )

    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        sys.exit(1)
