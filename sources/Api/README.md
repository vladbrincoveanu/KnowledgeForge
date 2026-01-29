# KnowledgeForge API

A clean, well-structured FastAPI application for semantic ontology extraction from CSV files.

## Architecture Overview

```
api/
├── app/                    # Main application package
│   ├── __init__.py
│   ├── main.py            # FastAPI app initialization
│   ├── api/               # API routes and endpoints
│   │   ├── __init__.py
│   │   ├── v1/            # API version 1
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/ # Route handlers
│   │   │   └── dependencies.py
│   ├── core/              # Core application logic
│   │   ├── __init__.py
│   │   ├── config.py      # Configuration management
│   │   ├── security.py    # Authentication & authorization
│   │   └── exceptions.py  # Custom exceptions
│   ├── domain/            # Business logic and models
│   │   ├── __init__.py
│   │   ├── models/        # Pydantic models
│   │   ├── services/      # Business logic services
│   │   └── repositories/  # Data access interfaces
│   ├── infrastructure/    # External integrations
│   │   ├── __init__.py
│   │   ├── database/      # Database connections
│   │   ├── llm/           # LLM integrations
│   │   ├── graph/         # Graph database operations
│   │   └── storage/       # File storage
│   └── shared/            # Shared utilities
│       ├── __init__.py
│       ├── utils.py
│       └── constants.py
├── tests/                 # Test suite
├── alembic/               # Database migrations
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

## Key Principles

1. **Separation of Concerns**: Clear boundaries between layers
2. **Dependency Injection**: Services are injected, not imported directly
3. **Clean Architecture**: Domain logic is independent of infrastructure
4. **API Versioning**: Structured for future API versions
5. **Configuration Management**: Centralized configuration handling
6. **Error Handling**: Consistent error responses across the API

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Set up environment variables (see `.env.example`)
3. Run the application: `uvicorn app.main:app --reload`

## API Documentation

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI Schema: `/openapi.json`

---

## Implementation Log

### 2024-12-XX: Service Extraction Layer Implementation

**Overview**: Implemented a comprehensive service extraction layer that extracts services from GitHub repositories or ZIP files, creating a service graph where each service is a node and connections between services are edges.

**Focus**: Services are nodes in the graph. We extract **5 primary fields** for each service:

| # | Field | Description | Example Values |
|---|-------|-------------|----------------|
| 1 | **domain** | Business area this service belongs to | Revenue Core, Checkout, Identity |
| 2 | **owner** | Squad/team that owns the service | Growth Squad, Platform Team |
| 3 | **status** | Lifecycle stage | Active-Dev, Maintenance-Only, Deprecated |
| 4 | **tier** | Criticality (how bad if it breaks?) | Tier 1 (site-wide), Tier 2 (journey), Tier 3 (minor) |
| 5 | **data_class** | What sensitive data lives here | PII, Credit-Card, Public, Internal |

#### Components Created:

1. **Domain Models** (`app/domain/models/services.py`):
   - `Service`: Represents a service with the 5 primary extraction fields
   - `ServiceConnection`: Represents connections between services
   - `ServiceGraph`: Complete service graph with services and connections
   - Enums: `ServiceStatus`, `ServiceTier`, `ConnectionType`

2. **Service Extractor** (`app/services/service_extraction/service_extractor.py`):
   - Extracts services from multiple sources:
     - Docker Compose files (labels, environment variables)
     - Kubernetes manifests (annotations, labels)
     - API route files (FastAPI, Express, Flask patterns)
     - Service configuration files (YAML/JSON)
     - Microservice directory patterns
   - **Extracts all 5 fields** from various locations in the codebase
   - **Git History Analysis**: Automatically infers `status` from git commit history:
     - Active-Dev: Recent commits (<30 days), frequent activity
     - Maintenance-Only: Old commits (30-180 days), only bugfixes
     - Deprecated: Very old commits (>180 days) or deprecation keywords in commits

3. **Git Status Analyzer** (`app/services/service_extraction/git_status_analyzer.py`):
   - Analyzes git commit history to infer service lifecycle status
   - Checks commit frequency, recency, and deprecation keywords
   - Enhances status field when not found in config files
   - Overrides config-based status if git history suggests different status

4. **Git Contributor Analyzer** (`app/services/service_extraction/git_contributor_analyzer.py`):
   - Extracts top contributors per service path (email + commit counts)
   - Builds owner candidate lists and unique contributor counts

5. **Service Relationship Discoverer** (`app/services/service_extraction/service_relationship_discoverer.py`):
   - Discovers connections between services from:
     - Docker Compose `depends_on` relationships
     - HTTP client calls in code (fetch, axios, requests, etc.)
     - API client configurations
     - Message queue configurations (RabbitMQ, Kafka, etc.)
     - Database connection configs
     - Service discovery configs (Consul, Eureka)
   - Creates `ServiceConnection` objects with connection types, protocols, endpoints

6. **GitHub Downloader** (`app/services/service_extraction/github_downloader.py`):
   - Downloads repositories from GitHub URLs
   - Supports git clone (preferred) or ZIP download fallback
   - Handles branch/tag specifications
   - Extracts and prepares repository for analysis

7. **API Endpoints** (`app/endpoint/v1/routes/service_extraction.py`):
   - `POST /api/v1/services/extract-from-github`: Extract from GitHub URL
   - `POST /api/v1/services/extract-from-zip`: Extract from uploaded ZIP file
   - `POST /api/v1/services/extract-from-path`: Extract from local path
   - `GET /api/v1/services/extraction/{task_id}`: Get extraction status
   - `GET /api/v1/services/extraction/{task_id}/results`: Get extraction results
   - `DELETE /api/v1/services/extraction/{task_id}`: Delete extraction task
   - All endpoints support background processing with WebSocket updates
   - Results stored in Neo4j graph database

#### Features:

- **Multi-source extraction**: Identifies services from Docker Compose, Kubernetes, API routes, configs, and directory patterns
- **Relationship discovery**: Automatically finds connections between services through code analysis
- **GitHub integration**: Direct support for GitHub repository URLs
- **ZIP file support**: Upload and extract from ZIP archives
- **Graph storage**: Services and connections stored in Neo4j for visualization
- **Background processing**: Asynchronous extraction with progress tracking
- **Error handling**: Comprehensive error and warning collection

#### Usage Example:

```bash
# Extract from GitHub
curl -X POST "http://localhost:8000/api/v1/services/extract-from-github" \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/user/repo"}'

