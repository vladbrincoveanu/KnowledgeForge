# API Layer

## Overview

The API layer is the entry point for all external requests to the KnowledgeForge application. It handles HTTP requests, validates input data, coordinates with the application layer, and returns appropriate responses. This layer is built using FastAPI and provides a RESTful interface for data processing and querying operations.

## Architecture Principles

- **Request/Response Handling**: Manages HTTP requests and responses
- **Input Validation**: Validates and sanitizes all incoming data
- **Error Handling**: Provides consistent error responses
- **Documentation**: Auto-generates API documentation
- **CORS Support**: Handles cross-origin requests
- **Rate Limiting**: Implements request rate limiting

## File Structure

```
Api/
├── main.py                      # FastAPI application and endpoints
├── __init__.py                  # Package initialization
└── README.md                    # This documentation
```

## Core Components

### FastAPI Application (`main.py`)

**Purpose:** Main FastAPI application that defines all API endpoints, middleware, and application configuration.

**Key Features:**
- RESTful API endpoints
- Automatic request/response validation
- OpenAPI documentation generation
- CORS middleware
- Error handling middleware
- Health check endpoints

**Main Endpoints:**
- `POST /process/file` - Process a single file
- `POST /process/directory` - Process all files in a directory
- `POST /query` - Query data from collections
- `GET /collections` - List all collections
- `GET /collections/{name}` - Get collection information
- `DELETE /collections/{name}` - Delete a collection
- `GET /health` - Health check endpoint

## API Endpoints

### 1. File Processing Endpoints

#### Process Single File
```http
POST /process/file
Content-Type: multipart/form-data

file: <file>
collection_name: <string> (optional)
sheet_name: <string> (optional, for Excel files)
```

**Request Example:**
```bash
curl -X POST "http://localhost:8000/process/file" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@data.csv" \
  -F "collection_name=customers"
```

**Response Example:**
```json
{
  "success": true,
  "message": "File processed successfully",
  "data": {
    "collection_name": "customers",
    "total_rows": 1000,
    "processing_time": 2.5,
    "file_metadata": {
      "file_name": "data.csv",
      "file_size": 102400,
      "columns": [
        {
          "name": "customer_id",
          "data_type": "integer",
          "null_count": 0,
          "unique_count": 1000
        }
      ]
    }
  }
}
```

#### Process Directory
```http
POST /process/directory
Content-Type: application/json

{
  "directory_path": "/path/to/directory",
  "file_patterns": ["*.csv", "*.xlsx"] (optional)
}
```

**Request Example:**
```bash
curl -X POST "http://localhost:8000/process/directory" \
  -H "Content-Type: application/json" \
  -d '{
    "directory_path": "/data/",
    "file_patterns": ["*.csv", "*.xlsx"]
  }'
```

### 2. Data Querying Endpoints

#### Query Data
```http
POST /query
Content-Type: application/json

{
  "collection_name": "customers",
  "query": {"age": {"$gte": 18}},
  "limit": 50,
  "skip": 0
}
```

**Request Example:**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "collection_name": "customers",
    "query": {"age": {"$gte": 18}},
    "limit": 50
  }'
```

**Response Example:**
```json
{
  "success": true,
  "message": "Query executed successfully",
  "data": [
    {
      "customer_id": 1,
      "name": "John Doe",
      "age": 30,
      "email": "john@example.com"
    }
  ],
  "total_count": 500
}
```

### 3. Collection Management Endpoints

#### List Collections
```http
GET /collections
```

**Response Example:**
```json
{
  "success": true,
  "message": "Collections retrieved successfully",
  "data": [
    {
      "name": "customers",
      "count": 1000,
      "created_date": "2024-01-15T10:30:00Z"
    },
    {
      "name": "products",
      "count": 500,
      "created_date": "2024-01-15T11:00:00Z"
    }
  ]
}
```

#### Get Collection Information
```http
GET /collections/{collection_name}
```

**Response Example:**
```json
{
  "success": true,
  "message": "Collection information retrieved successfully",
  "data": {
    "name": "customers",
    "count": 1000,
    "created_date": "2024-01-15T10:30:00Z",
    "metadata": {
      "file_name": "customers.csv",
      "total_rows": 1000,
      "columns": [
        {
          "name": "customer_id",
          "data_type": "integer",
          "null_count": 0,
          "unique_count": 1000
        }
      ]
    }
  }
}
```

#### Delete Collection
```http
DELETE /collections/{collection_name}
```

**Response Example:**
```json
{
  "success": true,
  "message": "Collection deleted successfully",
  "data": {
    "deleted_collection": "customers",
    "deleted_count": 1000
  }
}
```

### 4. Health Check Endpoint

#### Health Check
```http
GET /health
```

**Response Example:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T12:00:00Z",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "api": "running"
  }
}
```

