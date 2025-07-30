# Application Layer

## Overview

The Application layer contains the business logic and use cases that orchestrate the domain entities and coordinate with the infrastructure layer. This layer implements the application's core functionality by combining domain objects with external services.

## Architecture Principles

- **Business Logic Orchestration**: Coordinates domain entities and infrastructure services
- **Use Case Implementation**: Implements specific business use cases
- **Dependency Injection**: Uses dependency injection for external dependencies
- **Single Responsibility**: Each service has a focused responsibility
- **Testable Design**: Services are designed for easy testing and mocking

## File Structure

```
Application/
├── services/                    # Business services directory
│   ├── __init__.py             # Package initialization and exports
│   ├── data_processing_service.py  # Main orchestration service
│   ├── file_processor_service.py   # File processing logic
│   ├── query_service.py            # Data querying operations
│   └── README.md                   # Services documentation
├── services.py                 # Backward compatibility wrapper
├── __init__.py                 # Package initialization
└── README.md                   # This documentation
```

## Core Services

### 1. DataProcessingService

**File:** `services/data_processing_service.py`

**Purpose:** Main orchestration service that coordinates file processing operations and manages the overall data processing workflow.

**Responsibilities:**
- Process single files and directories
- Generate collection names
- Handle processing requests and responses
- Coordinate with FileProcessorService
- Manage processing status and queries

**Key Methods:**
- `process_file()` - Process a single file
- `process_directory()` - Process all files in a directory
- `get_processing_status()` - Get status of all collections
- `query_data()` - Query data from collections

**Dependencies:**
- `MongoDBConnector` - For data storage
- `FileProcessorService` - For file processing logic

### 2. FileProcessorService

**File:** `services/file_processor_service.py`

**Purpose:** Handle the actual file processing logic for different file types, including metadata extraction and data conversion.

**Responsibilities:**
- Process CSV and XLSX files
- Extract metadata using appropriate extractors
- Convert data to DataRow objects
- Handle file-specific processing logic

**Key Methods:**
- `process_file()` - Process any supported file type
- `_process_csv_file()` - Process CSV files
- `_process_xlsx_file()` - Process Excel files
- `_convert_dataframe_to_rows()` - Convert pandas DataFrames to DataRow objects

**Dependencies:**
- `CSVMetadataExtractor` - For CSV metadata extraction
- `XLSXMetadataExtractor` - For XLSX metadata extraction
- `MongoDBConnector` - For data storage

### 3. QueryService

**File:** `services/query_service.py`

**Purpose:** Handle data querying and collection management operations, providing a clean interface for data access.

**Responsibilities:**
- Query data from collections
- Manage collection information
- Provide collection statistics
- Search and filter collections

**Key Methods:**
- `get_collection_info()` - Get collection details
- `list_collections()` - List all collections
- `delete_collection()` - Delete a collection
- `get_collection_statistics()` - Get detailed statistics
- `search_collections()` - Search collections by name

**Dependencies:**
- `MongoDBConnector` - For database operations

## Service Architecture

### Dependency Flow

```
DataProcessingService
├── FileProcessorService
│   ├── CSVMetadataExtractor
│   ├── XLSXMetadataExtractor
│   └── MongoDBConnector
├── QueryService
│   └── MongoDBConnector
└── MongoDBConnector
```

### Service Communication

Services communicate through well-defined interfaces:

1. **DataProcessingService** orchestrates the overall workflow
2. **FileProcessorService** handles file-specific processing
3. **QueryService** manages data access and queries
4. All services use **MongoDBConnector** for data persistence

## Usage Examples

### Using DataProcessingService

