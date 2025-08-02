# Infrastructure Layer

## Overview

The Infrastructure layer contains all external dependencies and data access components. This layer handles interactions with databases, file systems, external APIs, and other infrastructure concerns. It implements the interfaces defined by the domain layer and provides concrete implementations for data persistence and external service integration.

## Architecture Principles

- **External Dependency Management**: Handles all external system interactions
- **Data Access Abstraction**: Provides clean interfaces for data operations
- **Error Handling**: Manages infrastructure-specific errors and failures
- **Connection Management**: Handles database connections and resource cleanup
- **Type Conversion**: Converts between domain objects and external formats

## File Structure

```
Infrastructure/
├── mongodb_connector.py           # MongoDB database operations
├── csv_metadata_extractor.py      # CSV file metadata extraction
├── xlsx_metadata_extractor.py     # XLSX file metadata extraction
├── __init__.py                    # Package initialization
└── README.md                      # This documentation
```

## Core Components

### 1. MongoDBConnector

**File:** `mongodb_connector.py`

**Purpose:** Handles all MongoDB database operations including connection management, data insertion, querying, and collection management.

**Key Features:**
- Connection pooling and management
- Batch data insertion for performance
- NumPy type conversion for MongoDB compatibility
- Collection metadata storage
- Error handling and retry logic

**Main Methods:**
- `connect()` - Establish database connection
- `disconnect()` - Close database connection
- `insert_many()` - Insert multiple documents
- `query()` - Query documents from collections
- `get_collection_info()` - Get collection metadata
- `list_collections()` - List all collections
- `delete_collection()` - Delete a collection

**Dependencies:**
- `pymongo` - MongoDB Python driver
- `numpy` - For type conversion

### 2. CSVMetadataExtractor

**File:** `csv_metadata_extractor.py`

**Purpose:** Extracts metadata from CSV files including column information, data types, and file statistics.

**Key Features:**
- Automatic data type inference
- Column statistics calculation
- Sample value extraction
- Null value detection
- File information extraction

**Main Methods:**
- `extract_metadata()` - Extract complete file metadata
- `_infer_data_type()` - Infer data type from column values
- `_get_column_statistics()` - Calculate column statistics
- `_extract_sample_values()` - Extract sample values for each column

**Dependencies:**
- `pandas` - For CSV file reading and analysis
- `numpy` - For data type detection

### 3. XLSXMetadataExtractor

**File:** `xlsx_metadata_extractor.py`

**Purpose:** Extracts metadata from Excel (XLSX) files including multiple sheet support, column information, and data type inference.

**Key Features:**
- Multi-sheet Excel file support
- Sheet metadata extraction
- Automatic data type inference
- Column statistics calculation
- Excel-specific format handling

**Main Methods:**
- `extract_metadata()` - Extract metadata from Excel file
- `_get_sheet_names()` - Get list of sheet names
- `_extract_sheet_metadata()` - Extract metadata from specific sheet
- `_infer_data_type()` - Infer data type from column values

**Dependencies:**
- `pandas` - For Excel file reading
- `openpyxl` - For Excel file format support

## Usage Examples

### Using MongoDBConnector

```python
from Api.Infrastructure.mongodb_connector import MongoDBConnector
from Api.Domain.models import DataRow

# Initialize connector
connector = MongoDBConnector()

# Connect to database
connector.connect()

# Insert data
data_rows = [
    DataRow(row_number=1, data={"name": "John", "age": 30}, metadata={}),
    DataRow(row_number=2, data={"name": "Jane", "age": 25}, metadata={})
]

# Convert to dictionaries for MongoDB
documents = [row.data for row in data_rows]
connector.insert_many("customers", documents)

# Query data
results = connector.query("customers", {"age": {"$gte": 25}})

# Get collection info
info = connector.get_collection_info("customers")
print(f"Collection: {info['name']}, Documents: {info['count']}")

# Clean up
connector.disconnect()
```

### Using CSVMetadataExtractor

