from typing import List, Dict, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class QueryNodeType(Enum):
    """Types of nodes that can be used in semantic queries"""
    TABLE = "table"
    FIELD = "field"
    AGGREGATION = "aggregation"
    FILTER = "filter"
    JOIN = "join"
    SUBQUERY = "subquery"
    CUSTOM = "custom"


class QueryEdgeType(Enum):
    """Types of edges that can connect query nodes"""
    SELECT = "select"
    WHERE = "where"
    JOIN = "join"
    GROUP_BY = "group_by"
    ORDER_BY = "order_by"
    HAVING = "having"
    UNION = "union"
    INTERSECT = "intersect"


class ExportFormat(Enum):
    """Supported export formats for semantic queries"""
    SQL = "sql"
    PYTHON = "python"
    R = "r"
    NATURAL_LANGUAGE = "natural_language"
    JSON = "json"


@dataclass
class QueryNode:
    """Represents a node in the semantic query graph"""
    id: str
    name: str
    node_type: QueryNodeType
    metadata: Dict[str, Any]
    position: Dict[str, float]  # x, y coordinates
    properties: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class QueryEdge:
    """Represents an edge connecting query nodes"""
    id: str
    source_node_id: str
    target_node_id: str
    edge_type: QueryEdgeType
    properties: Dict[str, Any]
    conditions: Optional[Dict[str, Any]] = None
    created_at: datetime = None
    updated_at: datetime = None


@dataclass
class SemanticQuery:
    """Represents a complete semantic query built visually"""
    id: str
    name: str
    description: str
    nodes: List[QueryNode]
    edges: List[QueryEdge]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    version: str = "1.0.0"


@dataclass
class QueryTranslation:
    """AI-generated translation of visual query to natural language"""
    query_id: str
    natural_language: str
    confidence_score: float
    suggestions: List[str]
    generated_at: datetime


@dataclass
class QueryExport:
    """Exported query in various formats"""
    query_id: str
    export_format: ExportFormat
    content: str
    metadata: Dict[str, Any]
    exported_at: datetime


@dataclass
class QueryInsight:
    """AI-generated insights from the semantic query"""
    query_id: str
    insight_type: str
    description: str
    confidence_score: float
    recommendations: List[str]
    generated_at: datetime


@dataclass
class VisualQueryBuilder:
    """Configuration for the visual query builder interface"""
    available_node_types: List[QueryNodeType]
    available_edge_types: List[QueryEdgeType]
    supported_export_formats: List[ExportFormat]
    ui_config: Dict[str, Any]
    validation_rules: Dict[str, Any]
