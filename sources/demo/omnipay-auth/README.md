# OmniPay Auth

Owner: Vlas

This service handles authentication and authorization using Auth0.
It provides JWT token validation, user management, and SSO integration.

## Technology

- Node.js 20 with Express
- Auth0 for authentication
- Redis for token blacklist

## Dependencies

- express>=4.18.0
- express-oauth2-jwt-bearer>=1.6.0
- @auth0/auth0-spa-js>=2.1.0
- redis>=4.6.0

## Environment Variables

- `AUTH0_DOMAIN` - Auth0 tenant domain
- `AUTH0_CLIENT_ID` - Auth0 client ID
- `AUTH0_CLIENT_SECRET` - Auth0 client secret
- `AUTH0_AUDIENCE` - Auth0 API audience
- `REDIS_URL` - Redis connection for session storage
