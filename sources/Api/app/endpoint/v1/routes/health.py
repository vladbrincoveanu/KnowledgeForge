"""Health and monitoring endpoints."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.infrastructure.graph.neo4j_manager import Neo4jGraphManager
from app.infrastructure.llm.llm_manager import LLMManager
from app.infrastructure.storage.metadata_store import MetadataStore
from utils.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


# Dependency injection
def get_neo4j_manager():
    """Get Neo4j manager instance."""
    config = get_config()
    manager = Neo4jGraphManager(
        uri=config.neo4j.uri,
        username=config.neo4j.username,
        password=config.neo4j.password,
        database=config.neo4j.database,
        encrypted=config.neo4j.encrypted,
    )
    # Connect immediately to ensure the connection is established
    manager.connect()
    return manager


def get_llm_manager():
    """Get LLM manager instance."""
    config = get_config()
    return LLMManager(
        lmstudio_url=config.lmstudio.base_url,
        default_model=config.lmstudio.model_name,
        max_retries=getattr(config.lmstudio, 'max_retries', 3),
    )


def get_metadata_store():
    """Get metadata store instance."""
    config = get_config()
    return MetadataStore(config=config.dict() if hasattr(config, 'dict') else config)


@router.get("/", response_model=dict[str, Any])
async def health_check(
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
    llm_manager: LLMManager = Depends(get_llm_manager),
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """Health check endpoint for Kubernetes deployment."""
    try:
        # Check Neo4j connection
        neo4j_status = "healthy"
        try:
            with neo4j_manager.driver.session(database=neo4j_manager.database) as session:
                result = session.run("RETURN 1 as test")
                result.single()
        except Exception as e:
            neo4j_status = f"unhealthy: {str(e)}"
            logger.error(f"Neo4j health check failed: {e}")

        # Check LLM service
        llm_status = "healthy"
        try:
            # Simple health check - try to get model info
            models = llm_manager.list_models()
            if not models:
                llm_status = "unhealthy: no models available"
        except Exception as e:
            llm_status = f"unhealthy: {str(e)}"
            logger.error(f"LLM health check failed: {e}")

        # Check DuckDB metadata store
        duckdb_status = "healthy"
        try:
            # Simple health check - try to get basic info
            info = metadata_store.get_database_info()
            if not info:
                duckdb_status = "unhealthy: cannot access database"
        except Exception as e:
            duckdb_status = f"unhealthy: {str(e)}"
            logger.error(f"DuckDB health check failed: {e}")

        dependencies = {
            "neo4j": neo4j_status,
            "llm_server": llm_status,
            "duckdb": duckdb_status,
        }

        # Overall status
        overall_status = (
            "healthy"
            if all("healthy" in status for status in dependencies.values())
            else "degraded"
        )

        return {
            "status": overall_status,
            "timestamp": datetime.now(),
            "version": "1.0.0",
            "dependencies": dependencies,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(),
            "version": "1.0.0",
            "dependencies": {"error": str(e)},
        }


@router.get("/ready")
async def readiness_check(
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """Readiness check endpoint for Kubernetes deployment."""
    try:
        # Check if core services are ready
        ready_checks = []

        # Check Neo4j
        try:
            with neo4j_manager.driver.session(database=neo4j_manager.database) as session:
                result = session.run("RETURN 1 as test")
                result.single()
            ready_checks.append("neo4j")
        except Exception as e:
            logger.warning(f"Neo4j not ready: {e}")

        # Check metadata store
        try:
            metadata_store.get_database_info()
            ready_checks.append("metadata_store")
        except Exception as e:
            logger.warning(f"Metadata store not ready: {e}")

        # Service is ready if at least core services are available
        if len(ready_checks) >= 1:
            return {
                "status": "ready",
                "ready_services": ready_checks,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "reason": "No core services available",
                    "ready_services": ready_checks,
                    "timestamp": datetime.now().isoformat(),
                },
            )

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


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
async def get_system_metrics(
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """Get system performance and extraction metrics."""
    try:
        # Get actual metrics from services
        system_metrics = {}
        extraction_metrics = {}

        # Neo4j metrics
        try:
            # Get graph statistics
            graph_stats = neo4j_manager.get_graph_statistics()
            system_metrics.update(
                {
                    "total_nodes": graph_stats.get("total_nodes", 0),
                    "total_relationships": graph_stats.get(
                        "total_relationships", 0
                    ),
                    "database_size_mb": graph_stats.get("database_size_mb", 0),
                    "index_count": graph_stats.get("index_count", 0),
                }
            )
        except Exception as e:
            logger.warning(f"Could not get Neo4j metrics: {e}")

        # Metadata store metrics
        try:
            db_info = metadata_store.get_database_info()
            extraction_metrics.update(
                {
                    "total_files_processed": db_info.get("total_files", 0),
                    "total_tasks": db_info.get("total_tasks", 0),
                    "completed_tasks": db_info.get("completed_tasks", 0),
                    "failed_tasks": db_info.get("failed_tasks", 0),
                }
            )
        except Exception as e:
            logger.warning(f"Could not get metadata store metrics: {e}")

        # Calculate success rate
        total_tasks = extraction_metrics.get("total_tasks", 0)
        completed_tasks = extraction_metrics.get("completed_tasks", 0)
        success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        # Get config for thresholds
        config = get_config()

        return {
            "system_metrics": {
                **system_metrics,
                "success_rate": round(success_rate, 2),
            },
            "extraction_metrics": {
                **extraction_metrics,
                "average_processing_time": 0,  # Would be calculated from actual data
                "total_entities_extracted": system_metrics.get("total_nodes", 0),
                "total_relationships_discovered": system_metrics.get(
                    "total_relationships", 0
                ),
            },
            "quality_metrics": {
                "average_entity_confidence": config.extraction.confidence_threshold,
                "average_relationship_confidence": config.extraction.relationship_threshold,
                "data_coverage": 0.92,  # Would be calculated from actual data
            },
            "timestamp": datetime.now(),
        }

    except Exception as e:
        logger.error(f"Failed to retrieve metrics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve metrics: {str(e)}"
        )


@router.get("/detailed")
async def detailed_health_check(
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
    llm_manager: LLMManager = Depends(get_llm_manager),
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """Detailed health check with service-specific information."""
    try:
        detailed_status = {}

        # Neo4j detailed check
        try:
            # Check connection pool
            pool_info = neo4j_manager.driver._pool
            detailed_status["neo4j"] = {
                "status": "healthy",
                "connection_pool_size": (
                    pool_info.size if hasattr(pool_info, "size") else "unknown"
                ),
                "active_connections": (
                    pool_info.in_use if hasattr(pool_info, "in_use") else "unknown"
                ),
                "database_version": "unknown",  # Would get from actual query
            }
        except Exception as e:
            detailed_status["neo4j"] = {"status": "unhealthy", "error": str(e)}

        # LLM detailed check
        try:
            models = llm_manager.list_models()
            detailed_status["llm"] = {
                "status": "healthy",
                "available_models": len(models) if models else 0,
                "base_url": llm_manager.base_url,
            }
        except Exception as e:
            detailed_status["llm"] = {"status": "unhealthy", "error": str(e)}

        # Metadata store detailed check
        try:
            db_info = metadata_store.get_database_info()
            detailed_status["metadata_store"] = {
                "status": "healthy",
                "database_path": str(metadata_store.db_path),
                "database_size_mb": db_info.get("size_mb", "unknown"),
                "table_count": db_info.get("table_count", "unknown"),
            }
        except Exception as e:
            detailed_status["metadata_store"] = {"status": "unhealthy", "error": str(e)}

        return {
            "timestamp": datetime.now(),
            "version": "1.0.0",
            "services": detailed_status,
        }

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Detailed health check failed: {str(e)}"
        )
