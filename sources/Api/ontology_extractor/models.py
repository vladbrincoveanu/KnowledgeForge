"""Data models for ontology extraction."""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class DataType(str, Enum):
    """Supported data types for columns."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    CATEGORICAL = "categorical"
    NUMERICAL = "numerical"


class ColumnProfile(BaseModel):
    """Profile information for a single column."""
    name: str
    data_type: DataType
    null_count: int
    unique_count: int
    sample_values: List[Any] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)


class DatasetProfile(BaseModel):
    """Complete profile of a dataset."""
    file_path: str
    row_count: int
    column_count: int
    columns: List[ColumnProfile]
    created_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Entity(BaseModel):
    """Represents an entity in the ontology."""
    id: str
    name: str
    entity_type: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    source_column: Optional[str] = None
    source_value: Optional[str] = None


class Relationship(BaseModel):
    """Represents a relationship between entities."""
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    source_columns: List[str] = Field(default_factory=list)


class Ontology(BaseModel):
    """Complete ontology representation."""
    entities: List[Entity]
    relationships: List[Relationship]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    version: str = "1.0"


class ExtractionConfig(BaseModel):
    """Configuration for ontology extraction."""
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    max_entities_per_column: int = Field(default=100, ge=1)
    relationship_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    use_llm: bool = True
    llm_model: str = "llama2"
    batch_size: int = Field(default=1000, ge=1)
    enable_semantic_similarity: bool = True
