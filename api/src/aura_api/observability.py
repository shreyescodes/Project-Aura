"""Structured logging, request IDs and Prometheus metrics."""

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram

REQUEST_ID_HEADER = "X-Request-ID"

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

REQUESTS = Counter(
    "aura_api_requests_total",
    "HTTP requests handled, by route template and status code.",
    ["method", "route", "status"],
)
LATENCY = Histogram(
    "aura_api_request_duration_seconds",
    "HTTP request latency, by route template.",
    ["method", "route"],
    # Onboarding makes a dozen OpenStack calls, so the tail runs to seconds.
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

# Attributes every LogRecord has; anything else came from `extra=` and is logged.
_RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if request_id := request_id_var.get():
            payload["request_id"] = request_id
        payload.update({k: v for k, v in vars(record).items() if k not in _RESERVED})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # The middleware below writes the access log, with route and request ID.
    logging.getLogger("uvicorn.access").disabled = True


def install_request_middleware(app: FastAPI) -> None:
    access_log = logging.getLogger("aura_api.access")

    @app.middleware("http")
    async def observe_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            elapsed = time.perf_counter() - start
            # Label by route template ("/v1/tenants/{name}"), not the raw path,
            # to keep metric cardinality bounded.
            route = getattr(request.scope.get("route"), "path", "unmatched")
            REQUESTS.labels(request.method, route, str(status_code)).inc()
            LATENCY.labels(request.method, route).observe(elapsed)
            access_log.info(
                "request",
                extra={
                    "method": request.method,
                    "route": route,
                    "status": status_code,
                    "duration_ms": round(elapsed * 1000, 1),
                },
            )
            request_id_var.reset(token)
