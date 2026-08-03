"""Centralized exception handlers for the global error contract.

Handlers translate domain errors, validation failures, HTTP exceptions, and
persistence failures into the shared ``ErrorResponse`` envelope so every
endpoint reports failures consistently.
"""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from forge_api.domain.errors import ForgeError
from forge_api.presentation.http.contracts import ErrorDetail, ErrorPayload

logger = logging.getLogger(__name__)

_HTTP_CODES = {
    400: "bad_request",
    401: "authentication_error",
    403: "authorization_error",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limit_exceeded",
    503: "service_unavailable",
}


def _body(payload: ErrorPayload) -> dict:
    return {"success": False, "error": jsonable_encoder(payload)}


def _http_code(status_code: int) -> str:
    return _HTTP_CODES.get(status_code, "http_error")


def _validation_details(errors: list[dict]) -> list[ErrorDetail]:
    return [
        ErrorDetail(
            field=".".join(str(part) for part in error.get("loc", ())[1:]),
            message=error.get("msg", "invalid value"),
        )
        for error in errors
    ]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ForgeError)
    async def forge_error_handler(request: Request, exc: ForgeError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(ErrorPayload(code=exc.code, message=exc.message, details=exc.details)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_body(
                ErrorPayload(
                    code="validation_error",
                    message="Request validation failed",
                    details=_validation_details(exc.errors()),
                )
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        message = detail if isinstance(detail, str) else str(detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(
                ErrorPayload(
                    code=_http_code(exc.status_code),
                    message=message,
                    details=detail if isinstance(detail, dict) else None,
                )
            ),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Integrity constraint violation: %s", exc.orig)
        return JSONResponse(
            status_code=409,
            content=_body(ErrorPayload(code="conflict", message="Resource conflict")),
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("Database error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_body(
                ErrorPayload(code="database_error", message="Database operation failed")
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_body(
                ErrorPayload(code="internal_error", message="An unexpected error occurred")
            ),
        )
