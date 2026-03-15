# OmniPay Analytics

Owner: Iulia

This service tracks user events and provides analytics via Mixpanel.
It collects behavioral data from all OmniPay services and exposes
analytics dashboards.

## Technology

- Node.js 20 with Express
- Mixpanel for event tracking and analytics
- PostgreSQL for data warehousing

## Dependencies

- express>=4.18.0
- mixpanel>=0.17.0
- pg>=8.11.0

## Environment Variables

- `MIXPANEL_TOKEN` - Mixpanel project token
- `MIXPANEL_PROJECT_TOKEN` - Mixpanel project token (alias)
- `DATABASE_URL` - PostgreSQL connection string
- `MIXPANEL_API_SECRET` - Mixpanel API secret for exports
