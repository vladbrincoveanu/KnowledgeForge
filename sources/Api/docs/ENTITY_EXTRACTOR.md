# Enhanced EntityExtractor

A comprehensive entity extraction system for CSV data that implements multi-strategy extraction, composite key detection, hierarchical entity recognition, and intelligent caching.

## 🚀 Features

### ✅ Multi-Strategy Entity Extraction
- **Regex Pattern Matching**: Pre-defined patterns for common entity types (email, phone, URL, date, UUID, etc.)
- **Statistical Analysis**: Intelligent detection of ID columns, sequential patterns, and uniqueness ratios
- **LLM Inference**: Semantic analysis using local LLM (LM Studio) for complex entity classification
- **Pattern Analysis**: Advanced pattern recognition for data structure analysis

### 🔑 Composite Key Detection
- Automatically identifies when multiple columns form unique identifiers
- Calculates uniqueness ratios for column combinations
- Supports complex key structures with confidence scoring

### 🏗️ Hierarchical Entity Recognition
- **Address Components**: Detects street, city, state, zip, country hierarchies
- **Category Hierarchies**: Identifies product categories, classifications, and taxonomies
- **Multi-level Structures**: Recognizes nested entity relationships

### 🎯 Enhanced Entity Properties
Each extracted entity includes:
- `name`: Entity identifier
- `type`: Semantic classification
- `source_column`: Origin column(s)
- `confidence`: 0-1 confidence score
- `extraction_method`: Strategy used (regex, statistical, LLM, pattern)
- `sample_values`: Representative data samples
- `statistical_profile`: Comprehensive data statistics

### 🧠 Intelligent Deduplication
- **Rule-based Merging**: Combines entities with same name/type
- **Embedding Similarity**: Uses sentence-transformers for semantic deduplication
- **Confidence-based Selection**: Prefers higher-confidence entities during merging

### 💾 File Hash Caching
- **Content-based Hashing**: MD5 hash of file content for cache keys
- **Efficient Reprocessing**: Skips extraction for unchanged files
- **Configurable TTL**: Cache expiration with timestamp validation
- **Cache Statistics**: Monitoring and management capabilities

## 🛠️ Installation

### Dependencies
```bash
pip install pandas scikit-learn sentence-transformers pydantic
```

### Optional LLM Support
```bash
# Install LM Studio for local LLM support
# Download from https://lmstudio.ai/

# Start LM Studio local server
# Select model and click "Start Server" on port 1234
```

## 📖 Usage

### Basic Entity Extraction

```python
from ontology_extractor.entity_extractor import EntityExtractor
from ontology_extractor.models import ColumnProfile, DataType

# Initialize extractor
extractor = EntityExtractor(cache_dir="./cache")

# Define column profiles
columns = [
    ColumnProfile(
        name="email",
        data_type=DataType.STRING,
        null_count=0,
        unique_count=100,
        sample_values=["user@example.com"],
        statistics={}
    )
]

# Extract entities
config = {
    'min_confidence': 0.7,
    'max_entities_per_column': 100
}

entities = extractor.extract_entities("data.csv", columns, config)
```

### With LLM Integration

```python
from ontology_extractor.llm_manager import LLMManager

# Initialize LLM manager
llm_manager = LLMManager(
    lmstudio_url="http://localhost:1234",
    default_model="llama2"
)

# Initialize extractor with LLM
extractor = EntityExtractor(
    llm_manager=llm_manager,
    cache_dir="./cache"
)

# Extract entities with semantic analysis
entities = extractor.extract_entities("data.csv", columns, config)
```

### Advanced Configuration

```python
config = {
    'min_confidence': 0.6,           # Minimum confidence threshold
    'max_entities_per_column': 50,   # Max entities per column
    'enable_semantic_similarity': True,  # Enable embedding-based deduplication
    'relationship_threshold': 0.7,   # Relationship detection threshold
    'use_llm': True,                 # Enable LLM analysis
    'batch_size': 1000               # Processing batch size
}
```

## 🔍 Extraction Strategies

### 1. Regex Pattern Matching
Automatically detects common entity types:

- **Email**: `user@domain.com`
- **Phone**: `+1-555-123-4567`, `(555) 123-4567`
- **URL**: `https://example.com`, `www.example.com`
- **Date**: `2024-01-15`, `01/15/2024`
- **UUID**: `123e4567-e89b-12d3-a456-426614174000`
- **Credit Card**: `1234-5678-9012-3456`
- **Postal Code**: `12345`, `A1B 2C3`
- **SSN**: `123-45-6789`

### 2. Statistical Analysis
Identifies ID columns and patterns:

- **Sequential IDs**: Detects auto-incrementing sequences
- **UUID-like**: Recognizes GUID/UUID patterns
- **Hash-like**: Identifies cryptographic hashes
- **Composite Keys**: Finds multi-column unique identifiers

### 3. LLM Semantic Analysis
Uses local LLM for complex classification:

- **Entity Type Classification**: Person, organization, location, product, etc.
- **Semantic Type Detection**: Email, phone, address, category, etc.
- **Context-aware Analysis**: Column name + data pattern analysis

### 4. Pattern Analysis
Advanced data structure recognition:

- **Length Distribution**: Character and word count analysis
- **Character Patterns**: Digit, letter, special character ratios
- **Format Patterns**: Email-like, phone-like, date-like detection
- **Word Patterns**: Vocabulary and frequency analysis

## 🏗️ Entity Types

### Basic Types
- `email`, `phone`, `url`, `date`, `time`
- `uuid`, `credit_card`, `postal_code`, `ssn`
- `sequential_id`, `uuid_like`, `hash_like`

