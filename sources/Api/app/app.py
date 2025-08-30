"""
KnowledgeForge API - Clean, focused FastAPI application for ontology extraction
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Import the new API router
from app.endpoint.v1 import api_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="KnowledgeForge Ontology Extraction API",
    description="Semantic ontology extraction from CSV files with local LLM support",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Include API routes
app.include_router(api_router)

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "KnowledgeForge Ontology Extraction API",
        "version": "1.0.0",
        "description": "Semantic ontology extraction from CSV files with local LLM support",
        "endpoints": {
            "upload": "/api/v1/extract/upload",
            "extract": "/api/v1/extract/",
            "entities": "/api/v1/entities",
            "relationships": "/api/v1/relationships",
            "feedback": "/api/v1/feedback",
            "graph_visualization": "/api/v1/graph/visualize",
            "metrics": "/api/v1/health/metrics",
            "health": "/api/v1/health/",
            "health_public": "/api/v1/health/public",
            "ready": "/api/v1/health/ready",
            "semantic_queries": "/api/v1/semantic-queries",
            "documentation": "/docs"
        }
    }

@app.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify API is working."""
    from datetime import datetime
    return {"message": "API is working", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
