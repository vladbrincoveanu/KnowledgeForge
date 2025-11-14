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

# Lifespan context manager
from contextlib import asynccontextmanager

from utils.config import get_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logging.info("KnowledgeForge API starting up...")
    logging.info(f"Current directory: {current_dir}")
    logging.info("FastAPI app created successfully")

    yield

    # Shutdown
    logging.info("KnowledgeForge API shutting down...")


# Create FastAPI app instance
app = FastAPI(
    title="KnowledgeForge API",
    description="A semantic ontology extraction API for CSV files",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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

# Import and include all route modules
try:
    from app.endpoint.v1.routes import (
        data,
        extraction,
        health,
        websocket,
        code_extraction,
    )

    app.include_router(health.router, prefix="/api/v1/health")
    app.include_router(data.router, prefix="/api/v1")
    app.include_router(extraction.router, prefix="/api/v1/extract")
    app.include_router(code_extraction.router, prefix="/api/v1/code")
    app.include_router(websocket.router)  # WebSocket doesn't need prefix

    logging.info("All route modules loaded successfully")

except ImportError as e:
    logging.error(f"Failed to import route modules: {e}")
    logging.error(
        "Please check that all route files exist and import paths are correct"
    )
    raise
except Exception as e:
    logging.error(f"Unexpected error loading routes: {e}")
    raise


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
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