## Request/Response Models

### Request Models

```python
from pydantic import BaseModel
from typing import Optional, List

class ProcessFileRequest(BaseModel):
    collection_name: Optional[str] = None
    sheet_name: Optional[str] = None

class ProcessDirectoryRequest(BaseModel):
    directory_path: str
    file_patterns: Optional[List[str]] = None

class QueryRequest(BaseModel):
    collection_name: str
    query: dict
    limit: Optional[int] = 10
    skip: Optional[int] = 0
```

### Response Models

```python
class ProcessingResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None

class QueryResponse(BaseModel):
    success: bool
    message: str
    data: Optional[List[dict]] = None
    total_count: Optional[int] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    services: dict
```

## Error Handling

### HTTP Status Codes

- **200 OK**: Request successful
- **400 Bad Request**: Invalid request data
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Validation error
- **500 Internal Server Error**: Server error

### Error Response Format

```json
{
  "success": false,
  "message": "Human-readable error message",
  "error": "Technical error details",
  "status_code": 400
}
```

### Common Error Scenarios

#### File Not Found
```json
{
  "success": false,
  "message": "File not found",
  "error": "File '/path/to/file.csv' does not exist",
  "status_code": 404
}
```

#### Invalid File Format
```json
{
  "success": false,
  "message": "Unsupported file format",
  "error": "File must be CSV or XLSX format",
  "status_code": 400
}
```

#### Database Connection Error
```json
{
  "success": false,
  "message": "Database connection failed",
  "error": "Failed to connect to MongoDB",
  "status_code": 500
}
```

## Middleware

### CORS Middleware

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Request Logging Middleware

```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    processing_time = time.time() - start_time
    
    logger.info(
        f"{request.method} {request.url.path} - "
        f"{response.status_code} - {processing_time:.2f}s"
    )
    
    return response
```

## Input Validation

### File Upload Validation

```python
async def process_file(
    file: UploadFile = File(...),
    collection_name: Optional[str] = Form(None),
    sheet_name: Optional[str] = Form(None)
):
    # Validate file type
    if not file.filename.lower().endswith(('.csv', '.xlsx')):
        raise HTTPException(
            status_code=400,
            detail="File must be CSV or XLSX format"
        )
    
    # Validate file size
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE} bytes"
        )
```

### Query Validation

```python
def validate_query(query: dict):
    """Validate MongoDB query structure."""
    if not isinstance(query, dict):
        raise ValueError("Query must be a dictionary")
    
    # Add additional validation as needed
    return query
```

## Security

### Input Sanitization

```python
def sanitize_collection_name(name: str) -> str:
    """Sanitize collection name for security."""
    if not name or not isinstance(name, str):
        raise ValueError("Collection name must be a non-empty string")
    
    # Remove dangerous characters
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    
    if not sanitized:
        raise ValueError("Invalid collection name")
    
    return sanitized
```

### Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/process/file")
@limiter.limit("10/minute")
async def process_file(request: Request, ...):
    # Endpoint implementation
