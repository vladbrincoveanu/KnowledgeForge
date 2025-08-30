"""Main entry point for the KnowledgeForge API."""

import uvicorn
import logging
from pathlib import Path
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime

# Add the current directory (sources/api) to the Python path so routes can access utils
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from utils.config import get_config

# Create FastAPI app instance
app = FastAPI(
    title="KnowledgeForge API",
    description="A semantic ontology extraction API for CSV files",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    logging.info("KnowledgeForge API starting up...")
    logging.info(f"Current directory: {current_dir}")
    logging.info("FastAPI app created successfully")

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
    from app.endpoint.v1.routes import health, data, extraction
    
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(data.router, prefix="/api/v1")
    app.include_router(extraction.router, prefix="/api/v1")
    
    logging.info("All route modules loaded successfully")
    
except ImportError as e:
    logging.error(f"Failed to import route modules: {e}")
    logging.error("Please check that all route files exist and import paths are correct")
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
            "timestamp": datetime.now().isoformat()
        }
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
        "health": "/api/v1/health/"
    }

# Health check endpoint (additional to the routes)
@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    try:
        # Load configuration
        config = get_config()
        
        # Run the application
        if config.debug:
            # Use import string for reload mode
            uvicorn.run(
                "app:app",
                host="0.0.0.0",
                port=8000,
                reload=True,
                log_level=config.logging.level.lower(),
                access_log=True
            )
        else:
            # Use app instance directly for production
            uvicorn.run(
                app,
                host="0.0.0.0",
                port=8000,
                reload=False,
                log_level=config.logging.level.lower(),
                access_log=True
            )
        
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        sys.exit(1)
