# OmniPay Payment Processor

Owner: Vlad

This service handles payment processing using Stripe as the primary payment provider.
It processes credit card transactions, manages payment intents, and handles webhooks.

## Technology

- Python 3.11 with Flask
- Stripe SDK for payment processing
- Redis for session management

## Dependencies

- stripe>=7.0.0
- redis>=5.0.0
- python-dotenv>=1.0.0

## Environment Variables

- `STRIPE_API_KEY` - Stripe secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing secret
- `REDIS_URL` - Redis connection URL
- `STRIPE_PUBLISHABLE_KEY` - Stripe public key (client-side)
