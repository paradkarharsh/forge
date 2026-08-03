"""Domain exception hierarchy shared across application and presentation layers.

Application services raise these exceptions; the presentation layer maps
them onto the global error response contract through centralized handlers.
"""
from typing import Any


class ForgeError(Exception):
    """Base class for every Forge error.

    Subclasses declare the HTTP status code and stable machine-readable
    ``code``; individual instances may override ``code`` to distinguish
    scenarios that share a status but need different client handling.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        *,
        details: Any = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code is not None:
            self.code = code


class DomainError(ForgeError):
    """A domain rule was violated."""

    status_code = 422
    code = "domain_error"


class ValidationError(ForgeError):
    """Request or input data failed validation."""

    status_code = 422
    code = "validation_error"


class AuthenticationError(ForgeError):
    """The caller could not be authenticated."""

    status_code = 401
    code = "authentication_error"


class AuthorizationError(ForgeError):
    """The caller is authenticated but lacks permission."""

    status_code = 403
    code = "authorization_error"


class NotFoundError(ForgeError):
    """The requested resource does not exist."""

    status_code = 404
    code = "not_found"


class ConflictError(ForgeError):
    """The request conflicts with the current state of a resource."""

    status_code = 409
    code = "conflict"


class DatabaseError(ForgeError):
    """A persistence operation failed."""

    status_code = 500
    code = "database_error"


class ServiceUnavailableError(ForgeError):
    """A required dependency (provider, cache, …) is unavailable."""

    status_code = 503
    code = "service_unavailable"
