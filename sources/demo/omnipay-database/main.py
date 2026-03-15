"""Database service providing PostgreSQL and Redis access."""

import os
from typing import Optional
from fastapi import FastAPI, HTTPException
import redis
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel

app = FastAPI(title="OmniPay Database Service")

# Redis connection
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('POSTGRES_USER', 'omnipay')}:{os.getenv('POSTGRES_PASSWORD', 'password')}"
    f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'omnipay')}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    amount = Column(Integer)
    currency = Column(String)
    status = Column(String)
    created_at = Column(DateTime)


Base.metadata.create_all(bind=engine)


class TransactionCreate(BaseModel):
    user_id: str
    amount: int
    currency: str


@app.get("/health")
def health():
    """Health check."""
    # Check Redis
    try:
        redis_client.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    return {
        "status": "healthy",
        "service": "database",
        "redis": redis_status,
    }


@app.post("/api/v1/cache/set")
def cache_set(key: str, value: str, ttl: Optional[int] = 3600):
    """Set a value in Redis cache."""
    redis_client.setex(key, ttl, value)
    return {"success": True, "key": key}


@app.get("/api/v1/cache/get")
def cache_get(key: str):
    """Get a value from Redis cache."""
    value = redis_client.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"key": key, "value": value}


@app.post("/api/v1/transactions")
def create_transaction(transaction: TransactionCreate):
    """Create a new transaction."""
    db = SessionLocal()
    try:
        db_transaction = Transaction(
            user_id=transaction.user_id,
            amount=transaction.amount,
            currency=transaction.currency,
            status="pending",
        )
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        return {
            "id": db_transaction.id,
            "status": db_transaction.status,
        }
    finally:
        db.close()


@app.get("/api/v1/transactions/{transaction_id}")
def get_transaction(transaction_id: int):
    """Get a transaction by ID."""
    db = SessionLocal()
    try:
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return {
            "id": transaction.id,
            "user_id": transaction.user_id,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status,
        }
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
