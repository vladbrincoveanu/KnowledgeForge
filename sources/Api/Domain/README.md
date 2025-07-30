# Domain Layer

## Overview

The Domain layer contains the core business logic, entities, and data transfer objects (DTOs) that represent the heart of the KnowledgeForge application. This layer is independent of external concerns and defines the business rules and data structures used throughout the application.

## Architecture Principles

- **Pure Business Logic**: Contains only business rules and domain entities
- **No External Dependencies**: Independent of databases, frameworks, or external services
- **Single Source of Truth**: Defines the core data structures used across all layers
- **Immutable Design**: Domain objects are designed to be immutable where possible

## File Structure

```
Domain/
├── models.py          # Core business entities and value objects
├── dtos.py            # Data Transfer Objects for API communication
├── __init__.py        # Package initialization
└── README.md          # This documentation
```

## Core Components

### 1. Business Entities (`models.py`)

#### DataType Enum
Represents the different data types that can be inferred from file columns.

```python
class DataType(Enum):
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    UNKNOWN = "unknown"
```

#### ColumnMetadata
Represents metadata about a single column in a data file.

```python
@dataclass
class ColumnMetadata:
    name: str
    data_type: DataType
    sample_values: List[Any]
    null_count: int
    unique_count: int
    total_count: int
```

#### FileInfo
Contains basic information about a processed file.

```python
@dataclass
class FileInfo:
    file_name: str
    file_size: int
    created_date: datetime
    modified_date: datetime
    file_path: str
```

#### DataRow
Represents a single row of data with its metadata.

```python
@dataclass
class DataRow:
    row_number: int
    data: Dict[str, Any]
    metadata: Dict[str, Any]
```

#### FileMetadata
Comprehensive metadata about a processed file.

```python
@dataclass
class FileMetadata:
    file_info: FileInfo
    columns: List[ColumnMetadata]
    total_rows: int
    processing_date: datetime
    file_type: str
```

#### ProcessingResult
Result of a file processing operation.

```python
@dataclass
class ProcessingResult:
    success: bool
    message: str
    file_metadata: Optional[FileMetadata]
    error: Optional[str]
    processing_time: float
```

#### ProcessingStatus Enum
Status of a processing operation.

```python
class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
```

### 2. Data Transfer Objects (`dtos.py`)

DTOs are used for API communication and define the contract between the API layer and external clients.

#### ProcessFileRequest
Request to process a single file.

```python
@dataclass
class ProcessFileRequest:
    file_path: str
    collection_name: Optional[str] = None
    sheet_name: Optional[str] = None
```

#### ProcessDirectoryRequest
Request to process all files in a directory.

```python
@dataclass
class ProcessDirectoryRequest:
    directory_path: str
    file_patterns: Optional[List[str]] = None
```

#### ProcessingResponse
Response from a processing operation.

```python
@dataclass
class ProcessingResponse:
    success: bool
    message: str
    data: Optional[Dict[str, Any]]
    error: Optional[str]
```

#### QueryRequest
Request to query data from a collection.

```python
@dataclass
class QueryRequest:
    collection_name: str
    query: Dict[str, Any]
    limit: Optional[int] = 10
    skip: Optional[int] = 0
```

#### QueryResponse
Response from a query operation.

```python
@dataclass
class QueryResponse:
    success: bool
    message: str
    data: Optional[List[Dict[str, Any]]]
    total_count: Optional[int]
    error: Optional[str]
```

#### StatusResponse
Response containing system status information.

```python
@dataclass
class StatusResponse:
    success: bool
    message: str
    data: Optional[Dict[str, Any]]
    error: Optional[str]
```

## Usage Examples

### Creating Domain Objects