```

## Documentation

### OpenAPI/Swagger Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: Available at `/docs`
- **ReDoc**: Available at `/redoc`
- **OpenAPI JSON**: Available at `/openapi.json`

### Custom Documentation

```python
@app.post(
    "/process/file",
    response_model=ProcessingResponse,
    summary="Process a single file",
    description="Upload and process a CSV or XLSX file, extracting metadata and storing data in MongoDB.",
    tags=["File Processing"]
)
async def process_file(
    file: UploadFile = File(..., description="CSV or XLSX file to process"),
    collection_name: Optional[str] = Form(None, description="Custom collection name"),
    sheet_name: Optional[str] = Form(None, description="Excel sheet name (for XLSX files)")
):
    """
    Process a single file and store its data in MongoDB.
    
    - **file**: CSV or XLSX file to process
    - **collection_name**: Optional custom collection name
    - **sheet_name**: Optional sheet name for Excel files
    
    Returns processing result with metadata.
    """
    # Implementation
```

## Testing

### API Testing

```python
from fastapi.testclient import TestClient
from Api.Api.main import app

client = TestClient(app)

def test_process_file_endpoint():
    # Test file processing
    with open("test.csv", "rb") as f:
        response = client.post(
            "/process/file",
            files={"file": ("test.csv", f, "text/csv")},
            data={"collection_name": "test"}
        )
    
    assert response.status_code == 200
    assert response.json()["success"] == True

def test_query_endpoint():
    # Test data querying
    response = client.post(
        "/query",
        json={
            "collection_name": "test",
            "query": {},
            "limit": 10
        }
    )
    
    assert response.status_code == 200
    assert response.json()["success"] == True
```

### Integration Testing

```python
def test_full_workflow():
    # Test complete workflow: upload -> process -> query
    # 1. Upload file
    with open("test.csv", "rb") as f:
        upload_response = client.post(
            "/process/file",
            files={"file": ("test.csv", f, "text/csv")}
        )
    
    assert upload_response.status_code == 200
    
    # 2. Query data
    query_response = client.post(
        "/query",
        json={"collection_name": "test", "query": {}}
    )
    
    assert query_response.status_code == 200
    assert len(query_response.json()["data"]) > 0
```

## Performance

### Response Caching

```python
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

@app.on_event("startup")
async def startup():
    redis = aioredis.from_url("redis://localhost", encoding="utf8")
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")

@app.get("/collections")
@cache(expire=60)
async def list_collections():
    # Cache collection list for 60 seconds
    return query_service.list_collections()
```

### Async Processing

```python
@app.post("/process/file")
async def process_file(file: UploadFile):
    # Process file asynchronously
    task = asyncio.create_task(process_file_async(file))
    return {"task_id": task.get_name()}

async def process_file_async(file: UploadFile):
    # Async file processing
    result = await data_service.process_file_async(file)
    return result
```

## Monitoring

### Health Checks

```python
@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": {}
    }
    
    # Check database connection
    try:
        mongodb_connector.connect()
        health_status["services"]["database"] = "connected"
    except Exception as e:
        health_status["services"]["database"] = "disconnected"
        health_status["status"] = "unhealthy"
    
    # Check API status
    health_status["services"]["api"] = "running"
    
    return health_status
```

### Metrics Collection

```python
from prometheus_client import Counter, Histogram

# Define metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')

@app.middleware("http")
async def collect_metrics(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    REQUEST_DURATION.observe(duration)
    
    return response
```

## Future Enhancements

### Planned Features

1. **Authentication**: JWT-based authentication
2. **Authorization**: Role-based access control
3. **WebSocket Support**: Real-time processing updates
4. **File Upload Progress**: Progress tracking for large files
5. **Batch Operations**: Bulk file processing endpoints

### Extension Points

- New endpoints can be added for additional functionality
- Custom middleware can be implemented for specific requirements
- Response models can be extended for new data types
- Authentication and authorization can be integrated

## Best Practices

1. **Input Validation**: Always validate and sanitize input data
2. **Error Handling**: Provide consistent error responses
3. **Documentation**: Keep API documentation up to date
4. **Security**: Implement proper security measures
5. **Performance**: Use caching and async processing where appropriate
6. **Testing**: Write comprehensive API tests
7. **Monitoring**: Implement health checks and metrics
8. **Versioning**: Plan for API versioning

---

*This documentation is part of the KnowledgeForge Enterprise Data Intelligence Platform.* 