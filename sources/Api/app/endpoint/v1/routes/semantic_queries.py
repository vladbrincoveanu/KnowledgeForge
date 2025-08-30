from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
import uuid
from datetime import datetime

from ....domain.services.semantic_query_service import SemanticQueryService
from ....domain.models.semantic_queries import (
    SemanticQuery, QueryNode, QueryEdge, QueryNodeType, QueryEdgeType,
    ExportFormat, QueryTranslation, QueryExport, QueryInsight
)
from ....infrastructure.llm.llm_analyzer import LLMAnalyzer

router = APIRouter(prefix="/api/semantic-queries", tags=["semantic-queries"])

# Dependency to get the semantic query service
def get_semantic_query_service():
    llm_analyzer = LLMAnalyzer()  # In production, this should be injected
    return SemanticQueryService(llm_analyzer)


@router.post("/", response_model=SemanticQuery)
async def create_semantic_query(
    name: str,
    description: str,
    metadata: Dict[str, Any] = None,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Create a new semantic query"""
    try:
        query = service.create_query(name, description, metadata)
        return query
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[SemanticQuery])
async def list_semantic_queries(
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """List all semantic queries"""
    try:
        return service.list_queries()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{query_id}", response_model=SemanticQuery)
async def get_semantic_query(
    query_id: str,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Get a specific semantic query by ID"""
    try:
        query = service.get_query(query_id)
        if not query:
            raise HTTPException(status_code=404, detail="Query not found")
        return query
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{query_id}")
async def delete_semantic_query(
    query_id: str,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Delete a semantic query"""
    try:
        success = service.delete_query(query_id)
        if not success:
            raise HTTPException(status_code=404, detail="Query not found")
        return {"message": "Query deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{query_id}/nodes", response_model=QueryNode)
async def add_node_to_query(
    query_id: str,
    node: QueryNode,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Add a node to a semantic query"""
    try:
        # Ensure node has an ID
        if not node.id:
            node.id = str(uuid.uuid4())
        
        # Ensure node has timestamps
        now = datetime.now()
        if not node.created_at:
            node.created_at = now
        node.updated_at = now
        
        added_node = service.add_node(query_id, node)
        return added_node
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{query_id}/nodes/{node_id}")
async def remove_node_from_query(
    query_id: str,
    node_id: str,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Remove a node from a semantic query"""
    try:
        success = service.remove_node(query_id, node_id)
        if not success:
            raise HTTPException(status_code=404, detail="Node not found")
        return {"message": "Node removed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{query_id}/edges", response_model=QueryEdge)
async def add_edge_to_query(
    query_id: str,
    edge: QueryEdge,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Add an edge to a semantic query"""
    try:
        # Ensure edge has an ID
        if not edge.id:
            edge.id = str(uuid.uuid4())
        
        # Ensure edge has timestamps
        now = datetime.now()
        if not edge.created_at:
            edge.created_at = now
        edge.updated_at = now
        
        added_edge = service.add_edge(query_id, edge)
        return added_edge
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{query_id}/edges/{edge_id}")
async def remove_edge_from_query(
    query_id: str,
    edge_id: str,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Remove an edge from a semantic query"""
    try:
        success = service.remove_edge(query_id, edge_id)
        if not success:
            raise HTTPException(status_code=404, detail="Edge not found")
        return {"message": "Edge removed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{query_id}/translate", response_model=QueryTranslation)
async def translate_query_to_natural_language(
    query_id: str,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Translate visual query to natural language using AI"""
    try:
        translation = await service.translate_to_natural_language(query_id)
        return translation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{query_id}/insights", response_model=List[QueryInsight])
async def generate_query_insights(
    query_id: str,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Generate AI insights from the semantic query"""
    try:
        insights = await service.generate_insights(query_id)
        return insights
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{query_id}/export", response_model=QueryExport)
async def export_query(
    query_id: str,
    export_format: ExportFormat,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Export query in various formats"""
    try:
        export = service.export_query(query_id, export_format)
        return export
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export-formats")
async def get_export_formats():
    """Get list of supported export formats"""
    return {
        "formats": [
            {"value": format.value, "label": format.value.upper(), "description": f"Export as {format.value}"}
            for format in ExportFormat
        ]
    }


@router.get("/node-types")
async def get_node_types():
    """Get list of available node types"""
    return {
        "node_types": [
            {"value": node_type.value, "label": node_type.value.replace('_', ' ').title(), "description": f"Node type: {node_type.value}"}
            for node_type in QueryNodeType
        ]
    }


@router.get("/edge-types")
async def get_edge_types():
    """Get list of available edge types"""
    return {
        "edge_types": [
            {"value": edge_type.value, "label": edge_type.value.replace('_', ' ').title(), "description": f"Edge type: {edge_type.value}"}
            for edge_type in QueryEdgeType
        ]
    }


@router.post("/{query_id}/validate")
async def validate_query(
    query_id: str,
    service: SemanticQueryService = Depends(get_semantic_query_service)
):
    """Validate a semantic query for completeness and correctness"""
    try:
        query = service.get_query(query_id)
        if not query:
            raise HTTPException(status_code=404, detail="Query not found")
        
        # Basic validation
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        # Check if query has nodes
        if not query.nodes:
            validation_result["is_valid"] = False
            validation_result["errors"].append("Query must have at least one node")
        
        # Check if table nodes exist
        table_nodes = [n for n in query.nodes if n.node_type == QueryNodeType.TABLE]
        if not table_nodes:
            validation_result["warnings"].append("No table nodes found - consider adding data sources")
        
        # Check for orphaned edges
        node_ids = {n.id for n in query.nodes}
        orphaned_edges = []
        for edge in query.edges:
            if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
                orphaned_edges.append(edge.id)
        
        if orphaned_edges:
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"Found {len(orphaned_edges)} edges with missing nodes")
        
        # Check for cycles (simplified)
        if len(query.edges) > 0:
            validation_result["suggestions"].append("Consider adding filters to limit data scope")
        
        return validation_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