```python
from Api.Infrastructure.mongodb_connector import MongoDBConnector
from Api.Application.services import DataProcessingService
from Api.Domain.dtos import ProcessFileRequest

# Initialize dependencies
mongodb_connector = MongoDBConnector()
data_service = DataProcessingService(mongodb_connector)

# Process a single file
request = ProcessFileRequest(
    file_path="/path/to/customers.csv",
    collection_name="customers"
)
response = data_service.process_file(request)

# Process a directory
directory_request = ProcessDirectoryRequest(
    directory_path="/path/to/data/",
    file_patterns=["*.csv", "*.xlsx"]
)
response = data_service.process_directory(directory_request)
```

### Using FileProcessorService

```python
from Api.Application.services import FileProcessorService

# Initialize service
file_processor = FileProcessorService(mongodb_connector)

# Process a file directly
result = file_processor.process_file(
    file_path="/path/to/data.csv",
    collection_name="customers"
)

# Check processing result
if result.success:
    print(f"Processed {result.file_metadata.total_rows} rows")
    print(f"Processing time: {result.processing_time:.2f} seconds")
else:
    print(f"Error: {result.error}")
```

### Using QueryService

```python
from Api.Application.services import QueryService

# Initialize service
query_service = QueryService(mongodb_connector)

# Get collection information
info = query_service.get_collection_info("customers")
print(f"Collection: {info['name']}, Documents: {info['count']}")

# List all collections
collections = query_service.list_collections()
for collection in collections:
    print(f"- {collection['name']}: {collection['count']} documents")

# Query data
query_request = QueryRequest(
    collection_name="customers",
    query={"age": {"$gte": 18}},
    limit=50
)
response = query_service.query_data(query_request)

# Search collections
results = query_service.search_collections("customer")
for result in results:
    print(f"Found: {result['name']}")
```

## Error Handling

### Service-Level Error Handling

All services implement consistent error handling:

```python
try:
    # Business logic
    result = self._process_file_logic(file_path)
    return ProcessingResult(
        success=True,
        message="File processed successfully",
        file_metadata=result,
        processing_time=processing_time
    )
except FileNotFoundError as e:
    logger.error(f"File not found: {file_path}")
    return ProcessingResult(
        success=False,
        message="File not found",
        error=str(e),
        processing_time=processing_time
    )
except Exception as e:
    logger.error(f"Unexpected error processing file: {e}")
    return ProcessingResult(
        success=False,
        message="Processing failed",
        error=str(e),
        processing_time=processing_time
    )
```

### Error Response Format

All services return consistent error responses:

```python
{
    "success": False,
    "message": "Human-readable error message",
    "error": "Technical error details",
    "data": None
}
```

## Logging

### Service Logging

All services use structured logging:

```python
import logging

logger = logging.getLogger(__name__)

class DataProcessingService:
    def process_file(self, request):
        logger.info(f"Processing file: {request.file_path}")
        
        try:
            # Processing logic
            logger.debug(f"File processing completed successfully")
        except Exception as e:
            logger.error(f"File processing failed: {e}")
            raise
```

### Log Levels

- **DEBUG**: Detailed processing information
- **INFO**: General processing status
- **WARNING**: Non-critical issues
- **ERROR**: Processing failures
- **CRITICAL**: System-level failures

## Testing

### Unit Testing Services

```python
import pytest
from unittest.mock import Mock, patch
from Api.Application.services import DataProcessingService

def test_process_file_success():
    # Arrange
    mock_connector = Mock()
    service = DataProcessingService(mock_connector)
    request = ProcessFileRequest(file_path="test.csv")
    
    # Act
    result = service.process_file(request)
    
    # Assert
    assert result.success == True
    assert "successfully" in result.message.lower()

def test_process_file_not_found():
    # Arrange
    mock_connector = Mock()
    service = DataProcessingService(mock_connector)
    request = ProcessFileRequest(file_path="nonexistent.csv")
    
    # Act
    result = service.process_file(request)
    
    # Assert
    assert result.success == False
    assert "not found" in result.message.lower()
```

### Integration Testing