### Semantic Types
- `person`, `organization`, `location`, `product`
- `identifier`, `category`, `measurement`, `contact`
- `concept`, `temporal`, `classification`

### Special Types
- `composite_key`: Multi-column unique identifiers
- `hierarchical_address`: Address component hierarchies
- `hierarchical_category`: Category taxonomies
- `pattern_based`: Pattern-derived entities

## 📊 Output Format

### Entity Structure
```python
Entity(
    id="email_john.doe@example.com_12345",
    name="john.doe@example.com",
    entity_type="email",
    attributes={
        "source_column": "email",
        "data_type": "string",
        "extraction_method": "regex_pattern",
        "pattern": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        "sample_values": ["john.doe@example.com"],
        "statistical_profile": {
            "length": 19,
            "word_count": 1,
            "character_types": {"digits": 0, "letters": 15, "special": 4}
        }
    },
    confidence=0.95,
    source_column="email",
    source_value="john.doe@example.com"
)
```

### Extraction Summary
```python
summary = extractor.get_extraction_summary(entities)

{
    "total_entities": 45,
    "extraction_methods": {
        "regex_pattern": 20,
        "statistical_analysis": 15,
        "llm_inference": 8,
        "pattern_analysis": 2
    },
    "entity_types": {
        "email": 15,
        "phone": 10,
        "sequential_id": 5,
        "location": 8,
        "date": 7
    },
    "confidence_distribution": {
        "high": 30,
        "medium": 12,
        "low": 3
    },
    "avg_confidence": 0.87,
    "unique_source_columns": 12
}
```

## 🗄️ Caching System

### Cache Features
- **File Hash-based**: MD5 hash of file content
- **Timestamp Validation**: Configurable TTL (default: 24 hours)
- **Automatic Cleanup**: Cache management utilities
- **Statistics Monitoring**: Cache performance metrics

### Cache Operations
```python
# Get cache statistics
stats = extractor.get_cache_stats()

# Clear cache
extractor.clear_cache()

# Cache is automatically used for unchanged files
entities = extractor.extract_entities("data.csv", columns, config)  # Uses cache if available
```

## 🔧 Advanced Features

### Composite Key Detection
```python
# Automatically detects when columns form unique combinations
# Example: (customer_id, order_date) might form a composite key
composite_entities = extractor._detect_composite_keys(file_path, columns, config)
```

### Hierarchical Entity Detection
```python
# Detects address hierarchies: street + city + state + zip + country
# Detects category hierarchies: Electronics > Computers > Laptops
hierarchical_entities = extractor._detect_hierarchical_entities(file_path, columns, config)
```

### Pattern Analysis
```python
# Analyze patterns in column data
patterns = extractor.extract_entity_patterns(file_path, "email")

# Returns:
{
    "length_distribution": {"min": 15, "max": 35, "avg": 22.5},
    "character_patterns": {"digit_ratio": 0.0, "alpha_ratio": 0.79},
    "word_patterns": {"avg_words_per_value": 1.0},
    "format_patterns": {"email_like": 1.0}
}
```

## 🧪 Testing

Run the test script to verify functionality:

```bash
cd sources/Api
python test_entity_extractor.py
```

The test script demonstrates:
- Basic entity extraction
- LLM integration (if LM Studio available)
- Caching functionality
- Pattern analysis
- Composite key detection
- Hierarchical entity recognition

## 📈 Performance

### Optimization Features
- **Batch Processing**: Configurable batch sizes for large datasets
- **Intelligent Caching**: Skip reprocessing for unchanged files
- **Parallel Processing**: LLM requests with rate limiting

### Expected Performance
- **Small files (< 1MB)**: < 1 second
- **Medium files (1-10MB)**: 1-5 seconds
- **Large files (10-100MB)**: 5-30 seconds
- **Cache hits**: < 100ms

## 🔒 Error Handling

### Graceful Degradation
- **LLM Failures**: Falls back to rule-based extraction
- **File Errors**: Continues with available data
- **Cache Failures**: Proceeds without caching
- **Pattern Failures**: Uses alternative strategies

### Logging
Comprehensive logging for debugging:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## 🚀 Future Enhancements

### Planned Features
- **Relationship Detection**: Automatic entity relationship discovery
- **Schema Evolution**: Track entity changes over time
- **Custom Patterns**: User-defined regex patterns
- **API Integration**: REST API for entity extraction
- **Visualization**: Entity relationship graphs
- **Multi-format Support**: JSON, XML, database tables

### Contributing
Contributions welcome! Areas for improvement:
- Additional regex patterns
- New entity types
- Performance optimizations
- Testing coverage
- Documentation

## 📚 API Reference

### EntityExtractor Class
- `__init__(llm_manager=None, cache_dir=None)`
- `extract_entities(file_path, columns, config)`
- `extract_entity_patterns(file_path, column_name)`
- `get_extraction_summary(entities)`
- `clear_cache()`
- `get_cache_stats()`

### LLMManager Class
- `__init__(lmstudio_url, default_model, use_embeddings, cache_dir)`
- `classify_entity_type(value, column_name)`
- `classify_semantic_type(column_data, column_name)`
- `generate_text(prompt, model, max_tokens, temperature)`

## 🤝 Support

For issues, questions, or contributions:
- Check the test script for usage examples
- Review the comprehensive logging output
- Ensure all dependencies are properly installed
- Verify LM Studio is running for LLM features

---

**EntityExtractor** - Intelligent entity discovery from structured data with local LLM integration and advanced caching.
