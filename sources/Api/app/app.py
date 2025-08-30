"""KnowledgeForge Ontology Extraction API - Main Application."""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uvicorn

from .core.config import get_settings
from .endpoint.v1.routes import health, data, extraction, semantic_queries


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting KnowledgeForge Ontology Extraction API...")
    
    try:
        # Load configuration
        config = get_settings()
        logger.info(f"Configuration loaded successfully: {config.get_summary()}")
        
        # Initialize services (database connections, etc.)
        # This would include Neo4j connection, LLM service initialization, etc.
        logger.info("Services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down KnowledgeForge Ontology Extraction API...")
    
    # Cleanup resources
    # This would include closing database connections, etc.
    logger.info("Cleanup completed")


# Create FastAPI application
app = FastAPI(
    title="KnowledgeForge Ontology Extraction API",
    description="AI-powered ontology extraction and relationship discovery from structured data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your security requirements
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure based on your security requirements
)


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "details": exc.errors(),
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if get_settings().debug else "An unexpected error occurred",
            "path": str(request.url)
        }
    )


# Include API routes
app.include_router(health.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")
app.include_router(extraction.router, prefix="/api/v1")
app.include_router(semantic_queries.router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    try:
        config = get_settings()
        return {
            "name": "KnowledgeForge Ontology Extraction API",
            "version": "1.0.0",
            "description": "AI-powered ontology extraction and relationship discovery",
            "status": "running",
            "environment": config.environment,
            "docs_url": "/docs",
            "health_check": "/api/v1/health",
            "endpoints": {
                "health": "/api/v1/health",
                "data": "/api/v1/entities",
                "extraction": "/api/v1/extract",
                "semantic_queries": "/api/v1/api/semantic-queries"
            }
        }
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        return {
            "name": "KnowledgeForge Ontology Extraction API",
            "version": "1.0.0",
            "status": "error",
            "error": str(e)
        }


# Health check endpoint (additional to the one in routes)
@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "KnowledgeForge API"}


# Configuration endpoint
@app.get("/config")
async def get_config():
    """Get current configuration (debug endpoint)."""
    try:
        config = get_settings()
        if config.debug:
            return config.get_summary()
        else:
            return {"message": "Configuration details not available in production mode"}
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("KnowledgeForge API starting up...")
    
    try:
        # Validate configuration
        config = get_settings()
        validation = config.validate_config()
        
        if not validation['valid']:
            logger.error(f"Configuration validation failed: {validation['errors']}")
            raise ValueError("Invalid configuration")
        
        if validation['warnings']:
            logger.warning(f"Configuration warnings: {validation['warnings']}")
        
        logger.info("Configuration validated successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("KnowledgeForge API shutting down...")


if __name__ == "__main__":
    # Run the application directly if this file is executed
    try:
        config = get_settings()
        uvicorn.run(
            "app.app:app",
            host="0.0.0.0",
            port=8000,
            reload=config.debug,
            log_level=config.logging.level.lower(),
            access_log=True
        )
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
