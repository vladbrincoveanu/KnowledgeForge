# KnowledgeForge - Enterprise Data Intelligence Platform

Transform your enterprise data into intelligent knowledge networks with KnowledgeForge.

KnowledgeForge is a platform designed to help organizations seamlessly convert their data into structured, intelligent knowledge systems. With a focus on clarity, usability, and scalability, KnowledgeForge empowers teams to extract insights, foster collaboration, and drive innovation using their existing information resources.

## 🌐 Landing Page

Check out the live demo and learn more about the project at:  
👉 [https://knowlyai.netlify.app/](https://knowlyai.netlify.app/)

---

# Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Docker Infrastructure](#docker-infrastructure)
5. [Application Services](#application-services)
6. [API Documentation](#api-documentation)
7. [Development Guide](#development-guide)
8. [Testing](#testing)
9. [Deployment](#deployment)
10. [Landing Page](#landing-page)
11. [Migration Guide](#migration-guide)
12. [Troubleshooting](#troubleshooting)

---

# Project Overview

## 🎯 What is KnowledgeForge?

KnowledgeForge is an enterprise-grade data processing and knowledge management platform that:

- **Processes multiple data formats** (CSV, XLSX, PDF, databases, SAP)
- **Extracts metadata** and creates intelligent schemas
- **Stores data** in MongoDB with full metadata preservation
- **Provides query capabilities** for business intelligence
- **Offers enterprise security** and compliance features
- **Scales horizontally** for large enterprise deployments

## 🚀 Key Features

- **Multi-format Support**: CSV, XLSX, and more
- **Intelligent Metadata Extraction**: Automatic schema inference
- **MongoDB Integration**: Scalable document storage
- **RESTful API**: Easy integration with existing systems
- **Docker Deployment**: Production-ready infrastructure
- **Clean Architecture**: Maintainable and testable codebase
- **Enterprise Security**: On-premise deployment options

---

# Architecture

## 🏗️ Clean Architecture Implementation

The application follows clean architecture principles with proper separation of concerns:

```
sources/
├── Api/                          # API Layer
│   ├── Api/                     # FastAPI endpoints and controllers
│   │   └── main.py             # Main FastAPI application
│   ├── Application/             # Application services and business logic
│   │   └── services/           # Split business services
│   │       ├── data_processing_service.py
│   │       ├── file_processor_service.py
│   │       └── query_service.py
│   ├── Domain/                 # Domain models, DTOs, and business rules
│   │   ├── models.py          # Core business entities
│   │   └── dtos.py            # Data Transfer Objects
│   └── Infrastructure/         # External dependencies
│       ├── mongodb_connector.py # MongoDB operations
│       ├── csv_metadata_extractor.py # CSV processing
│       └── xlsx_metadata_extractor.py # XLSX processing
├── Tests/                       # Test suite
│   └── unit/                   # Unit tests
│       └── test_domain_models.py
├── LandingPage/                 # Marketing landing page
├── docker-compose.yml          # Production infrastructure
├── docker-compose.dev.yml      # Development infrastructure
├── Dockerfile                  # Application container
├── main.py                     # Application entry point
├── process_data.py             # Data processing script
└── requirements.txt            # Dependencies
```

## 📋 Architecture Layers

### 1. Domain Layer (`Api/Domain/`)
- **Purpose**: Core business logic and entities
- **Components**:
  - `models.py`: Business entities (DataType, ColumnMetadata, FileInfo, etc.)
  - `dtos.py`: Data Transfer Objects for API communication
- **Dependencies**: None (pure business logic)

### 2. Application Layer (`Api/Application/`)
- **Purpose**: Use cases and business orchestration
- **Components**:
  - `services/`: Split business services
    - `data_processing_service.py`: Main orchestration
    - `file_processor_service.py`: File processing logic
    - `query_service.py`: Data querying operations
- **Dependencies**: Domain layer, Infrastructure layer

### 3. Infrastructure Layer (`Api/Infrastructure/`)
- **Purpose**: External dependencies and data access
- **Components**:
  - `mongodb_connector.py`: MongoDB operations
  - `csv_metadata_extractor.py`: CSV file processing
  - `xlsx_metadata_extractor.py`: XLSX file processing
- **Dependencies**: Domain layer

### 4. API Layer (`Api/Api/`)
- **Purpose**: HTTP endpoints and request handling
- **Components**:
  - `main.py`: FastAPI application with all endpoints
- **Dependencies**: Application layer

## 🔄 Data Flow

1. **Request**: Client sends HTTP request to API layer
2. **Validation**: API layer validates input using DTOs
3. **Orchestration**: Application layer coordinates business logic
4. **Processing**: Infrastructure layer handles external operations
5. **Response**: Results flow back through layers to client

---

# Quick Start

## 🚀 Prerequisites

- Python 3.11+
- Docker and Docker Compose
- MongoDB (or use Docker)
- At least 4GB RAM and 10GB disk space

## 📦 Installation

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd Knowlly/sources

# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

### Option 2: Local Development

```bash
# Clone the repository
git clone <repository-url>
cd Knowlly/sources

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start MongoDB (if not using Docker)
# brew services start mongodb/brew/mongodb-community

# Run the API
python main.py
```

## 🧪 Testing the Setup

```bash
# Test service structure
python test_services_structure.py

# Test Docker setup
python test_docker_setup.py

# Run unit tests
pytest Tests/
```

---

# Docker Infrastructure

## 🏗️ Infrastructure Overview

The Docker Compose setup includes the following services:

### Core Services
- **MongoDB**: Primary database for data storage
- **Redis**: Caching and session management
- **MinIO**: Object storage for files
- **API**: FastAPI application
- **Nginx**: Reverse proxy and load balancer

### Development Tools
- **MongoDB Express**: Web-based MongoDB admin interface
- **Redis Commander**: Web-based Redis admin interface
- **Portainer**: Docker management UI

## 🚀 Quick Start

### Production Setup

1. **Start all services:**
   ```bash
   docker-compose up -d
   ```

2. **Check service status:**
   ```bash
   docker-compose ps
   ```

3. **View logs:**
   ```bash
   docker-compose logs -f api
   ```

### Development Setup

1. **Start development infrastructure:**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

2. **Run the API locally:**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Run the API
   python main.py
   ```

## 📊 Service Ports

| Service | Port | Description |
|---------|------|-------------|
| API | 8000 | FastAPI application |
| Nginx | 80 | HTTP reverse proxy |
| MongoDB | 27017 | Database |
| MongoDB Express | 8081 | MongoDB admin UI |
| Redis | 6379 | Cache |
| Redis Commander | 8082 | Redis admin UI |
| MinIO | 9000 | Object storage API |
| MinIO Console | 9001 | MinIO admin UI |
| Portainer | 9002 | Docker management UI |

## 🔧 Configuration

### Environment Variables

The API service uses the following environment variables:

```bash
MONGODB_URI=mongodb://admin:knowlly123@mongodb:27017/knowlly_data?authSource=admin
REDIS_URL=redis://redis:6379
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=knowlly123
LOG_LEVEL=INFO
```

### MongoDB Configuration

- **Database**: `knowlly_data`
- **Username**: `admin`
- **Password**: `knowlly123`
- **Authentication**: `admin` database

### Redis Configuration

- **Port**: 6379
- **No authentication** (development setup)
- **Persistence**: Enabled with volume mounting

### MinIO Configuration

- **Access Key**: `minioadmin`
- **Secret Key**: `knowlly123`
- **Console**: Available at `http://localhost:9001`

## 🛠️ Management Commands

### Start Services
```bash
# Production
docker-compose up -d

# Development (infrastructure only)
docker-compose -f docker-compose.dev.yml up -d
```

### Stop Services
```bash
# Production
docker-compose down

# Development
docker-compose -f docker-compose.dev.yml down
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f mongodb
```

### Restart Services
```bash
# All services
docker-compose restart

# Specific service
docker-compose restart api
```

### Update Services
```bash
# Pull latest images
docker-compose pull

# Rebuild and restart
docker-compose up -d --build
```

### Clean Up
```bash
# Stop and remove containers
docker-compose down

# Remove volumes (WARNING: This will delete all data)
docker-compose down -v

# Remove images
docker-compose down --rmi all
```

## 🔍 Monitoring and Debugging

### Health Checks

All services include health checks:

```bash
# Check health status
docker-compose ps

# View health check logs
docker inspect knowlly-api | grep -A 10 Health
```

### Accessing Services

#### MongoDB
```bash
# Connect via command line
docker exec -it knowlly-mongodb mongosh -u admin -p knowlly123

# Web interface: http://localhost:8081
# Username: admin, Password: knowlly123
```

#### Redis
```bash
# Connect via command line
docker exec -it knowlly-redis redis-cli

# Web interface: http://localhost:8082
```

#### MinIO
```bash
# Web interface: http://localhost:9001
# Access Key: minioadmin, Secret Key: knowlly123
```

#### API
```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs
```

## 📁 Data Persistence

### Volumes

The following data is persisted:

- **MongoDB**: `mongodb_data` - Database files
- **Redis**: `redis_data` - Cache data
- **MinIO**: `minio_data` - Object storage
- **Portainer**: `portainer_data` - Management data

### Backup

```bash
# Backup MongoDB
docker exec knowlly-mongodb mongodump --out /backup

# Backup Redis
docker exec knowlly-redis redis-cli BGSAVE

# Backup MinIO data
# Use MinIO client (mc) to sync data
```

## 🔒 Security Considerations

### Production Deployment

1. **Change default passwords** in `docker-compose.yml`
2. **Enable HTTPS** by uncommenting SSL configuration in Nginx
3. **Add SSL certificates** to `docker/nginx/ssl/`
4. **Configure firewall** rules
5. **Use secrets management** for sensitive data

### Environment Variables

For production, use environment files:

```bash
# Create .env file
MONGODB_PASSWORD=your_secure_password
REDIS_PASSWORD=your_redis_password
MINIO_SECRET_KEY=your_minio_secret
```

---

# Application Services

## 🏗️ Services Architecture

The services follow a clean architecture pattern where each service has a single responsibility and clear dependencies:

```
services/
├── __init__.py                    # Package initialization and exports
├── data_processing_service.py     # Main orchestration service
├── file_processor_service.py      # File processing logic
├── query_service.py              # Data querying and collection management
└── README.md                     # This documentation
```

## 📋 Services Overview

### 1. DataProcessingService
**File:** `data_processing_service.py`

**Purpose:** Main orchestration service that coordinates file processing operations.

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

### 2. FileProcessorService
**File:** `file_processor_service.py`

**Purpose:** Handle the actual file processing logic for different file types.

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

### 3. QueryService
**File:** `query_service.py`

**Purpose:** Handle data querying and collection management operations.

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

## 🔄 Service Dependencies

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

## 🚀 Usage Examples

### Importing Services

```python
# Import specific services
from Api.Application.services.data_processing_service import DataProcessingService
from Api.Application.services.query_service import QueryService
from Api.Application.services.file_processor_service import FileProcessorService

# Or import from the package
from Api.Application.services import DataProcessingService, QueryService, FileProcessorService
```

### Using DataProcessingService

```python
from Api.Infrastructure.mongodb_connector import MongoDBConnector
from Api.Application.services import DataProcessingService
from Api.Domain.dtos import ProcessFileRequest

# Initialize
mongodb_connector = MongoDBConnector()
data_service = DataProcessingService(mongodb_connector)

# Process a file
request = ProcessFileRequest(file_path="data.csv")
response = data_service.process_file(request)
```

### Using QueryService

```python
from Api.Application.services import QueryService

# Initialize
query_service = QueryService(mongodb_connector)

# Get collection info
info = query_service.get_collection_info("csv_customers")

# List all collections
collections = query_service.list_collections()

# Search collections
results = query_service.search_collections("customer")
```

### Using FileProcessorService

```python
from Api.Application.services import FileProcessorService

# Initialize
file_processor = FileProcessorService(mongodb_connector)

# Process a file directly
result = file_processor.process_file("data.csv", "customers")
```

## 🔧 Service Configuration

### Logging

All services use the standard Python logging module:

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Processing file...")
logger.error("Error occurred: %s", error_message)
```

### Error Handling

Services follow a consistent error handling pattern:

1. **Try-catch blocks** around all operations
2. **Logging** of errors with context
3. **Return of structured responses** with success/error information
4. **Graceful degradation** when possible

### Dependencies

Services are designed to be dependency-injected:

```python
# Good: Dependency injection
service = DataProcessingService(mongodb_connector)

# Avoid: Hard-coded dependencies
service = DataProcessingService()  # Don't do this
```

## 🧪 Testing

### Unit Testing

Each service should have corresponding unit tests:

```python
# tests/test_data_processing_service.py
def test_process_file_success():
    # Arrange
    mock_connector = MockMongoDBConnector()
    service = DataProcessingService(mock_connector)
    
    # Act
    result = service.process_file(request)
    
    # Assert
    assert result.success == True
```

### Integration Testing

Test service interactions:

```python
# tests/test_service_integration.py
def test_data_processing_with_file_processor():
    # Test that DataProcessingService correctly delegates to FileProcessorService
    pass
```

## 📈 Performance Considerations

### Batch Processing

- File processing uses batch inserts for efficiency
- Large files are processed in chunks
- Memory usage is optimized for large datasets

### Caching

- Collection metadata is cached when possible
- Query results can be cached for frequently accessed data

### Async Operations

- Services are designed to be async-compatible
- Long-running operations can be made async in the future

## 🔒 Security

### Input Validation

- All file paths are validated
- Collection names are sanitized
- Query parameters are validated

### Access Control

- Services don't handle authentication directly
- Authentication should be handled at the API layer
- Services assume authorized access

## 🚨 Error Handling

### Common Error Scenarios

1. **File not found** - Return appropriate error message
2. **Invalid file format** - Validate file type before processing
3. **Database connection issues** - Handle connection failures gracefully
4. **Memory issues** - Process large files in chunks

### Error Response Format

```python
{
    "success": False,
    "message": "Human-readable error message",
    "error": "Technical error details",
    "data": None
}
```

## 🔄 Future Enhancements

### Planned Features

1. **Async Processing** - Support for async file processing
2. **Streaming** - Process files as streams for memory efficiency
3. **Caching Layer** - Redis-based caching for frequently accessed data
4. **Event System** - Publish events for processing milestones
5. **Retry Logic** - Automatic retry for failed operations

### Extension Points

Services are designed to be extensible:

- New file types can be added to FileProcessorService
- New query methods can be added to QueryService
- New processing workflows can be added to DataProcessingService

---

# API Documentation

## 🚀 API Endpoints

### Health Check
```http
GET /health
```

### Process File
```http
POST /process/file
Content-Type: multipart/form-data

file: <file>
```

### Process Directory
```http
POST /process/directory
Content-Type: application/json

{
  "directory_path": "/path/to/directory"
}
```

### Query Data
```http
POST /query
Content-Type: application/json

{
  "collection_name": "customers",
  "query": {},
  "limit": 10
}
```

### List Collections
```http
GET /collections
```

### Get Collection Info
```http
GET /collections/{collection_name}
```

### Delete Collection
```http
DELETE /collections/{collection_name}
```

## 📊 Response Formats

### Success Response
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response data
  }
}
```

### Error Response
```json
{
  "success": false,
  "message": "Human-readable error message",
  "error": "Technical error details"
}
```

---

# Development Guide

## 🛠️ Development Setup

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- Git

### Local Development

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Knowlly/sources
   ```

2. **Set up virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start infrastructure:**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

5. **Run the application:**
   ```bash
   python main.py
   ```

### Code Structure

```
sources/
├── Api/
│   ├── Domain/           # Business entities and DTOs
│   ├── Application/      # Business logic services
│   ├── Infrastructure/   # External dependencies
│   └── Api/             # API endpoints
├── Tests/               # Test suite
├── LandingPage/         # Marketing site
└── docker/             # Docker configuration
```

### Development Workflow

1. **Create feature branch:**
   ```bash
   git checkout -b feature/new-feature
   ```

2. **Make changes and test:**
   ```bash
   # Run tests
   pytest Tests/
   
   # Run linting
   flake8 Api/
   
   # Run type checking
   mypy Api/
   ```

3. **Commit changes:**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

4. **Push and create PR:**
   ```bash
   git push origin feature/new-feature
   ```

## 🔧 Configuration

### Environment Variables

Create a `.env` file for local development:

```bash
MONGODB_URI=mongodb://localhost:27017/knowlly_data
REDIS_URL=redis://localhost:6379
LOG_LEVEL=DEBUG
```

### IDE Setup

#### VS Code
Install the following extensions:
- Python
- Pylance
- Docker
- REST Client

#### PyCharm
Configure:
- Python interpreter (virtual environment)
- Docker integration
- Run configurations

## 📝 Code Style

### Python Style Guide
- Follow PEP 8
- Use type hints
- Write docstrings for all functions
- Keep functions small and focused

### Naming Conventions
- **Files**: snake_case (e.g., `data_processor.py`)
- **Classes**: PascalCase (e.g., `DataProcessingService`)
- **Functions**: snake_case (e.g., `process_file()`)
- **Variables**: snake_case (e.g., `file_path`)

### Import Organization
```python
# Standard library imports
import os
import sys
from typing import List, Dict

# Third-party imports
import pandas as pd
from fastapi import FastAPI

# Local imports
from Api.Domain.models import DataRow
from Api.Application.services import DataProcessingService
```

---

# Testing

## 🧪 Testing Strategy

### Unit Tests
- **Domain Models**: Test business entities and rules
- **Services**: Test business logic in isolation
- **Infrastructure**: Test external integrations with mocks

### Integration Tests
- **API Endpoints**: Test complete request/response cycles
- **Database Operations**: Test MongoDB interactions

### End-to-End Tests
- **Full Workflows**: Test complete data processing pipelines

## 🚀 Running Tests

### All Tests
```bash
pytest Tests/
```

### Specific Test Categories
```bash
# Unit tests only
pytest Tests/unit/

# Integration tests only
pytest Tests/integration/

# End-to-end tests only
pytest Tests/e2e/
```

### Test with Coverage
```bash
pytest Tests/ --cov=Api --cov-report=html
```

### Test with Verbose Output
```bash
pytest Tests/ -v
```

## 📝 Writing Tests

### Unit Test Example
```python
# Tests/unit/test_data_processing_service.py
import pytest
from unittest.mock import Mock
from Api.Application.services import DataProcessingService
from Api.Domain.dtos import ProcessFileRequest

def test_process_file_success():
    # Arrange
    mock_connector = Mock()
    service = DataProcessingService(mock_connector)
    request = ProcessFileRequest(file_path="test.csv")
    
    # Act
    result = service.process_file(request)
    
    # Assert
    assert result.success == True
    assert result.message == "File processed successfully"
```

### Integration Test Example
```python
# Tests/integration/test_api_endpoints.py
import pytest
from fastapi.testclient import TestClient
from Api.Api.main import app

client = TestClient(app)

def test_process_file_endpoint():
    # Arrange
    test_file = "test_data.csv"
    
    # Act
    with open(test_file, "rb") as f:
        response = client.post("/process/file", files={"file": f})
    
    # Assert
    assert response.status_code == 200
    assert response.json()["success"] == True
```

## 🔧 Test Configuration

### pytest.ini
```ini
[tool:pytest]
testpaths = Tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

### Test Data
- Store test data in `Tests/data/`
- Use fixtures for common test data
- Clean up test data after tests

### Mocking
- Mock external dependencies
- Use `unittest.mock` for Python standard library
- Use `pytest-mock` for pytest integration

---

# Deployment

## 🚀 Production Deployment

### Docker Deployment

1. **Build and deploy:**
   ```bash
   # Build images
   docker-compose build
   
   # Deploy to production
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. **Configure environment:**
   ```bash
   # Set production environment variables
   export NODE_ENV=production
   export MONGODB_URI=your_production_mongodb_uri
   export REDIS_URL=your_production_redis_url
   ```

3. **Set up monitoring:**
   ```bash
   # Monitor services
   docker-compose logs -f
   
   # Check health
   curl http://your-domain/health
   ```

### Cloud Deployment

#### AWS
```bash
# Deploy to ECS
aws ecs create-service --cluster knowlly-cluster --service-name knowlly-api

# Deploy to EKS
kubectl apply -f k8s/
```

#### Google Cloud
```bash
# Deploy to GKE
gcloud container clusters create knowlly-cluster
kubectl apply -f k8s/
```

#### Azure
```bash
# Deploy to AKS
az aks create --resource-group knowlly-rg --name knowlly-cluster
kubectl apply -f k8s/
```

## 🔧 Configuration Management

### Environment Variables
```bash
# Production
MONGODB_URI=mongodb://prod-mongo:27017/knowlly_data
REDIS_URL=redis://prod-redis:6379
LOG_LEVEL=INFO
NODE_ENV=production

# Development
MONGODB_URI=mongodb://localhost:27017/knowlly_data
REDIS_URL=redis://localhost:6379
LOG_LEVEL=DEBUG
NODE_ENV=development
```

### Secrets Management
```bash
# Use Docker secrets
echo "your_secret" | docker secret create db_password -

# Use Kubernetes secrets
kubectl create secret generic db-secret --from-literal=password=your_secret
```

## 📊 Monitoring and Logging

### Health Checks
```bash
# Application health
curl http://your-domain/health

# Service health
docker-compose ps
```

### Logging
```bash
# View application logs
docker-compose logs -f api

# View all logs
docker-compose logs -f
```

### Metrics
- Use Prometheus for metrics collection
- Use Grafana for visualization
- Monitor CPU, memory, and disk usage

## 🔒 Security

### SSL/TLS
```nginx
# Nginx SSL configuration
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
}
```

### Authentication
- Implement JWT authentication
- Use OAuth2 for external services
- Implement rate limiting

### Network Security
- Use VPC for network isolation
- Configure firewall rules
- Use security groups

---

# Landing Page

## 📁 Files

- **`index.html`** - Main landing page HTML file
- **`styles.css`** - CSS styles for the landing page

## 🎯 Purpose

The landing page showcases the KnowledgeForge enterprise knowledge graph platform, highlighting:

- **Multi-format data integration** (Excel, PDF, CSV, databases, SAP)
- **Expert-driven curation** with human-in-the-loop approach
- **Intelligent querying** and business insights
- **On-premise security** and compliance
- **Cluster scalability** for enterprise deployment

## 🚀 Usage

### Local Development

1. **Open the HTML file directly:**
   ```bash
   open index.html
   ```

2. **Or serve with a local server:**
   ```bash
   # Using Python
   python -m http.server 8080
   
   # Using Node.js
   npx serve .
   
   # Using PHP
   php -S localhost:8080
   ```

3. **Access at:** `http://localhost:8080`

### Deployment

The landing page can be deployed to any static hosting service:

- **GitHub Pages**
- **Netlify**
- **Vercel**
- **AWS S3**
- **Any web server**

## 🎨 Design Features

- **Responsive design** - Works on desktop, tablet, and mobile
- **Modern UI** - Clean, professional enterprise look
- **Interactive elements** - Hover effects and animations
- **Data flow visualization** - Shows the platform's data processing pipeline
- **Security focus** - Emphasizes enterprise-grade security

## 🔧 Customization

### Colors
The primary brand color is `#2563eb` (blue). You can modify this in `styles.css`:

```css
:root {
    --primary-color: #2563eb;
    --secondary-color: #1d4ed8;
}
```

### Content
Update the content in `index.html` to match your specific:
- Company name and branding
- Feature descriptions
- Contact information
- Call-to-action buttons

### Styling
Modify `styles.css` to adjust:
- Typography (currently using Inter font)
- Layout and spacing
- Animations and transitions
- Responsive breakpoints

## 📱 Responsive Design

The landing page is fully responsive with breakpoints at:
- **Desktop:** 1200px and above
- **Tablet:** 768px - 1199px
- **Mobile:** Below 768px

## 🔗 Integration

This landing page can be integrated with:
- **Analytics** (Google Analytics, Mixpanel)
- **CRM systems** (HubSpot, Salesforce)
- **Email marketing** (Mailchimp, ConvertKit)
- **Chat widgets** (Intercom, Drift)

---

# Migration Guide

## 🔄 Architecture Migration

### Before (Old Structure)
```
Knowlly/
├── api/                           # Old monolithic API directory
│   ├── csv_metadata_extractor.py
│   ├── xlsx_metadata_extractor.py
│   ├── mongodb_connector.py
│   ├── data_processor.py
│   ├── query_examples.py
│   ├── process_data.py
│   ├── main.py
│   ├── README_DATA_PROCESSING.md
│   ├── SYSTEM_SUMMARY.md
│   └── run_tests.py
├── index.html                     # Landing page
├── styles.css                     # Landing page styles
└── README.md
```

### After (New Clean Architecture)
```
Knowlly/
├── sources/                       # Main application directory
│   ├── Api/                       # Clean Architecture layers
│   │   ├── Domain/                # Business entities and DTOs
│   │   ├── Application/           # Business logic services
│   │   │   └── services/          # Split services
│   │   ├── Infrastructure/        # External dependencies
│   │   └── Api/                   # API endpoints
│   ├── Tests/                     # Test suite
│   ├── LandingPage/               # Marketing landing page
│   ├── docker-compose.yml         # Production infrastructure
│   ├── docker-compose.dev.yml     # Development infrastructure
│   ├── Dockerfile                 # Application container
│   ├── main.py                    # Application entry point
│   ├── process_data.py            # Data processing script
│   └── requirements.txt           # Dependencies
├── archive/                       # Archived old files
│   └── old_api/                   # Old API files (backup)
└── README.md                      # Project overview
```

## 🗂️ File Cleanup Summary

### Archived Files (../archive/old_api/)
```
old_api/
├── csv_metadata_extractor.py      # Replaced by Infrastructure layer
├── xlsx_metadata_extractor.py     # Replaced by Infrastructure layer
├── mongodb_connector.py           # Replaced by Infrastructure layer
├── data_processor.py              # Replaced by Application services
├── query_examples.py              # Replaced by QueryService
├── process_data.py                # Replaced by new version
├── main.py                        # Replaced by Api layer
├── README_DATA_PROCESSING.md      # Replaced by new documentation
├── SYSTEM_SUMMARY.md              # Replaced by ARCHITECTURE_SUMMARY
├── run_tests.py                   # Replaced by pytest structure
├── requirements.txt               # Replaced by new requirements
└── __init__.py                    # No longer needed
```

### New Files Added
```
sources/
├── Api/Domain/                    # New domain layer
├── Api/Application/services/      # Split services
├── Api/Infrastructure/            # Infrastructure components
├── Api/Api/                       # API endpoints
├── Tests/                         # Test structure
├── LandingPage/                   # Marketing site
├── docker/                        # Docker configuration
├── docker-compose.yml             # Production setup
├── docker-compose.dev.yml         # Development setup
├── Dockerfile                     # Application container
├── .dockerignore                  # Docker exclusions
├── Makefile                       # Development commands
├── DOCKER_README.md               # Infrastructure docs
├── ARCHITECTURE_SUMMARY.md        # Architecture overview
└── test_services_structure.py     # Service validation
```

## 🚀 Migration Benefits

### 1. Maintainability
- ✅ Clear separation of concerns
- ✅ Smaller, focused files
- ✅ Better code organization
- ✅ Easier to understand and modify

### 2. Testability
- ✅ Unit tests for each service
- ✅ Integration tests for layers
- ✅ Mock dependencies easily
- ✅ Better test coverage

### 3. Scalability
- ✅ Easy to add new services
- ✅ Simple to extend functionality
- ✅ Clear extension points
- ✅ Docker-based deployment

### 4. Development Experience
- ✅ Better IDE support
- ✅ Clearer imports
- ✅ Faster development cycles
- ✅ Comprehensive documentation

### 5. Production Readiness
- ✅ Docker infrastructure
- ✅ Health checks
- ✅ Monitoring setup
- ✅ Backup strategies

## 🔄 Backward Compatibility

The migration maintains backward compatibility:
- Original `services.py` still works (imports from new structure)
- All existing functionality preserved
- API endpoints remain the same
- Data processing logic unchanged

---

# Troubleshooting

## 🚨 Common Issues

### Service Won't Start
```bash
# Check logs
docker-compose logs service_name

# Check resource usage
docker stats

# Restart service
docker-compose restart service_name
```

### Connection Issues
```bash
# Check network connectivity
docker network ls
docker network inspect knowlly-network

# Test service connectivity
docker exec knowlly-api ping mongodb
```

### Port Conflicts
```bash
# Check port usage
netstat -tulpn | grep :8000

# Change ports in docker-compose.yml
ports:
  - "8001:8000"  # Use different host port
```

### Permission Issues
```bash
# Fix volume permissions
sudo chown -R 1000:1000 ./data
sudo chown -R 1000:1000 ./logs
```

### Import Errors
```bash
# Check Python path
export PYTHONPATH="${PYTHONPATH}:/path/to/sources"

# Install missing dependencies
pip install -r requirements.txt
```

### MongoDB Connection Issues
```bash
# Check MongoDB status
brew services list | grep mongodb

# Start MongoDB
brew services start mongodb/brew/mongodb-community

# Check connection
mongosh --eval "db.runCommand('ping')"
```

## 🔧 Performance Tuning

### Memory Limits
```yaml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
```

### CPU Limits
```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '1.0'
        reservations:
          cpus: '0.5'
```

## 📊 Monitoring

### Health Checks
```bash
# Application health
curl http://localhost:8000/health

# Service health
docker-compose ps
```

### Logs
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f mongodb
```

### Metrics
```bash
# Check resource usage
docker stats

# Check disk usage
df -h
```

## 🔒 Security Issues

### SSL/TLS Configuration
```nginx
# Check SSL certificate
openssl x509 -in cert.pem -text -noout

# Test SSL connection
openssl s_client -connect your-domain:443
```

### Authentication Issues
```bash
# Check JWT token
jwt decode your_token

# Test authentication endpoint
curl -H "Authorization: Bearer your_token" http://localhost:8000/protected
```

## 📞 Getting Help

### Documentation
- Check this comprehensive README
- Review API documentation at `/docs`
- Check service-specific documentation

### Logs and Debugging
- Enable debug logging: `LOG_LEVEL=DEBUG`
- Check application logs
- Check infrastructure logs

### Community Support
- Create an issue on GitHub
- Check existing issues and solutions
- Contact the development team

---

# License

This project is licensed under the MIT License - see the LICENSE file for details.

---

# Contributing

We welcome contributions! Please see our contributing guidelines for more information.

---

# Support

For support and questions:
- 📧 Email: support@knowledgeforge.com
- 📖 Documentation: [https://docs.knowledgeforge.com](https://docs.knowledgeforge.com)
- 🐛 Issues: [GitHub Issues](https://github.com/knowledgeforge/issues)
- 💬 Community: [Discord](https://discord.gg/knowledgeforge)

---

*Last updated: July 2024*