```python
def test_service_integration():
    # Test that services work together correctly
    mongodb_connector = MongoDBConnector()
    data_service = DataProcessingService(mongodb_connector)
    query_service = QueryService(mongodb_connector)
    
    # Process a file
    request = ProcessFileRequest(file_path="test.csv")
    result = data_service.process_file(request)
    
    # Query the processed data
    query_request = QueryRequest(collection_name="test", query={})
    response = query_service.query_data(query_request)
    
    assert result.success == True
    assert response.success == True
```

## Performance Considerations

### Batch Processing

Services implement batch processing for efficiency:

```python
def _insert_data_in_batches(self, collection_name, data_rows, batch_size=1000):
    """Insert data in batches to improve performance."""
    for i in range(0, len(data_rows), batch_size):
        batch = data_rows[i:i + batch_size]
        self.mongodb_connector.insert_many(collection_name, batch)
```

### Memory Management

Large files are processed in chunks:

```python
def _process_large_file(self, file_path, chunk_size=10000):
    """Process large files in chunks to manage memory."""
    for chunk in pd.read_csv(file_path, chunksize=chunk_size):
        # Process chunk
        yield self._process_chunk(chunk)
```

### Caching

Frequently accessed data is cached:

```python
def get_collection_info(self, collection_name):
    """Get collection info with caching."""
    cache_key = f"collection_info_{collection_name}"
    
    if cache_key in self._cache:
        return self._cache[cache_key]
    
    info = self.mongodb_connector.get_collection_info(collection_name)
    self._cache[cache_key] = info
    return info
```

## Security

### Input Validation

All services validate input parameters:

```python
def process_file(self, request):
    """Process a file with input validation."""
    if not request.file_path:
        raise ValueError("File path is required")
    
    if not os.path.exists(request.file_path):
        raise FileNotFoundError(f"File not found: {request.file_path}")
    
    # Continue with processing
```

### Access Control

Services assume authorized access and delegate authentication to the API layer:

```python
def query_data(self, request):
    """Query data (assumes authorized access)."""
    # Authentication is handled at the API layer
    # This service focuses on business logic
    return self.mongodb_connector.query(request.collection_name, request.query)
```

## Configuration

### Service Configuration

Services can be configured through dependency injection:

```python
class DataProcessingService:
    def __init__(self, mongodb_connector, batch_size=1000, timeout=30):
        self.mongodb_connector = mongodb_connector
        self.batch_size = batch_size
        self.timeout = timeout
```

### Environment Variables

Services can use environment variables for configuration:

```python
import os

class FileProcessorService:
    def __init__(self, mongodb_connector):
        self.mongodb_connector = mongodb_connector
        self.max_file_size = int(os.getenv('MAX_FILE_SIZE', '100MB'))
        self.supported_formats = os.getenv('SUPPORTED_FORMATS', 'csv,xlsx').split(',')
```

## Future Enhancements

### Planned Features

1. **Async Processing**: Support for async file processing
2. **Event-Driven Architecture**: Publish events for processing milestones
3. **Retry Logic**: Automatic retry for failed operations
4. **Streaming**: Process files as streams for memory efficiency
5. **Caching Layer**: Redis-based caching for frequently accessed data

### Extension Points

Services are designed to be extensible:

- New file types can be added to `FileProcessorService`
- New query methods can be added to `QueryService`
- New processing workflows can be added to `DataProcessingService`
- Additional services can be created for new business logic

## Best Practices

1. **Single Responsibility**: Each service has one clear purpose
2. **Dependency Injection**: Use dependency injection for external dependencies
3. **Error Handling**: Implement comprehensive error handling
4. **Logging**: Use structured logging for debugging
5. **Testing**: Write comprehensive unit and integration tests
6. **Documentation**: Document all public methods and classes
7. **Type Hints**: Use type hints for better code clarity
8. **Validation**: Validate all input parameters

---

*This documentation is part of the KnowledgeForge Enterprise Data Intelligence Platform.* 