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


# ─── LLM-specific errors ─────────────────────────────────────────────


class ProviderUnavailableError(ForgeError):
    """The LLM provider is not reachable."""

    status_code = 503
    code = "provider_unavailable"


class LLMAuthError(ForgeError):
    """Provider rejected the API key / credentials."""

    status_code = 401
    code = "llm_auth_failed"


class ProviderRateLimitedError(ForgeError):
    """The LLM provider returned a rate-limit response."""

    status_code = 429
    code = "provider_rate_limited"


class LLMTimeoutError(ForgeError):
    """The LLM call timed out."""

    status_code = 504
    code = "llm_timeout"


class ContextTooLargeError(ForgeError):
    """The assembled context exceeds the model's context window."""

    status_code = 422
    code = "context_too_large"


class ModelUnavailableError(ForgeError):
    """The requested model is not registered or not enabled."""

    status_code = 404
    code = "model_unavailable"


class ProviderError(ForgeError):
    """An unclassified error from the LLM provider."""

    status_code = 502
    code = "provider_error"


class CancelledError(ForgeError):
    """The operation was cancelled (client disconnect, etc.)."""

    status_code = 499
    code = "cancelled"
