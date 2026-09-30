from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # A request must start with a clean context so values from a previous
        # request can never appear in the next request's logs.
        clear_contextvars()

        # Preserve a caller-supplied ID when present; otherwise create the
        # lab's stable, non-PII request ID format.
        correlation_id = request.headers.get("x-request-id", "").strip()
        if not correlation_id:
            correlation_id = f"req-{uuid.uuid4().hex[:8]}"

        bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            response.headers["x-request-id"] = correlation_id
            response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"
            return response
        finally:
            # BaseHTTPMiddleware can reuse execution context between requests.
            # Clear it even when the handler raises an exception.
            clear_contextvars()
