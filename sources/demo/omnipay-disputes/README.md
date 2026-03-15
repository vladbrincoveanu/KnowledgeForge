# OmniPay Disputes

This service handles chargeback and dispute management for OmniPay.
It processes refund requests, communicates with payment providers,
and manages the dispute lifecycle.

## Technology

- Node.js 20 with Express
- PostgreSQL for dispute records
- Redis for caching

## Dependencies

- express>=4.18.0
- pg>=8.11.0
- redis>=4.6.0
