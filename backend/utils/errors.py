"""
Typed exception hierarchy for Ethic Companion.

Raise a typed exception in any route or service; the FastAPI handler
(registered via register_error_handlers) maps it to the correct HTTP status
with a clean JSON body — no stack traces leak to clients.

Usage:
    from utils.errors import IntegrationError
    raise IntegrationError("Composio returned 503")
    # FastAPI returns: HTTP 502 {"error": "integration_error", "detail": "Composio returned 503"}
"""

from __future__ import annotations

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class EthicCompanionError(Exception):
    """Base class for all typed application errors."""

    http_status: int = 500
    error_code: str = "internal_error"

    def __init__(self, detail: str = "An unexpected error occurred."):
        super().__init__(detail)
        self.detail = detail


class IntegrationError(EthicCompanionError):
    """External service (Composio, GitHub, etc.) returned an error."""

    http_status = 502
    error_code = "integration_error"


class DBError(EthicCompanionError):
    """Database query or connection failure."""

    http_status = 503
    error_code = "db_error"


class AuthError(EthicCompanionError):
    """Authentication or authorisation failure."""

    http_status = 401
    error_code = "auth_error"


class ESLError(EthicCompanionError):
    """ESL vetoed the requested action."""

    http_status = 403
    error_code = "esl_error"


class ValidationError(EthicCompanionError):
    """Business-rule validation failure (beyond Pydantic)."""

    http_status = 422
    error_code = "validation_error"


def register_error_handlers(app: FastAPI) -> None:
    """Register typed exception handlers on a FastAPI app instance."""

    @app.exception_handler(EthicCompanionError)
    async def handle_ethic_companion_error(
        request: Request, exc: EthicCompanionError
    ) -> JSONResponse:
        log_fn = logger.error if exc.http_status >= 500 else logger.warning
        log_fn(
            f"{exc.__class__.__name__} on {request.method} {request.url.path}: {exc.detail}"
        )
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.error_code, "detail": exc.detail},
        )
