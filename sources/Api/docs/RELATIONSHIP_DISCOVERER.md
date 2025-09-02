# Enhanced RelationshipDiscoverer

A comprehensive relationship discovery system for CSV data that implements multi-strategy relationship detection, foreign key analysis, semantic similarity using SBERT embeddings, LLM inference, cardinality detection, and graph cycle prevention.

## 🚀 Features

### ✅ Multi-Strategy Relationship Discovery
- **Foreign Key Detection**: Value overlap analysis for identifying referential relationships
- **SBERT Semantic Similarity**: Advanced embedding-based similarity using sentence-transformers
- **LLM Inference**: Intelligent relationship type inference using local LLM (LM Studio)
- **Co-occurrence Analysis**: Row-level relationship detection based on value co-occurrence
- **Hierarchical Detection**: Parent-child and category relationship recognition
- **Temporal Analysis**: Time-based relationship discovery

### 🔑 Foreign Key Detection
- **Value Overlap Analysis**: Calculates percentage of overlapping values between columns
- **Cardinality Analysis**: Determines relationship direction (1:1, 1:n, n:m)
- **Confidence Scoring**: Multi-factor confidence calculation based on overlap, uniqueness, and data volume
- **Evidence Collection**: Sample data proving the relationship exists

### 🧠 SBERT Semantic Similarity
- **Embedding Generation**: Uses all-MiniLM-L6-v2 model for high-quality embeddings
- **Cosine Similarity**: Advanced similarity calculation between entity representations
- **Relationship Type Inference**: Automatically determines relationship types based on similarity scores
- **Configurable Thresholds**: Adjustable similarity thresholds for relationship discovery

### 🤖 LLM-Powered Relationship Inference
- **Column Name Analysis**: Intelligent analysis of column names and sample data
- **Relationship Type Suggestion**: LLM suggests appropriate relationship types
- **Context-Aware Reasoning**: Considers data patterns and semantic context
- **Confidence Assessment**: LLM provides confidence scores for relationships

### 🎯 Relationship Cardinality Detection
- **Automatic Detection**: Calculates 1:1, 1:n, n:1, and n:m relationships
- **Data-Driven Analysis**: Uses actual data statistics for accurate cardinality
- **Confidence Adjustment**: Adjusts relationship confidence based on cardinality consistency
- **Validation Support**: Ensures cardinality aligns with relationship characteristics

### 🔄 Graph Cycle Detection
- **NetworkX Integration**: Uses NetworkX for graph analysis and cycle detection
- **Automatic Cycle Removal**: Identifies and removes redundant relationship cycles
- **Confidence-Based Selection**: Removes lowest-confidence relationships in cycles
- **Graph Integrity**: Maintains clean, acyclic relationship graphs

### 📊 Enhanced Output & Analysis
- **Comprehensive Evidence**: Detailed evidence for each relationship type
- **Graph Export**: Export relationships to visualization-ready graph format
- **Validation System**: Relationship quality and consistency validation
- **Statistical Analysis**: Detailed relationship discovery statistics

## 🛠️ Installation

### Dependencies
```bash
pip install pandas scikit-learn sentence-transformers pydantic networkx
```

### Optional LLM Support
```bash
# Install LM Studio for local LLM support
# Download from https://lmstudio.ai/

# Start LM Studio local server
# Select model and click "Start Server" on port 1234
```

## 📖 Usage

### Basic Relationship Discovery

```python
from ontology_extractor.relationship_discoverer import RelationshipDiscoverer
from ontology_extractor.models import Entity, ColumnProfile

# Initialize discoverer
discoverer = RelationshipDiscoverer(use_sbert=True)

# Discover relationships
config = {
    'relationship_threshold': 0.6,
    'fk_overlap_threshold': 0.8,
    'semantic_similarity_threshold': 0.7
}

relationships = discoverer.discover_relationships(
    "data.csv", entities, columns, config
)
```

### With LLM Integration

```python
from ontology_extractor.llm_manager import LLMManager

# Initialize LLM manager
llm_manager = LLMManager(
    lmstudio_url="http://localhost:1234",
    default_model="llama2"
)

# Initialize discoverer with LLM
discoverer = RelationshipDiscoverer(
    llm_manager=llm_manager,
    use_sbert=True
)

# Discover relationships with AI enhancement
relationships = discoverer.discover_relationships(
    "data.csv", entities, columns, config
)
```

### Advanced Configuration

```python
config = {
    'relationship_threshold': 0.5,           # Minimum confidence for relationships
    'fk_overlap_threshold': 0.7,            # Minimum overlap for foreign keys
    'semantic_similarity_threshold': 0.6,   # Minimum similarity for semantic relationships
    'enable_cycle_detection': True,         # Enable graph cycle detection
    'max_relationships_per_pair': 10        # Limit relationships per entity pair
}
```

## 🔍 Discovery Strategies

### 1. Foreign Key Detection
Automatically identifies referential relationships:

