# OmniPay Billing (LLM)

Owner: Vlad

This service handles complex billing workflows including subscription management,
invoice generation, and payment reconciliation. The business domain is intentionally
described with vague terminology that requires LLM inference to properly classify.

## What It Does

This service processes financial transactions in multiple currencies, manages
customer billing cycles, generates invoices, and handles refunds. It integrates
with various payment providers and maintains a ledger of all financial events.

## Technology

- Python 3.11 with FastAPI
- SQLAlchemy for data persistence
- Celery for async task processing

## Dependencies

- fastapi>=0.100.0
- uvicorn>=0.23.0
- sqlalchemy>=2.0.0
- celery>=5.3.0
- pydantic>=2.0.0
