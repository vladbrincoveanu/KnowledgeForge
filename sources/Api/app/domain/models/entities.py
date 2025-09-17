"""Data models for ontology extraction."""

from enum import Enum
from typing import Any, Optional, List, Dict
import os
import re

import numpy as np
from pydantic import BaseModel, Field, field_validator


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
    elif hasattr(value, "dtype"):  # Handle pandas Series, DataFrames, etc.
        try:
            return convert_numpy_types(value.tolist())
        except Exception:
            return str(value)
    elif hasattr(value, "item"):  # Handle scalar numpy types
        try:
            return value.item()
        except Exception:
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
    MEASUREMENT = "measurement"


class Attribute(BaseModel):
    """Represents an attribute of an entity."""
    
    name: str
    data_type: DataType
    source_column: str
    confidence: float = Field(ge=0.0, le=1.0)
    statistics: dict[str, Any] = Field(default_factory=dict)
    sample_values: list[Any] = Field(default_factory=list)

    @field_validator("statistics", "sample_values", mode="before")
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class ColumnProfile(BaseModel):
    """Profile information for a single column."""

    name: str
    data_type: DataType
    null_count: int
    unique_count: int
    sample_values: list[Any] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sample_values", "statistics", mode="before")
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class DatasetProfile(BaseModel):
    """Complete profile of a dataset."""

    file_path: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", mode="before")
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class Entity(BaseModel):
    """Represents an entity in the ontology."""

    id: Optional[str] = None
    name: str
    entity_type: str = "table"
    attributes: List[Attribute] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    source_table: str

    @field_validator("attributes", mode="before")
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class Relationship(BaseModel):
    """Represents a relationship between entities."""

    id: Optional[str] = None
    source_entity_id: Optional[str] = None
    target_entity_id: Optional[str] = None
    relationship_type: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    source_columns: list[str] = Field(default_factory=list)

    @field_validator("attributes", mode="before")
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class Ontology(BaseModel):
    """Complete ontology representation."""

    entities: list[Entity]
    relationships: list[Relationship]
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    version: str = "1.0"

    @field_validator("metadata", mode="before")
    @classmethod
    def convert_numpy_types(cls, v):
        return convert_numpy_types(v)


class ExtractionConfig(BaseModel):
    """Configuration for ontology extraction."""

    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    max_entities_per_column: int = Field(default=100, ge=1)
    relationship_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    use_llm: bool = True
    llm_model: str = ""
    batch_size: int = Field(default=1000, ge=1)
    enable_semantic_similarity: bool = True


def infer_entity_name(file_path: str) -> str:
    """
    Infer the entity name from the file path.
    Removes file extension, UUID prefixes, and pluralization.
    """
    filename = os.path.basename(file_path)
    name = os.path.splitext(filename)[0]
    
    # Remove UUID prefix if present (format: uuid_filename)
    # UUID pattern: 8-4-4-4-12 characters separated by hyphens
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_'
    name = re.sub(uuid_pattern, '', name, flags=re.IGNORECASE)
    
    # Remove common plural endings
    if name.endswith('s'):
        name = name[:-1]
    elif name.endswith('ies'):
        name = name[:-3] + 'y'
    
    # Convert to title case
    name = re.sub(r'[_-]', ' ', name)
    name = name.title()
    name = re.sub(r'\s+', '', name)
    
    result = name or "Entity"
    print(f"DEBUG: infer_entity_name('{file_path}') -> '{result}'")
    return result


def extract_ontology_from_profile(profile: DatasetProfile, config: ExtractionConfig) -> Ontology:
    """
    Extract ontology from dataset profile using table-level entity recognition.
    """
    # Infer entity name from file path
    entity_name = infer_entity_name(profile.file_path)
    
    # Convert column profiles to attributes
    attributes = []
    for column in profile.columns:
        attribute = Attribute(
            name=column.name,
            data_type=column.data_type,
            source_column=column.name,
            confidence=0.95,  # High confidence for direct column mapping
            statistics=column.statistics,
            sample_values=column.sample_values
        )
        attributes.append(attribute)
    
    # Create the main entity
    entity = Entity(
        name=entity_name,
        attributes=attributes,
        confidence=1.0,  # High confidence for table-level entity
        source_table=profile.file_path
    )
    
    # Create ontology with single entity and no relationships
    ontology = Ontology(
        entities=[entity],
        relationships=[],
        metadata=profile.metadata,
        created_at=profile.created_at
    )
    
    return ontology