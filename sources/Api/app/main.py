"""Main FastAPI application for KnowledgeForge API."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from utils.config import config
from endpoint.v1.routes import health, data, extraction, semantic_queries


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logging.info("Starting KnowledgeForge API...")
    logging.info(f"Environment: {config.environment}")
    logging.info(f"Debug mode: {config.debug}")
    logging.info(f"Neo4j: {config.get_neo4j_connection_string()}")
    logging.info(f"LLM Server: {config.lmstudio.base_url}")
    
    yield
    
    # Shutdown
    logging.info("Shutting down KnowledgeForge API...")


# Create FastAPI app
app = FastAPI(
    title="KnowledgeForge API",
    description="AI-powered ontology extraction and knowledge graph management",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
if config.security.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.security.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if config.security.trusted_hosts:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=config.security.trusted_hosts
    )

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(data.router, prefix="/api/v1", tags=["data"])
app.include_router(extraction.router, prefix="/api/v1", tags=["extraction"])
app.include_router(semantic_queries.router, prefix="/api/v1", tags=["semantic-queries"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "KnowledgeForge API",
        "version": "1.0.0",
        "environment": config.environment,
        "status": "running"
    }


@app.get("/config")
async def get_config_info():
    """Get configuration information (for debugging)."""
    if not config.debug:
        raise HTTPException(status_code=403, detail="Configuration endpoint disabled in production")
    
    return {
        "environment": config.environment,
        "debug": config.debug,
        "neo4j_uri": config.neo4j.uri,
        "llm_server": config.lmstudio.base_url,
        "model": config.lmstudio.model_name,
        "confidence_threshold": config.extraction.confidence_threshold,
        "batch_size": config.extraction.batch_size
    }
