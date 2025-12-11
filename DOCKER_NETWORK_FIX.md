# Docker Network Communication Fix

## Issue

The `VITE_API_URL` and `VITE_APP_API_URL` environment variables were set to empty strings in `docker-compose.yml`, which broke UI-API communication within the Docker network.

## Problem

When running in Docker Compose:
- UI container needs to communicate with API container
- Empty `VITE_API_URL` causes fallback to `http://localhost:8000`
- `localhost` inside the UI container refers to the UI container itself, not the API container
- This breaks all API calls from the UI

## Solution

Set the environment variables to use the Docker Compose service hostname:

```yaml
environment:
  - VITE_API_URL=http://api:8000
  - VITE_APP_API_URL=http://api:8000
```

## How Docker Compose Networking Works

In Docker Compose:
- Services can communicate using their service names as hostnames
- `api` is the service name, so `http://api:8000` resolves to the API container
- This works within the `knowledgeforge-network` bridge network

## Vite Proxy Configuration

The `vite.config.ts` also has a proxy configured:
```typescript
proxy: {
  '/api': {
    target: 'http://api:8000',  // ✅ Correct for Docker network
    changeOrigin: true,
  }
}
```

This proxy works during development (Vite dev server), but the environment variable is still needed for:
1. Direct API calls that don't go through the proxy
2. Built/production mode where proxy doesn't apply
3. Fallback when proxy configuration isn't available

## Verification

After the fix:
- UI container can communicate with API container
- API calls work correctly
- Both dev mode (with proxy) and production mode work

## Files Changed

- `docker-compose.yml`: Lines 126-127
  - Changed from empty strings to `http://api:8000`

