"""Data models for ontology extraction."""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import numpy as np


def convert_numpy_types(value: Any) -> Any:
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(value, np.integer):
        return int(value)
    elif isinstance(value, np.floating):
        return float(value)
    elif isinstance(value, np.bool_):
        return bool(value)
    elif isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, np.dtype):
        return str(value)
    elif isinstance(value, dict):
        return {k: convert_numpy_types(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [convert_numpy_types(item) for item in value]
    elif hasattr(value, 'dtype'):  # Handle pandas Series, DataFrames, etc.
        try:
            return convert_numpy_types(value.tolist())
        except:
            return str(value)
    elif hasattr(value, 'item'):  # Handle scalar numpy types
        try:
            return value.item()
        except:
            return str(value)
    return value


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
    
    @field_validator('sample_values', 'statistics', mode='before')
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class DatasetProfile(BaseModel):
    """Complete profile of a dataset."""
    file_path: str
    row_count: int
    column_count: int
    columns: List[ColumnProfile]
    created_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('metadata', mode='before')
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class Entity(BaseModel):
    """Represents an entity in the ontology."""
    id: str
    name: str
    entity_type: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    source_column: Optional[str] = None
    source_value: Optional[str] = None
    
    @field_validator('attributes', mode='before')
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class Relationship(BaseModel):
    """Represents a relationship between entities."""
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    source_columns: List[str] = Field(default_factory=list)
    
    @field_validator('attributes', mode='before')
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class Ontology(BaseModel):
    """Complete ontology representation."""
    entities: List[Entity]
    relationships: List[Relationship]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    version: str = "1.0"
    
    @field_validator('metadata', mode='before')
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class ExtractionConfig(BaseModel):
    """Configuration for ontology extraction."""
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    max_entities_per_column: int = Field(default=100, ge=1)
    relationship_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    use_llm: bool = True
    llm_model: str = "llama2"
    batch_size: int = Field(default=1000, ge=1)
    enable_semantic_similarity: bool = True