```python
# Example: customer_id -> customer table
# Detects when columns share values (foreign key relationships)
fk_relationships = discoverer._discover_foreign_key_relationships(
    file_path, entities, columns, config
)

# Features:
# - Overlap percentage calculation
# - Cardinality determination
# - Confidence scoring
# - Evidence collection
```

### 2. SBERT Semantic Similarity
Uses advanced embeddings for semantic analysis:

```python
# Example: "customer" and "client" entities
# High similarity suggests synonym relationship
semantic_rels = discoverer._discover_semantic_relationships_sbert(
    entities, columns, config
)

# Features:
# - all-MiniLM-L6-v2 embeddings
# - Cosine similarity calculation
# - Automatic relationship type inference
# - Configurable similarity thresholds
```

### 3. LLM Relationship Inference
Intelligent analysis using local language models:

```python
# Example: Column name analysis
# "customer_id" and "order_customer_id" -> foreign key relationship
llm_rels = discoverer._discover_llm_relationships(
    file_path, entities, columns, config
)

# Features:
# - Column name pattern analysis
# - Sample data interpretation
# - Relationship type suggestion
# - Confidence assessment
```

### 4. Co-occurrence Analysis
Row-level relationship detection:

```python
# Example: Products that frequently appear together
# "laptop" and "mouse" often co-occur
co_occurrence_rels = discoverer._discover_co_occurrence_relationships(
    file_path, entities, columns, config
)

# Features:
# - Frequency-based analysis
# - Statistical significance
# - Confidence calculation
# - Evidence collection
```

## 🏗️ Relationship Types

### Foreign Key Types
- `references`: Source column references target column
- `is_referenced_by`: Target column is referenced by source column

### Semantic Types
- `is_synonym_of`: High similarity entities
- `is_similar_to`: Medium similarity entities
- `related_to`: General relationship
- `weakly_related_to`: Low similarity entities

### LLM-Inferred Types
- `foreign_key`: Referential relationships
- `hierarchical`: Parent-child relationships
- `temporal`: Time-based relationships
- `spatial`: Location relationships
- `ownership`: Belongs to, contains, has
- `measurement`: Quantity, amount relationships
- `co_occurrence`: Values appearing together

### Special Types
- `co_occurs_with`: Co-occurrence relationships
- `is_parent_of`: Hierarchical relationships
- `precedes`: Temporal sequence relationships

## 📊 Output Format

### Relationship Structure
```python
Relationship(
    id="fk_customer_1_order_1_hash123",
    source_entity_id="customer_1",
    target_entity_id="order_1",
    relationship_type="references",
    attributes={
        "overlap_percentage": 0.95,
        "overlap_count": 19,
        "source_column": "customer_id",
        "target_column": "order_customer_id",
        "unique_source_values": 5,
        "unique_target_values": 10,
        "evidence": [
            {"source_value": "1", "target_value": "1"},
            {"source_value": "2", "target_value": "2"}
        ],
        "extraction_method": "foreign_key_analysis",
        "cardinality": "1:n"
    },
    confidence=0.92,
    source_columns=["customer_id", "order_customer_id"]
)
```

### Discovery Statistics
```python
stats = discoverer.get_relationship_statistics(relationships)

{
    "total_relationships": 25,
    "relationship_types": {
        "references": 8,
        "is_similar_to": 5,
        "co_occurs_with": 7,
        "is_parent_of": 3,
        "precedes": 2
    },
    "extraction_methods": {
        "foreign_key_analysis": 8,
        "sbert_similarity": 5,
        "llm_inference": 7,
        "co_occurrence_analysis": 5
    },
    "cardinality_distribution": {
        "1:1": 3,
        "1:n": 12,
        "n:1": 8,
        "n:m": 2
    },
    "average_confidence": 0.78,
    "columns_with_relationships": {"customer_id": 15, "order_id": 12}
}
```

## 🔄 Graph Operations

### Cycle Detection
```python
# Automatically detects and removes cycles
relationships = discoverer._detect_graph_cycles(relationships)

# Features:
# - NetworkX graph analysis
# - Automatic cycle identification
# - Confidence-based cycle resolution
# - Clean graph maintenance
```

### Graph Export
```python
# Export to visualization format
graph_data = discoverer.export_relationships_to_graph(relationships, entities)

# Returns:
{
    "nodes": [entity_nodes],
    "edges": [relationship_edges],
    "metadata": {
        "total_nodes": 25,
        "total_edges": 30,
        "node_types": {"person": 10, "product": 15},
        "edge_types": {"references": 15, "is_similar_to": 15}
    }
}
```

## 🔍 Evidence & Validation

### Relationship Evidence
```python
# Get detailed evidence for any relationship
evidence = discoverer.get_relationship_evidence(relationship, file_path)

# Evidence includes:
# - FK evidence: overlap percentages, counts
# - Semantic evidence: similarity scores, entity types
# - LLM evidence: reasoning, confidence, sample data
# - Co-occurrence evidence: frequency counts, values
```

### Validation System
```python
# Validate relationship quality and consistency
validation = discoverer.validate_relationships(relationships, entities)

# Validation includes:
# - Entity existence verification
# - Self-relationship detection
# - Confidence range validation
# - Attribute completeness
# - Quality metrics calculation
```

