"""Request-ID middleware for correlation tracking.

Attaches a unique request_id to every HTTP request so log lines from the
same request can be correlated.

The ID is taken from the incoming X-Request-ID header (if present) or generated
as a short UUID.  It is propagated via:
  - Response header: X-Request-ID
  - contextvars (accessible anywhere within the same async context)
  - LogRecord via a logging.Filter so every log line includes request_id
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable holding the current request ID
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the request ID for the current async context (or empty string)."""
    return _request_id_var.get()


class RequestIDFilter(logging.Filter):
    """Inject request_id into every LogRecord while inside a request context."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()  # type: ignore[attr-defined]
        return True


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Starlette/FastAPI middleware that assigns a unique ID to each request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        token = _request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            _request_id_var.reset(token)
