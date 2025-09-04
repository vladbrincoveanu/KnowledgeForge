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