# Check status
curl "http://localhost:8000/api/v1/services/extraction/{task_id}"

# Get results
curl "http://localhost:8000/api/v1/services/extraction/{task_id}/results"
```

#### Files Modified:

- `app.py`: Added service_extraction router registration
- `app/domain/models/services.py`: New domain models
- `app/services/service_extraction/`: New service extraction module
- `app/endpoint/v1/routes/service_extraction.py`: New API endpoints

#### Recent Updates:

- **Git History Analysis** (2024-12-XX): Added automatic status inference from git commit history
  - Analyzes commit frequency, recency, and deprecation keywords
  - Enhances status field when not found in config files
  - Overrides config-based status if git history suggests different
  - Captures top contributors per service for owner candidate lists

#### Recent Updates:

- **JSON File Storage** (2024-12-XX): Added feature flag for JSON file output
  - Set `KF_STORE_TO_JSON=true` (default) to save results to JSON files
  - Set `KF_STORE_TO_NEO4J=true` to also store in Neo4j
  - Output location: `data/extractions/{task_id}/`
  - Files: `metadata.json`, `services.json`, `connections.json`, `summary.json`
  - Easy for Cursor/AI to read and debug extraction results

- **Top-Level Directory Extraction**: Now extracts services from root directories
  - Detects Python packages, Django apps, Node.js modules
  - Analyzes git history per directory for status inference

#### Feature Flags (Environment Variables):

| Variable | Default | Description |
|----------|---------|-------------|
| `KF_STORE_TO_JSON` | `true` | Store results to JSON files in `data/extractions/` |
| `KF_STORE_TO_NEO4J` | `false` | Store results to Neo4j graph database |
| `KF_JSON_OUTPUT_DIR` | `data/extractions` | Directory for JSON output |

#### JSON Output Structure:

```
data/extractions/
└── {task_id}/
    ├── metadata.json      # Task metadata, timestamps, status
    ├── services.json      # All services with the 5 primary fields
    ├── connections.json   # Service connections/relationships
    └── summary.json       # Human-readable summary
```

#### Next Steps (Future Enhancements):

- Add more service discovery patterns
- Support for gRPC service detection
- Enhanced relationship strength scoring
- Service dependency visualization
- Service health monitoring integration
