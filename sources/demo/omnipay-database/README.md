# OmniPay Database

Owner: Iulia

This service provides database management and connection pooling for OmniPay.
It exposes PostgreSQL as the primary data store and Redis for caching.

## Technology

- Python 3.11 with FastAPI
- PostgreSQL via psycopg2
- Redis for caching via redis-py
- SQLAlchemy ORM

## Dependencies

- fastapi>=0.100.0
- uvicorn>=0.23.0
- psycopg2-binary>=2.9.0
- sqlalchemy>=2.0.0
- redis>=5.0.0

## Environment Variables

- `POSTGRES_HOST` - PostgreSQL host
- `POSTGRES_PORT` - PostgreSQL port
- `POSTGRES_DB` - Database name
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password
- `REDIS_HOST` - Redis host
- `REDIS_PORT` - Redis port
- `DATABASE_URL` - Full database URL (alternative)