```python
from Api.Infrastructure.csv_metadata_extractor import CSVMetadataExtractor

# Initialize extractor
extractor = CSVMetadataExtractor()

# Extract metadata from CSV file
metadata = extractor.extract_metadata("/path/to/customers.csv")

# Access metadata information
print(f"File: {metadata.file_info.file_name}")
print(f"Total rows: {metadata.total_rows}")
print(f"Columns: {len(metadata.columns)}")

# Examine column metadata
for column in metadata.columns:
    print(f"Column: {column.name}")
    print(f"  Type: {column.data_type}")
    print(f"  Null count: {column.null_count}")
    print(f"  Unique count: {column.unique_count}")
    print(f"  Sample values: {column.sample_values[:3]}")
```

### Using XLSXMetadataExtractor

```python
from Api.Infrastructure.xlsx_metadata_extractor import XLSXMetadataExtractor

# Initialize extractor
extractor = XLSXMetadataExtractor()

# Extract metadata from Excel file
metadata = extractor.extract_metadata("/path/to/data.xlsx")

# Extract metadata from specific sheet
sheet_metadata = extractor.extract_metadata(
    "/path/to/data.xlsx", 
    sheet_name="Sheet1"
)

# Access sheet information
print(f"File: {metadata.file_info.file_name}")
print(f"Total rows: {metadata.total_rows}")
print(f"File type: {metadata.file_type}")

# List available sheets
sheets = extractor._get_sheet_names("/path/to/data.xlsx")
print(f"Available sheets: {sheets}")
```

## Data Type Handling

### NumPy Type Conversion

The MongoDB connector includes automatic NumPy type conversion:

```python
def _convert_numpy_types(self, obj):
    """Convert NumPy types to native Python types for MongoDB compatibility."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {key: self._convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [self._convert_numpy_types(item) for item in obj]
    else:
        return obj
```

### Data Type Inference

Both extractors implement intelligent data type inference:

```python
def _infer_data_type(self, values):
    """Infer data type from a list of values."""
    if not values:
        return DataType.UNKNOWN
    
    # Check for boolean
    if all(isinstance(v, bool) or str(v).lower() in ['true', 'false', '1', '0'] for v in values):
        return DataType.BOOLEAN
    
    # Check for datetime
    if all(self._is_datetime(v) for v in values):
        return DataType.DATETIME
    
    # Check for integer
    if all(self._is_integer(v) for v in values):
        return DataType.INTEGER
    
    # Check for float
    if all(self._is_float(v) for v in values):
        return DataType.FLOAT
    
    # Default to string
    return DataType.STRING
```

## Error Handling

### Connection Errors

```python
def connect(self):
    """Establish database connection with error handling."""
    try:
        self.client = MongoClient(self.connection_string)
        self.db = self.client[self.database_name]
        self.client.admin.command('ping')  # Test connection
        logger.info("Successfully connected to MongoDB")
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        raise
```

### File Processing Errors

```python
def extract_metadata(self, file_path):
    """Extract metadata with comprehensive error handling."""
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path.lower().endswith('.csv'):
            raise ValueError(f"File must be a CSV file: {file_path}")
        
        # Extract metadata
        return self._extract_metadata_internal(file_path)
        
    except pd.errors.EmptyDataError:
        logger.error(f"CSV file is empty: {file_path}")
        raise
    except pd.errors.ParserError as e:
        logger.error(f"Error parsing CSV file {file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing CSV file {file_path}: {e}")
        raise
```

## Performance Optimization

### Batch Processing

```python
def insert_many(self, collection_name, documents, batch_size=1000):
    """Insert documents in batches for better performance."""
    collection = self.db[collection_name]
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        
        # Convert NumPy types
        converted_batch = [self._convert_numpy_types(doc) for doc in batch]
        
        try:
            result = collection.insert_many(converted_batch)
            logger.debug(f"Inserted {len(result.inserted_ids)} documents into {collection_name}")
        except BulkWriteError as e:
            logger.error(f"Bulk write error: {e}")
            raise
```

### Memory Management

```python
def _read_large_csv(self, file_path, chunk_size=10000):
    """Read large CSV files in chunks to manage memory."""
    for chunk in pd.read_csv(file_path, chunksize=chunk_size):
        yield chunk
```

## Configuration

### Environment Variables

```python
import os

class MongoDBConnector:
    def __init__(self):
        self.connection_string = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        self.database_name = os.getenv('MONGODB_DATABASE', 'knowlly_data')
        self.max_pool_size = int(os.getenv('MONGODB_MAX_POOL_SIZE', '10'))
        self.timeout = int(os.getenv('MONGODB_TIMEOUT', '30'))
```