```python
from Api.Domain.models import DataType, ColumnMetadata, FileInfo, DataRow

# Create a column metadata
column = ColumnMetadata(
    name="customer_id",
    data_type=DataType.INTEGER,
    sample_values=[1, 2, 3, 4, 5],
    null_count=0,
    unique_count=100,
    total_count=100
)

# Create file info
file_info = FileInfo(
    file_name="customers.csv",
    file_size=1024,
    created_date=datetime.now(),
    modified_date=datetime.now(),
    file_path="/path/to/customers.csv"
)

# Create a data row
data_row = DataRow(
    row_number=1,
    data={"customer_id": 1, "name": "John Doe"},
    metadata={"source": "csv", "processed_at": datetime.now()}
)
```

### Using DTOs

```python
from Api.Domain.dtos import ProcessFileRequest, QueryRequest

# Create a processing request
request = ProcessFileRequest(
    file_path="/path/to/data.csv",
    collection_name="customers"
)

# Create a query request
query = QueryRequest(
    collection_name="customers",
    query={"age": {"$gte": 18}},
    limit=50
)
```

## Design Patterns

### 1. Value Objects
Domain objects like `DataType` and `ProcessingStatus` are implemented as enums to ensure type safety and prevent invalid states.

### 2. Data Classes
Most domain objects use Python's `@dataclass` decorator for automatic generation of `__init__`, `__repr__`, and other special methods.

### 3. Immutability
Domain objects are designed to be immutable where possible, preventing accidental modifications to business data.

### 4. Type Hints
All domain objects use comprehensive type hints to improve code clarity and enable better IDE support.

## Validation Rules

### Column Metadata
- Column names must be non-empty strings
- Sample values must be a list
- Counts must be non-negative integers
- Data types must be valid enum values

### File Information
- File names must be non-empty strings
- File sizes must be positive integers
- Dates must be valid datetime objects
- File paths must be valid strings

### Data Rows
- Row numbers must be positive integers
- Data must be a dictionary
- Metadata must be a dictionary

## Error Handling

Domain objects include validation and error handling:

```python
# Example validation in a domain object
def validate_column_metadata(self):
    if not self.name or not isinstance(self.name, str):
        raise ValueError("Column name must be a non-empty string")
    
    if self.null_count < 0:
        raise ValueError("Null count cannot be negative")
    
    if self.unique_count > self.total_count:
        raise ValueError("Unique count cannot exceed total count")
```

## Testing

Domain objects should be thoroughly tested:

```python
# Example test for domain object
def test_column_metadata_validation():
    # Valid column metadata
    column = ColumnMetadata(
        name="test_column",
        data_type=DataType.STRING,
        sample_values=["a", "b", "c"],
        null_count=0,
        unique_count=3,
        total_count=3
    )
    assert column.name == "test_column"
    assert column.data_type == DataType.STRING
    
    # Invalid column metadata should raise error
    with pytest.raises(ValueError):
        ColumnMetadata(
            name="",  # Empty name
            data_type=DataType.STRING,
            sample_values=[],
            null_count=0,
            unique_count=0,
            total_count=0
        )
```

## Best Practices

1. **Keep Domain Objects Pure**: Don't add external dependencies or framework-specific code
2. **Use Type Hints**: Always include comprehensive type hints
3. **Validate Input**: Include validation logic in domain objects
4. **Document Business Rules**: Use docstrings to explain business logic
5. **Test Thoroughly**: Write comprehensive tests for all domain objects
6. **Use Enums for Constants**: Use enums for fixed sets of values
7. **Keep Objects Small**: Each domain object should have a single responsibility

## Future Enhancements

### Planned Features
1. **Domain Events**: Add domain events for important business operations
2. **Aggregates**: Implement aggregate patterns for complex business entities
3. **Specifications**: Add specification pattern for complex business rules
4. **Value Object Validation**: Enhanced validation for value objects
5. **Domain Services**: Add domain services for complex business logic

### Extension Points
- New data types can be added to the `DataType` enum
- New processing statuses can be added to the `ProcessingStatus` enum
- Additional metadata fields can be added to domain objects
- New DTOs can be created for additional API endpoints

---

*This documentation is part of the KnowledgeForge Enterprise Data Intelligence Platform.* 