"""Data access endpoints for entities, relationships, and graph visualization."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

# Import actual backend services
from app.infrastructure.graph.neo4j_manager import Neo4jGraphManager
from app.infrastructure.storage.metadata_store import MetadataStore
from utils.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])


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


def get_metadata_store():
    """Get metadata store instance."""
    config = get_config()
    return MetadataStore(config=config)


@router.get("/entities")
async def list_entities(
    task_id: Optional[str] = Query(None, description="Task ID to filter entities"),
    limit: int = Query(100, ge=1, le=1000, description="Number of entities to return"),
    offset: int = Query(0, ge=0, description="Number of entities to skip"),
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
):
    """List extracted entities with pagination."""
    try:
        # Use actual Neo4j manager to retrieve entities
        entities = neo4j_manager.get_entities(
            limit=limit, offset=offset, task_id=task_id
        )

        # Get total count for pagination
        total_count = neo4j_manager.count_entities(task_id=task_id)

        return {
            "entities": [entity if isinstance(entity, dict) else entity.dict() for entity in entities],
            "total_count": total_count,
            "extraction_metadata": {
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
            },
        }

    except Exception as e:
        logger.error(f"Failed to retrieve entities: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve entities: {str(e)}"
        )


@router.get("/relationships")
async def list_relationships(
    task_id: Optional[str] = Query(None, description="Task ID to filter relationships"),
    limit: int = Query(
        100, ge=1, le=1000, description="Number of relationships to return"
    ),
    offset: int = Query(0, ge=0, description="Number of relationships to skip"),
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
):
    """List discovered relationships with pagination."""
    try:
        # Use actual Neo4j manager to retrieve relationships
        relationships = neo4j_manager.get_relationships(
            limit=limit, offset=offset, task_id=task_id
        )

        # Get total count for pagination using the proper count_relationships method
        total_count = neo4j_manager.count_relationships(task_id=task_id)

        return {
            "relationships": relationships,
            "total_count": total_count,
            "discovery_metadata": {
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
            },
        }

    except Exception as e:
        logger.error(f"Failed to retrieve relationships: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve relationships: {str(e)}"
        )


@router.post("/feedback")
async def submit_feedback(
    entity_id: Optional[str] = None,
    relationship_id: Optional[str] = None,
    feedback_type: str = "correction",
    feedback_value: str = "",
    confidence_delta: float = 0.0,
    user_id: Optional[str] = None,
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """Submit user feedback for entities or relationships."""
    try:
        feedback_id = str(uuid.uuid4())

        # Store feedback in metadata store
        feedback_data = {
            "feedback_id": feedback_id,
            "entity_id": entity_id,
            "relationship_id": relationship_id,
            "feedback_type": feedback_type,
            "feedback_value": feedback_value,
            "confidence_delta": confidence_delta,
            "user_id": user_id,
            "submitted_at": datetime.now().isoformat(),
        }

        # Extract individual fields for the add_user_feedback method
        feedback_id = metadata_store.add_user_feedback(
            entity_id=feedback_data.get("entity_id"),
            relationship_id=feedback_data.get("relationship_id"),
            feedback_type=feedback_data.get("feedback_type"),
            feedback_value=feedback_data.get("feedback_value"),
            confidence_adjustment=feedback_data.get("confidence_delta"),
            user_id=feedback_data.get("user_id"),
            feedback_source="api",
        )

        return {
            "feedback_id": feedback_id,
            "status": "received",
            "message": "Feedback submitted successfully",
        }

    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to submit feedback: {str(e)}"
        )


@router.get("/graph/visualize")
async def get_graph_visualization(
    task_id: Optional[str] = None, neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager)
):
    """Return graph data for visualization in the format expected by the frontend."""
    try:
        # Use actual Neo4j manager to get graph data
        graph_data = neo4j_manager.get_graph_visualization_data(task_id)

        # Convert entities to the format expected by frontend
        nodes = []
        for entity in graph_data.get("graph_structure", {}).get("entities", []):
            node = {
                "id": entity["id"],
                "label": entity["name"],
                "type": "entity",
                "properties": {
                    "entityType": entity["entity_type"],
                    "confidence": entity["confidence"],
                    "sourceColumns": entity.get("source_columns", []),
                    "sourceValue": entity.get("source_value", "N/A"),
                    "attributes": entity.get("attributes", {}),
                    "createdAt": entity.get("created_at"),
                    "updatedAt": entity.get("updated_at"),
                    "sourceFile": entity.get("source_file", "Unknown"),
                    "extractionTimestamp": entity.get("extraction_timestamp")
                }
            }
            nodes.append(node)

        # Convert relationships to the format expected by frontend
        edges = []
        for relationship in graph_data.get("graph_structure", {}).get("relationships", []):
            edge = {
                "id": relationship["id"],
                "source": relationship["source_id"],
                "target": relationship["target_id"],
                "type": relationship["type"],
                "properties": {
                    "confidence": relationship["confidence"]
                }
            }
            edges.append(edge)

        return {
            "nodes": nodes,
            "edges": edges,
            "cypher_queries": graph_data.get("cypher_queries", []),
            "graph_metadata": {
                "task_id": task_id,
                "entity_count": graph_data.get("entity_count", 0),
                "relationship_count": graph_data.get("relationship_count", 0),
            },
            "node_count": graph_data.get("node_count", 0),
            "edge_count": graph_data.get("edge_count", 0),
        }

    except Exception as e:
        logger.error(f"Failed to generate graph visualization: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate graph visualization: {str(e)}"
        )


@router.get("/config")
async def get_current_config():
    """Get the current configuration being used by the API."""
    try:
        config = get_config()
        return {
            "neo4j": {
                "uri": config.neo4j.uri,
                "database": config.neo4j.database,
                "max_connection_pool_size": config.neo4j.max_connection_pool_size,
            },
            "lmstudio": {
                "base_url": config.lmstudio.base_url,
                "model_name": config.lmstudio.model_name,
                "use_embeddings": config.lmstudio.use_embeddings,
            },
            "extraction": {
                "confidence_threshold": config.extraction.confidence_threshold,
                "max_entities_per_column": config.extraction.max_entities_per_column,
                "relationship_threshold": config.extraction.relationship_threshold,
            },
            "metadata_storage": {
                "cache_enabled": config.metadata_storage.cache_enabled,
            },
            "environment": "development",
            "debug": True,
        }
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        return {"error": str(e)}


@router.get("/entities/{entity_id}")
async def get_entity_details(
    entity_id: str, neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager)
):
    """Get detailed information about a specific entity."""
    try:
        entity = neo4j_manager.get_entity_by_id(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        return entity.dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get entity details: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get entity details: {str(e)}"
        )


@router.get("/relationships/{relationship_id}")
async def get_relationship_details(
    relationship_id: str, neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager)
):
    """Get detailed information about a specific relationship."""
    try:
        relationship = neo4j_manager.get_relationship_by_id(relationship_id)
        if not relationship:
            raise HTTPException(status_code=404, detail="Relationship not found")

        return relationship.dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get relationship details: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get relationship details: {str(e)}"
        )


@router.get("/search")
async def search_entities_and_relationships(
    query: str = Query(..., description="Search query"),
    search_type: str = Query(
        "both", description="Search type: entities, relationships, or both"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
):
    """Search for entities and relationships using text search."""
    try:
        search_results = neo4j_manager.search_graph(query, search_type, limit)

        return {
            "query": query,
            "search_type": search_type,
            "results": search_results,
            "total_count": len(search_results),
            "search_metadata": {
                "query_time": search_results.get("query_time", 0),
                "index_used": search_results.get("index_used", False),
            },
        }

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/profile")
async def get_data_profile(
    neo4j_manager: Neo4jGraphManager = Depends(get_neo4j_manager),
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """Get a profile of the current data in the system."""
    try:
        # Get basic graph statistics
        graph_stats = neo4j_manager.get_graph_statistics()
        
        # Get metadata store information
        db_info = metadata_store.get_database_info()
        
        return {
            "graph_profile": {
                "total_entities": graph_stats.get("total_nodes", 0),
                "total_relationships": graph_stats.get("total_relationships", 0),
                "database_size_mb": graph_stats.get("database_size_mb", 0),
                "index_count": graph_stats.get("index_count", 0),
            },
            "metadata_profile": {
                "total_files_processed": db_info.get("total_files", 0),
                "total_tasks": db_info.get("total_tasks", 0),
                "completed_tasks": db_info.get("completed_tasks", 0),
                "failed_tasks": db_info.get("failed_tasks", 0),
            },
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Failed to get data profile: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get data profile: {str(e)}"
        )