### Connection Pooling

```python
def connect(self):
    """Establish connection with connection pooling."""
    self.client = MongoClient(
        self.connection_string,
        maxPoolSize=self.max_pool_size,
        serverSelectionTimeoutMS=self.timeout * 1000
    )
```

## Testing

### Unit Testing Infrastructure Components

```python
import pytest
from unittest.mock import Mock, patch
from Api.Infrastructure.mongodb_connector import MongoDBConnector

def test_mongodb_connection():
    # Arrange
    connector = MongoDBConnector()
    
    # Act & Assert
    with patch('pymongo.MongoClient'):
        connector.connect()
        assert connector.client is not None

def test_insert_many():
    # Arrange
    connector = MongoDBConnector()
    documents = [{"name": "John"}, {"name": "Jane"}]
    
    # Act & Assert
    with patch.object(connector, 'db') as mock_db:
        mock_collection = Mock()
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.insert_many.return_value = Mock(inserted_ids=[1, 2])
        
        connector.insert_many("test", documents)
        mock_collection.insert_many.assert_called_once()
```

### Integration Testing

```python
def test_csv_metadata_extraction():
    # Test with actual CSV file
    extractor = CSVMetadataExtractor()
    
    # Create test CSV file
    test_data = "name,age,city\nJohn,30,NYC\nJane,25,LA"
    with open("test.csv", "w") as f:
        f.write(test_data)
    
    try:
        metadata = extractor.extract_metadata("test.csv")
        assert metadata.total_rows == 2
        assert len(metadata.columns) == 3
        assert metadata.columns[0].name == "name"
    finally:
        os.remove("test.csv")
```

## Security Considerations

### Input Validation

```python
def _validate_file_path(self, file_path):
    """Validate file path for security."""
    if not file_path or not isinstance(file_path, str):
        raise ValueError("File path must be a non-empty string")
    
    # Prevent directory traversal
    if ".." in file_path or file_path.startswith("/"):
        raise ValueError("Invalid file path")
    
    # Check file extension
    if not file_path.lower().endswith(('.csv', '.xlsx')):
        raise ValueError("Unsupported file type")
```

### Database Security

```python
def _sanitize_collection_name(self, collection_name):
    """Sanitize collection name for MongoDB."""
    if not collection_name or not isinstance(collection_name, str):
        raise ValueError("Collection name must be a non-empty string")
    
    # Remove dangerous characters
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', collection_name)
    
    if not sanitized:
        raise ValueError("Invalid collection name")
    
    return sanitized
```

## Monitoring and Logging

### Performance Monitoring

```python
import time

def insert_many(self, collection_name, documents):
    """Insert documents with performance monitoring."""
    start_time = time.time()
    
    try:
        result = self._insert_documents(collection_name, documents)
        processing_time = time.time() - start_time
        
        logger.info(f"Inserted {len(documents)} documents into {collection_name} in {processing_time:.2f}s")
        return result
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Failed to insert documents into {collection_name} after {processing_time:.2f}s: {e}")
        raise
```

### Health Checks

```python
def health_check(self):
    """Perform health check on database connection."""
    try:
        self.client.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## Future Enhancements

### Planned Features

1. **Connection Pooling**: Enhanced connection pool management
2. **Caching Layer**: Redis-based caching for frequently accessed data
3. **Async Operations**: Support for async database operations
4. **Data Validation**: Enhanced data validation and sanitization
5. **Backup Integration**: Automated backup and restore functionality

### Extension Points

- New file format extractors can be added
- Additional database connectors can be implemented
- External API integrations can be added
- Caching strategies can be implemented

## Best Practices

1. **Connection Management**: Always close connections properly
2. **Error Handling**: Implement comprehensive error handling
3. **Type Safety**: Use type hints and validation
4. **Performance**: Use batch operations and connection pooling
5. **Security**: Validate and sanitize all inputs
6. **Logging**: Log all important operations and errors
7. **Testing**: Write comprehensive unit and integration tests
8. **Documentation**: Document all public methods and configurations

---

*This documentation is part of the KnowledgeForge Enterprise Data Intelligence Platform.* 