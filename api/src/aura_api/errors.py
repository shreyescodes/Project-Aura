"""Domain errors, and rendering of every error response as RFC 9457 problem details."""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_CONTENT_TYPE = "application/problem+json"

logger = logging.getLogger(__name__)


class AuraError(Exception):
    """Base class for errors that map to a specific HTTP response."""

    status: HTTPStatus = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class TenantNotFoundError(AuraError):
    status = HTTPStatus.NOT_FOUND

    def __init__(self, name: str) -> None:
        super().__init__(f"Tenant '{name}' does not exist.")


class TenantAlreadyExistsError(AuraError):
    status = HTTPStatus.CONFLICT

    def __init__(self, name: str) -> None:
        super().__init__(f"A project named '{name}' already exists.")


class TenantNotEmptyError(AuraError):
    status = HTTPStatus.CONFLICT

    def __init__(self, name: str, servers: int, volumes: int) -> None:
        super().__init__(
            f"Tenant '{name}' still owns {servers} server(s) and {volumes} volume(s); "
            "delete them before offboarding."
        )


class UnknownUsersError(AuraError):
    status = HTTPStatus.UNPROCESSABLE_ENTITY

    def __init__(self, names: list[str]) -> None:
        super().__init__(f"Unknown user(s): {', '.join(sorted(names))}.")


class CloudError(AuraError):
    """The OpenStack API failed or was unreachable."""

    status = HTTPStatus.BAD_GATEWAY


class ProvisioningError(CloudError):
    """Onboarding failed part-way; completed steps were rolled back."""


def problem_response(
    status: int, detail: str, headers: Mapping[str, str] | None = None, **extra: Any
) -> JSONResponse:
    http_status = HTTPStatus(status)
    return JSONResponse(
        status_code=http_status.value,
        media_type=PROBLEM_CONTENT_TYPE,
        headers=headers,
        content={
            "type": "about:blank",
            "title": http_status.phrase,
            "status": http_status.value,
            "detail": detail,
            **extra,
        },
    )


async def _aura_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AuraError)  # noqa: S101 - guaranteed by registration
    return problem_response(exc.status, exc.detail)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    return problem_response(exc.status_code, exc.detail, headers=exc.headers)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    # Location and message only: echoing the rejected input could leak secrets.
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return problem_response(422, "Request validation failed.", errors=errors)


async def _unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error", exc_info=exc)
    return problem_response(500, "An unexpected error occurred.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuraError, _aura_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled_error)
