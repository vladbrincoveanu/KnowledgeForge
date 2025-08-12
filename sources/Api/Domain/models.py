"""
Domain Models

Core business entities and value objects for the data processing system.
Using Pydantic for validation, serialization, and automatic type conversion.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from pathlib import Path


class DataType(Enum):
    """Supported data types."""
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    UNKNOWN = "unknown"


class ColumnMetadata(BaseModel):
    """Metadata for a single column."""
    name: str = Field(..., description="Column name")
    position: int = Field(..., ge=0, description="Column position (0-indexed)")
    data_type: DataType = Field(..., description="Detected data type")
    subtype: str = Field(..., description="Specific subtype (e.g., int64, float64)")
    nullable: bool = Field(..., description="Whether the column contains null values")
    total_count: int = Field(..., ge=0, description="Total number of values")
    null_count: int = Field(..., ge=0, description="Number of null values")
    null_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of null values")
    unique_count: int = Field(..., ge=0, description="Number of unique values")
    min_value: Optional[Any] = Field(None, description="Minimum value in the column")
    max_value: Optional[Any] = Field(None, description="Maximum value in the column")
    max_length: Optional[int] = Field(None, ge=0, description="Maximum string length")
    sample_values: List[Any] = Field(default_factory=list, description="Sample values from the column")
    
    @field_validator('null_percentage')
    @classmethod
    def validate_null_percentage(cls, v):
        """Ensure null percentage is within valid range."""
        if v < 0 or v > 100:
            raise ValueError("Null percentage must be between 0 and 100")
        return v
    
    @field_validator('total_count')
    @classmethod
    def validate_total_count(cls, v, info):
        """Ensure total count is greater than or equal to null count."""
        if 'null_count' in info.data and v < info.data['null_count']:
            raise ValueError("Total count cannot be less than null count")
        return v


class SchemaSummary(BaseModel):
    """Summary of data schema."""
    numeric_columns_count: int = Field(..., ge=0, description="Number of numeric columns")
    categorical_columns_count: int = Field(..., ge=0, description="Number of categorical columns")
    datetime_columns_count: int = Field(..., ge=0, description="Number of datetime columns")
    boolean_columns_count: int = Field(..., ge=0, description="Number of boolean columns")
    numeric_columns: List[str] = Field(default_factory=list, description="List of numeric column names")
    categorical_columns: List[str] = Field(default_factory=list, description="List of categorical column names")
    datetime_columns: List[str] = Field(default_factory=list, description="List of datetime column names")
    boolean_columns: List[str] = Field(default_factory=list, description="List of boolean column names")


class FileInfo(BaseModel):
    """Information about the source file."""
    file_name: str = Field(..., description="Name of the file")
    file_path: str = Field(..., description="Full path to the file")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    file_size_mb: float = Field(..., ge=0.0, description="File size in megabytes")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    total_rows: int = Field(..., ge=0, description="Total number of rows")
    total_columns: int = Field(..., ge=0, description="Total number of columns")
    has_duplicates: bool = Field(..., description="Whether the file contains duplicate rows")
    duplicate_rows_count: int = Field(..., ge=0, description="Number of duplicate rows")
    extraction_timestamp: datetime = Field(..., description="When metadata was extracted")
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v):
        """Validate that the file path is absolute."""
        path = Path(v)
        return str(path.absolute())
    
    @field_validator('file_size_mb')
    @classmethod
    def validate_file_size_mb(cls, v):
        """Ensure file size is reasonable."""
        if v > 1000:  # 1GB limit
            raise ValueError("File size cannot exceed 1GB")
        return v


class DataRow(BaseModel):
    """A single row of data."""
    row_id: int = Field(..., ge=0, description="Unique row identifier")
    data: Dict[str, Any] = Field(..., description="Row data as key-value pairs")
    file_info: FileInfo = Field(..., description="Reference to file information")
    inserted_at: datetime = Field(..., description="When the row was inserted")


class FileMetadata(BaseModel):
    """Complete metadata for a file."""
    file_info: FileInfo = Field(..., description="File information")
    columns: Dict[str, ColumnMetadata] = Field(..., description="Column metadata by column name")
    schema_summary: SchemaSummary = Field(..., description="Schema summary")


class ProcessingResult(BaseModel):
    """Result of processing a file."""
    success: bool = Field(..., description="Whether processing was successful")
    file_path: str = Field(..., description="Path to the processed file")
    collection_name: str = Field(..., description="MongoDB collection name")
    rows_processed: int = Field(..., ge=0, description="Number of rows processed")
    rows_inserted: int = Field(..., ge=0, description="Number of rows inserted")
    metadata: FileMetadata = Field(..., description="File metadata")
    error: Optional[str] = Field(None, description="Error message if processing failed")
    
    @field_validator('rows_inserted')
    @classmethod
    def validate_rows_inserted(cls, v, info):
        """Ensure rows inserted is not greater than rows processed."""
        if 'rows_processed' in info.data and v > info.data['rows_processed']:
            raise ValueError("Rows inserted cannot be greater than rows processed")
        return v


class CollectionInfo(BaseModel):
    """Information about a MongoDB collection."""
    collection_name: str = Field(..., description="Name of the collection")
    document_count: int = Field(..., ge=0, description="Number of documents in the collection")
    storage_size: int = Field(..., ge=0, description="Storage size in bytes")
    index_size: int = Field(..., ge=0, description="Index size in bytes")
    metadata: Optional[FileMetadata] = Field(None, description="File metadata if available")
    created_at: Optional[datetime] = Field(None, description="When the collection was created")
    last_updated: Optional[datetime] = Field(None, description="When the collection was last updated")


class ProcessingStatus(BaseModel):
    """Status of data processing operations."""
    total_collections: int = Field(..., ge=0, description="Total number of collections")
    collections: List[CollectionInfo] = Field(default_factory=list, description="List of collection information")
    success: bool = Field(..., description="Whether the status retrieval was successful")
    error: Optional[str] = Field(None, description="Error message if status retrieval failed")

class ConnectionType(Enum):
    """Types of connections between datasets."""
    # Existing types
    SEMANTIC_MATCH = "semantic_match"
    FOREIGN_KEY = "foreign_key"
    BUSINESS_RULE = "business_rule"
    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    HIERARCHICAL = "hierarchical"
    TRANSACTIONAL = "transactional"
    
    # New enhanced types for better ontology capabilities
    CATEGORICAL = "categorical"      # e.g., product categories, customer segments
    SEQUENTIAL = "sequential"        # e.g., workflow steps, process sequences
    INFLUENCE = "influence"          # e.g., customer behavior influencing sales
    CORRELATION = "correlation"      # e.g., weather patterns affecting sales
    COMPOSITIONAL = "compositional"  # e.g., parts making up a whole
    DERIVATIVE = "derivative"        # e.g., calculated fields, aggregations
    CONDITIONAL = "conditional"      # e.g., if-then business rules
    EVOLUTIONARY = "evolutionary"    # e.g., data changes over time
    CONTEXTUAL = "contextual"        # e.g., environmental factors
    COLLABORATIVE = "collaborative"  # e.g., multi-entity partnerships

class ConnectionConfidence(Enum):
    """Confidence levels for connections."""
    HIGH = "high"      # 0.9 - 1.0
    MEDIUM = "medium"  # 0.7 - 0.89
    LOW = "low"        # 0.6 - 0.69


class LLMAnalysisResult(BaseModel):
    """Result of LLM analysis for connection detection."""
    reasoning: str = Field(..., description="LLM reasoning for the connection")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score from LLM")
    connection_type: ConnectionType = Field(..., description="Type of connection detected")
    business_context: str = Field(..., description="Business context explanation")
    suggested_join_strategy: str = Field(..., description="Suggested join strategy")
    potential_issues: List[str] = Field(default_factory=list, description="Potential issues with the connection")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for the connection")


class PotentialConnection(BaseModel):
    """A potential connection between two datasets."""
    id: str = Field(..., description="Unique identifier for the potential connection")
    source_collection: str = Field(..., description="Source collection name")
    target_collection: str = Field(..., description="Target collection name")
    source_column: str = Field(..., description="Source column name")
    target_column: str = Field(..., description="Target column name")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    connection_type: ConnectionType = Field(..., description="Type of connection")
    llm_analysis: LLMAnalysisResult = Field(..., description="LLM analysis result")
    created_at: datetime = Field(..., description="When the potential connection was created")
    status: str = Field(default="pending", description="Status: pending, accepted, rejected")


class MergedMetadata(BaseModel):
    """Metadata for a merged dataset."""
    total_columns: int = Field(..., ge=0, description="Total number of columns")
    shared_columns: int = Field(..., ge=0, description="Number of shared columns")
    unique_columns: int = Field(..., ge=0, description="Number of unique columns")
    data_types: List[str] = Field(..., description="List of data types")
    column_types: Dict[str, str] = Field(..., description="Column type mapping")
    connection_strength: float = Field(..., ge=0.0, le=1.0, description="Connection strength")
    merge_strategy: str = Field(..., description="Merge strategy")
    join_column: str = Field(..., description="Join column")
    data_quality_metrics: Dict[str, float] = Field(..., description="Data quality metrics")
    estimated_rows: int = Field(..., ge=0, description="Estimated number of rows")
    last_updated: datetime = Field(..., description="Last update timestamp")
    merge_complexity: str = Field(..., description="Merge complexity level")
    sample_data: Optional[Dict[str, Any]] = Field(None, description="Sample merged data")


class Edge(BaseModel):
    """An edge representing a connection between two datasets."""
    id: str = Field(..., description="Unique edge identifier")
    source_collection: str = Field(..., description="Source collection")
    target_collection: str = Field(..., description="Target collection")
    source_column: str = Field(..., description="Source column")
    target_column: str = Field(..., description="Target column")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    connection_type: ConnectionType = Field(..., description="Connection type")
    merged_metadata: MergedMetadata = Field(..., description="Merged metadata")
    llm_analysis: LLMAnalysisResult = Field(..., description="LLM analysis")
    status: str = Field(default="active", description="Edge status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="User who created the edge")


class ConnectionDetectionRequest(BaseModel):
    """Request for connection detection."""
    new_collection_name: str = Field(..., description="Name of the newly added collection")
    existing_collections: List[str] = Field(..., description="List of existing collection names")


class ConnectionDetectionResponse(BaseModel):
    """Response from connection detection."""
    success: bool = Field(..., description="Whether detection was successful")
    potential_connections: List[PotentialConnection] = Field(..., description="List of potential connections")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if failed")


class EdgeConfirmationRequest(BaseModel):
    """Request to confirm a potential connection as an edge.

    Supports two modes:
    - By referencing an existing potential connection stored in the backend (legacy path)
    - By directly providing the connection payload (frontend-driven analysis)
    """
    potential_connection_id: Optional[str] = Field(
        None, description="ID of the potential connection to confirm"
    )
    user_id: Optional[str] = Field(None, description="User ID who confirmed the connection")
    # Direct connection payload from the frontend (fallback if potential_connection_id is not found)
    connection: Optional[Dict[str, Any]] = Field(
        None, description="Direct connection payload when no backend potential connection exists"
    )
    # Optional corrected metadata coming from the UI
    corrected_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Corrected/augmented metadata to attach to the edge"
    )


class EdgeConfirmationResponse(BaseModel):
    """Response from edge confirmation."""
    success: bool = Field(..., description="Whether confirmation was successful")
    edge: Optional[Edge] = Field(None, description="Created edge if successful")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if failed") 

class BusinessOntology(BaseModel):
    """Business ontology representing domain knowledge and relationships."""
    id: str = Field(..., description="Unique identifier for the ontology")
    name: str = Field(..., description="Name of the business ontology")
    domain: str = Field(..., description="Business domain (e.g., e-commerce, healthcare, finance)")
    entities: List[str] = Field(default_factory=list, description="List of business entities")
    relationships: List[str] = Field(default_factory=list, description="List of business relationships")
    business_rules: List[str] = Field(default_factory=list, description="List of business rules")
    created_at: datetime = Field(..., description="When the ontology was created")
    updated_at: datetime = Field(..., description="When the ontology was last updated")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in the ontology")
    source_collections: List[str] = Field(default_factory=list, description="Collections used to generate this ontology")


class DataSourceSuggestion(BaseModel):
    """Suggestion for additional data sources that would enrich existing relationships."""
    id: str = Field(..., description="Unique identifier for the suggestion")
    suggested_source: str = Field(..., description="Name of the suggested data source")
    source_type: str = Field(..., description="Type of data source (e.g., API, database, file)")
    business_value: str = Field(..., description="Business value of adding this data source")
    enrichment_potential: float = Field(..., ge=0.0, le=1.0, description="Potential for enriching existing data")
    related_collections: List[str] = Field(default_factory=list, description="Collections this would enrich")
    suggested_columns: List[str] = Field(default_factory=list, description="Suggested columns to include")
    implementation_complexity: str = Field(..., description="Implementation complexity (low, medium, high)")
    priority: str = Field(..., description="Priority level (low, medium, high, critical)")
    created_at: datetime = Field(..., description="When the suggestion was created")


class BusinessActionRecommendation(BaseModel):
    """Recommendation for business actions based on discovered data patterns."""
    id: str = Field(..., description="Unique identifier for the recommendation")
    action_type: str = Field(..., description="Type of business action")
    title: str = Field(..., description="Title of the recommendation")
    description: str = Field(..., description="Detailed description of the recommendation")
    business_impact: str = Field(..., description="Expected business impact")
    confidence_level: str = Field(..., description="Confidence level (low, medium, high)")
    implementation_steps: List[str] = Field(default_factory=list, description="Steps to implement")
    estimated_effort: str = Field(..., description="Estimated effort required")
    priority: str = Field(..., description="Priority level (low, medium, high, critical)")
    related_patterns: List[str] = Field(default_factory=list, description="Data patterns that led to this recommendation")
    created_at: datetime = Field(..., description="When the recommendation was created")


class ComplexRelationshipExplanation(BaseModel):
    """Natural language explanation of complex data relationships."""
    id: str = Field(..., description="Unique identifier for the explanation")
    relationship_summary: str = Field(..., description="High-level summary of the relationship")
    detailed_explanation: str = Field(..., description="Detailed natural language explanation")
    business_context: str = Field(..., description="Business context and implications")
    technical_details: str = Field(..., description="Technical details of the relationship")
    visual_representation: str = Field(..., description="Suggested visual representation")
    related_insights: List[str] = Field(default_factory=list, description="Related business insights")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in the explanation")
    created_at: datetime = Field(..., description="When the explanation was created")


class EnhancedLLMAnalysisResult(BaseModel):
    """Enhanced LLM analysis result with business intelligence capabilities."""
    # Original fields
    reasoning: str = Field(..., description="LLM reasoning for the connection")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score from LLM")
    connection_type: ConnectionType = Field(..., description="Type of connection detected")
    business_context: str = Field(..., description="Business context explanation")
    suggested_join_strategy: str = Field(..., description="Suggested join strategy")
    potential_issues: List[str] = Field(default_factory=list, description="Potential issues with the connection")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for the connection")
    
    # New enhanced fields
    business_ontology: Optional[BusinessOntology] = Field(None, description="Generated business ontology")
    data_source_suggestions: List[DataSourceSuggestion] = Field(default_factory=list, description="Suggested data sources")
    business_actions: List[BusinessActionRecommendation] = Field(default_factory=list, description="Business action recommendations")
    relationship_explanation: Optional[ComplexRelationshipExplanation] = Field(None, description="Complex relationship explanation")
    pattern_insights: List[str] = Field(default_factory=list, description="Insights about data patterns")
    risk_assessment: str = Field(default="", description="Risk assessment of the connection")
    compliance_notes: List[str] = Field(default_factory=list, description="Compliance and governance notes")


class BusinessIntelligenceRequest(BaseModel):
    """Request for enhanced business intelligence analysis."""
    collection_names: List[str] = Field(..., description="Names of collections to analyze")
    analysis_type: str = Field(..., description="Type of analysis (ontology, suggestions, actions, explanations)")
    business_domain: Optional[str] = Field(None, description="Business domain for context")
    include_patterns: bool = Field(default=True, description="Whether to include pattern analysis")
    include_risk_assessment: bool = Field(default=True, description="Whether to include risk assessment")


class BusinessIntelligenceResponse(BaseModel):
    """Response from enhanced business intelligence analysis."""
    success: bool = Field(..., description="Whether the analysis was successful")
    ontologies: List[BusinessOntology] = Field(default_factory=list, description="Generated business ontologies")
    data_source_suggestions: List[DataSourceSuggestion] = Field(default_factory=list, description="Data source suggestions")
    business_actions: List[BusinessActionRecommendation] = Field(default_factory=list, description="Business action recommendations")
    relationship_explanations: List[ComplexRelationshipExplanation] = Field(default_factory=list, description="Relationship explanations")
    pattern_insights: List[str] = Field(default_factory=list, description="Data pattern insights")
    risk_assessments: Dict[str, str] = Field(default_factory=dict, description="Risk assessments by collection")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if analysis failed")


class OntologyRelationship(BaseModel):
    """A relationship within a business ontology."""
    id: str = Field(..., description="Unique identifier for the relationship")
    source_entity: str = Field(..., description="Source entity name")
    target_entity: str = Field(..., description="Target entity name")
    relationship_type: str = Field(..., description="Type of relationship")
    description: str = Field(..., description="Description of the relationship")
    cardinality: str = Field(..., description="Cardinality (one-to-one, one-to-many, etc.)")
    business_rules: List[str] = Field(default_factory=list, description="Business rules governing this relationship")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in this relationship")
    evidence_sources: List[str] = Field(default_factory=list, description="Sources of evidence for this relationship")
    created_at: datetime = Field(..., description="When the relationship was created")
    updated_at: datetime = Field(..., description="When the relationship was last updated")


class OntologyEntity(BaseModel):
    """An entity within a business ontology."""
    id: str = Field(..., description="Unique identifier for the entity")
    name: str = Field(..., description="Entity name")
    description: str = Field(..., description="Description of the entity")
    entity_type: str = Field(..., description="Type of entity (e.g., customer, product, transaction)")
    attributes: List[str] = Field(default_factory=list, description="List of entity attributes")
    business_rules: List[str] = Field(default_factory=list, description="Business rules for this entity")
    lifecycle_stages: List[str] = Field(default_factory=list, description="Lifecycle stages of the entity")
    data_sources: List[str] = Field(default_factory=list, description="Data sources that define this entity")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in this entity definition")
    created_at: datetime = Field(..., description="When the entity was created")
    updated_at: datetime = Field(..., description="When the entity was last updated")


class EnhancedBusinessOntology(BaseModel):
    """Enhanced business ontology with detailed entities and relationships."""
    id: str = Field(..., description="Unique identifier for the ontology")
    name: str = Field(..., description="Name of the business ontology")
    domain: str = Field(..., description="Business domain (e.g., e-commerce, healthcare, finance)")
    version: str = Field(default="1.0", description="Ontology version")
    description: str = Field(..., description="Detailed description of the ontology")
    
    # Enhanced structure
    entities: List[OntologyEntity] = Field(default_factory=list, description="Detailed entity definitions")
    relationships: List[OntologyRelationship] = Field(default_factory=list, description="Detailed relationship definitions")
    
    # Business context
    business_rules: List[str] = Field(default_factory=list, description="List of business rules")
    domain_expertise: List[str] = Field(default_factory=list, description="Areas of domain expertise covered")
    compliance_requirements: List[str] = Field(default_factory=list, description="Compliance requirements addressed")
    
    # Metadata
    created_at: datetime = Field(..., description="When the ontology was created")
    updated_at: datetime = Field(..., description="When the ontology was last updated")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in the ontology")
    source_collections: List[str] = Field(default_factory=list, description="Collections used to generate this ontology")
    
    # Quality metrics
    completeness_score: float = Field(..., ge=0.0, le=1.0, description="Completeness of the ontology")
    consistency_score: float = Field(..., ge=0.0, le=1.0, description="Internal consistency score")
    coverage_score: float = Field(..., ge=0.0, le=1.0, description="Coverage of the business domain")


class OntologyDiscoveryRequest(BaseModel):
    """Request for ontology discovery and generation."""
    collection_names: List[str] = Field(..., description="Names of collections to analyze")
    business_domain: str = Field(..., description="Business domain for context")
    discovery_depth: str = Field(default="standard", description="Depth of discovery (basic, standard, deep)")
    include_patterns: bool = Field(default=True, description="Whether to include pattern analysis")
    include_business_rules: bool = Field(default=True, description="Whether to infer business rules")
    include_relationships: bool = Field(default=True, description="Whether to discover relationships")
    custom_entities: Optional[List[str]] = Field(None, description="Custom entities to look for")
    custom_relationships: Optional[List[str]] = Field(None, description="Custom relationships to look for")


class OntologyDiscoveryResponse(BaseModel):
    """Response from ontology discovery."""
    success: bool = Field(..., description="Whether discovery was successful")
    ontologies: List[EnhancedBusinessOntology] = Field(default_factory=list, description="Generated ontologies")
    discovered_entities: List[str] = Field(default_factory=list, description="List of discovered entities")
    discovered_relationships: List[str] = Field(default_factory=list, description="List of discovered relationships")
    business_rules: List[str] = Field(default_factory=list, description="Inferred business rules")
    data_patterns: List[str] = Field(default_factory=list, description="Identified data patterns")
    confidence_metrics: Dict[str, float] = Field(default_factory=dict, description="Confidence metrics by aspect")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for ontology improvement")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if discovery failed")


class OntologyValidationRequest(BaseModel):
    """Request for ontology validation."""
    ontology_id: str = Field(..., description="ID of the ontology to validate")
    validation_rules: List[str] = Field(default_factory=list, description="Specific validation rules to apply")
    include_consistency_check: bool = Field(default=True, description="Whether to check internal consistency")
    include_completeness_check: bool = Field(default=True, description="Whether to check completeness")
    include_business_rule_validation: bool = Field(default=True, description="Whether to validate business rules")


class OntologyValidationResponse(BaseModel):
    """Response from ontology validation."""
    success: bool = Field(..., description="Whether validation was successful")
    ontology_id: str = Field(..., description="ID of the validated ontology")
    is_valid: bool = Field(..., description="Whether the ontology is valid")
    validation_score: float = Field(..., ge=0.0, le=1.0, description="Overall validation score")
    issues: List[str] = Field(default_factory=list, description="List of validation issues found")
    warnings: List[str] = Field(default_factory=list, description="List of validation warnings")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for fixing issues")
    validation_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed validation results")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if validation failed") 