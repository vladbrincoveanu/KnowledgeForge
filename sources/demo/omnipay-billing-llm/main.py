"""Billing service with complex financial workflows."""

import os
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = FastAPI(title="OmniPay Billing Service")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./billing.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, index=True)
    amount = Column(Numeric(10, 2))
    currency = Column(String)
    status = Column(String)
    due_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, index=True)
    plan_id = Column(String)
    status = Column(String)
    billing_cycle = Column(String)
    next_billing_date = Column(DateTime)


Base.metadata.create_all(bind=engine)


class InvoiceCreate(BaseModel):
    customer_id: str
    amount: float
    currency: str


class SubscriptionCreate(BaseModel):
    customer_id: str
    plan_id: str
    billing_cycle: str


@app.get("/health")
def health():
    return {"status": "healthy", "service": "billing-llm"}


@app.post("/api/v1/invoices")
def create_invoice(invoice: InvoiceCreate):
    """Create a new invoice."""
    db = SessionLocal()
    try:
        due_date = datetime.utcnow() + timedelta(days=30)
        db_invoice = Invoice(
            customer_id=invoice.customer_id,
            amount=invoice.amount,
            currency=invoice.currency,
            status="pending",
            due_date=due_date,
        )
        db.add(db_invoice)
        db.commit()
        db.refresh(db_invoice)
        return {
            "id": db_invoice.id,
            "status": db_invoice.status,
            "due_date": db_invoice.due_date.isoformat(),
        }
    finally:
        db.close()


@app.get("/api/v1/invoices/{invoice_id}")
def get_invoice(invoice_id: int):
    """Get invoice details."""
    db = SessionLocal()
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {
            "id": invoice.id,
            "customer_id": invoice.customer_id,
            "amount": float(invoice.amount),
            "currency": invoice.currency,
            "status": invoice.status,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        }
    finally:
        db.close()


@app.post("/api/v1/subscriptions")
def create_subscription(subscription: SubscriptionCreate):
    """Create a new subscription."""
    db = SessionLocal()
    try:
        billing_cycle_days = {"monthly": 30, "yearly": 365}
        days = billing_cycle_days.get(subscription.billing_cycle, 30)

        db_subscription = Subscription(
            customer_id=subscription.customer_id,
            plan_id=subscription.plan_id,
            status="active",
            billing_cycle=subscription.billing_cycle,
            next_billing_date=datetime.utcnow() + timedelta(days=days),
        )
        db.add(db_subscription)
        db.commit()
        db.refresh(db_subscription)
        return {
            "id": db_subscription.id,
            "status": db_subscription.status,
            "next_billing_date": db_subscription.next_billing_date.isoformat(),
        }
    finally:
        db.close()


@app.post("/api/v1/refunds")
def process_refund(invoice_id: int, amount: Optional[float] = None):
    """Process a refund for an invoice."""
    db = SessionLocal()
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        refund_amount = amount or float(invoice.amount)
        invoice.status = "refunded"
        db.commit()

        return {
            "invoice_id": invoice_id,
            "refund_amount": refund_amount,
            "status": "processed",
        }
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
