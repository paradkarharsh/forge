"""Global HTTP response contracts.

Every endpoint responds with one of these two envelopes. Success responses
carry ``data`` plus optional ``meta`` (for example pagination); failures
carry a stable machine-readable ``error.code`` so clients can branch
programmatically instead of parsing messages.
"""
from typing import Any, Literal

from pydantic import BaseModel, Field


class SuccessResponse[T](BaseModel):
    success: Literal[True] = True
    data: T | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ErrorPayload


def ok[T](
    data: T | None = None, *, meta: dict[str, Any] | None = None
) -> SuccessResponse[T]:
    """Build a success envelope for a payload."""
    return SuccessResponse(data=data, meta=meta or {})


def fail(
    code: str,
    message: str,
    *,
    details: list[ErrorDetail] | dict[str, Any] | None = None,
) -> ErrorResponse:
    """Build an error envelope."""
    return ErrorResponse(error=ErrorPayload(code=code, message=message, details=details))