## 🧪 Testing

Run the test script to verify functionality:

```bash
cd sources/Api
python test_relationship_discoverer.py
```

The test script demonstrates:
- Basic relationship discovery
- LLM integration (if LM Studio available)
- Foreign key detection
- SBERT similarity analysis
- Graph operations
- Validation and evidence collection

## 📈 Performance

### Optimization Features
- **Efficient Embeddings**: SBERT model optimization
- **Batch Processing**: Configurable batch sizes
- **Intelligent Filtering**: Early filtering of low-confidence candidates

### Expected Performance
- **Small datasets (< 1K rows)**: < 1 second
- **Medium datasets (1K-100K rows)**: 1-10 seconds
- **Large datasets (100K+ rows)**: 10-60 seconds
- **SBERT processing**: ~100 entities/second
- **LLM processing**: ~10 relationships/second

## 🔒 Error Handling

### Graceful Degradation
- **SBERT Failures**: Falls back to TF-IDF similarity
- **LLM Failures**: Continues with rule-based discovery
- **Database Errors**: Continues with available data
- **Cycle Detection Failures**: Proceeds without cycle removal

### Logging
Comprehensive logging for debugging:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## 🚀 Advanced Features

### Custom Relationship Patterns
```python
# Add custom relationship detection patterns
discoverer.relationship_patterns['custom'] = ['pattern1', 'pattern2']

# Patterns are used to identify potential relationship columns
```

### Relationship Filtering
```python
# Filter relationships by type, confidence, or method
high_confidence_rels = [
    r for r in relationships 
    if r.confidence >= 0.8
]

fk_rels = [
    r for r in relationships 
    if 'foreign_key_analysis' in r.attributes.get('extraction_method', '')
]
```

### Evidence Enhancement
```python
# Enhance evidence with additional data
for rel in relationships:
    if rel.attributes.get('extraction_method') == 'foreign_key_analysis':
        # Add additional FK-specific evidence
        rel.attributes['fk_strength'] = calculate_fk_strength(rel)
```

## 🔧 Configuration Options

### Discovery Thresholds
```python
config = {
    'relationship_threshold': 0.6,           # Overall relationship confidence
    'fk_overlap_threshold': 0.8,            # Foreign key overlap requirement
    'semantic_similarity_threshold': 0.7,   # SBERT similarity threshold
    'co_occurrence_threshold': 0.5,         # Co-occurrence significance
    'llm_confidence_threshold': 0.6         # LLM inference confidence
}
```

### Processing Limits
```python
config = {
    'max_relationships_per_pair': 10,       # Max relationships per entity pair
    'max_entities_per_analysis': 100,      # Max entities for similarity analysis
    'max_sample_data': 20,                 # Max samples for LLM analysis
    'enable_cycle_detection': True,        # Enable graph cycle detection
    'cache_embeddings': True               # Cache SBERT embeddings
}
```

## 🚀 Future Enhancements

### Planned Features
- **Relationship Evolution**: Track relationship changes over time
- **Custom Similarity Metrics**: User-defined similarity functions
- **Relationship Clustering**: Group similar relationships
- **API Integration**: REST API for relationship discovery
- **Visualization Tools**: Interactive relationship graphs
- **Multi-format Support**: JSON, XML, database tables

### Contributing
Contributions welcome! Areas for improvement:
- Additional similarity metrics
- New relationship types
- Performance optimizations
- Testing coverage
- Documentation

## 📚 API Reference

### RelationshipDiscoverer Class
- `__init__(llm_manager=None, use_sbert=True, cache_dir=None)`
- `discover_relationships(file_path, entities, columns, config)`
- `get_relationship_statistics(relationships)`
- `get_relationship_evidence(relationship, file_path)`
- `export_relationships_to_graph(relationships, entities)`
- `validate_relationships(relationships, entities)`

### Discovery Methods
- `_discover_foreign_key_relationships(file_path, entities, columns, config)`
- `_discover_semantic_relationships_sbert(entities, columns, config)`
- `_discover_llm_relationships(file_path, entities, columns, config)`
- `_discover_co_occurrence_relationships(file_path, entities, columns, config)`
- `_discover_hierarchical_relationships(entities, columns, config)`
- `_discover_temporal_relationships(file_path, entities, columns, config)`

### Analysis Methods
- `_analyze_foreign_key_candidate(file_path, col1, col2, entity_columns, config)`
- `_calculate_cardinality(file_path, source_col, target_col)`
- `_detect_graph_cycles(relationships)`
- `_deduplicate_relationships(relationships)`

## 🤝 Support

For issues, questions, or contributions:
- Check the test script for usage examples
- Review the comprehensive logging output
- Ensure all dependencies are properly installed
- Verify LM Studio is running for LLM features
- Check SBERT model availability for semantic similarity

---

**RelationshipDiscoverer** - Intelligent relationship discovery from structured data with multi-strategy analysis, AI-powered inference, and advanced graph operations.
