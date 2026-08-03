"""Response contract tests.

Verifies that the global error handlers produce the documented envelope
for every error class and that success responses wrap data correctly.
"""
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from forge_api.domain.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DatabaseError,
    DomainError,
    ForgeError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from forge_api.presentation.http.contracts import ErrorDetail, fail, ok
from forge_api.presentation.http.errors import register_exception_handlers


def _make_app(exception: Exception) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test")
    async def test_route():
        raise exception

    return TestClient(app, raise_server_exceptions=False)


class TestSuccessResponse:
    def test_ok_wraps_data_with_success_flag(self) -> None:
        result = ok({"id": "abc"})
        assert result.success is True
        assert result.data == {"id": "abc"}
        assert result.meta == {}

    def test_ok_with_meta(self) -> None:
        result = ok([1, 2], meta={"total": 2})
        assert result.meta == {"total": 2}

    def test_ok_with_none_data(self) -> None:
        result = ok()
        assert result.success is True
        assert result.data is None


class TestErrorResponse:
    def test_fail_builds_error_envelope(self) -> None:
        result = fail("not_found", "Thing not found")
        assert result.success is False
        assert result.error.code == "not_found"
        assert result.error.message == "Thing not found"

    def test_fail_with_details(self) -> None:
        result = fail(
            "validation_error",
            "Bad input",
            details=[ErrorDetail(field="email", message="required")],
        )
        assert len(result.error.details) == 1
        assert result.error.details[0].field == "email"


class TestExceptionHandlers:
    def test_authentication_error(self) -> None:
        client = _make_app(AuthenticationError("bad token"))
        resp = client.get("/test")
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "authentication_error"

    def test_authorization_error(self) -> None:
        client = _make_app(AuthorizationError("denied"))
        resp = client.get("/test")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "authorization_error"

    def test_not_found_error(self) -> None:
        client = _make_app(NotFoundError("gone"))
        resp = client.get("/test")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    def test_conflict_error(self) -> None:
        client = _make_app(ConflictError("dupe"))
        resp = client.get("/test")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "conflict"

    def test_domain_error(self) -> None:
        client = _make_app(DomainError("rule broken"))
        resp = client.get("/test")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "domain_error"

    def test_validation_error(self) -> None:
        client = _make_app(ValidationError("bad data"))
        resp = client.get("/test")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    def test_database_error(self) -> None:
        client = _make_app(DatabaseError("pg down"))
        resp = client.get("/test")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "database_error"

    def test_service_unavailable(self) -> None:
        client = _make_app(ServiceUnavailableError("redis gone"))
        resp = client.get("/test")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "service_unavailable"

    def test_http_exception_uses_contract(self) -> None:
        client = _make_app(HTTPException(429, "slow down"))
        resp = client.get("/test")
        assert resp.status_code == 429
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "rate_limit_exceeded"

    def test_forge_error_with_custom_code(self) -> None:
        client = _make_app(ForgeError("custom", code="my_custom_code"))
        resp = client.get("/test")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "my_custom_code"

    def test_pydantic_validation_uses_contract(self) -> None:
        """FastAPI request validation errors use the global envelope."""
        app = FastAPI()
        register_exception_handlers(app)
        from pydantic import BaseModel

        class Body(BaseModel):
            email: str
            count: int

        @app.post("/test")
        async def test_route(body: Body):
            return body

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/test", json={"email": 123})
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "validation_error"
        assert isinstance(body["error"]["details"], list)

    def test_unhandled_exception_returns_internal_error(self) -> None:
        client = _make_app(RuntimeError("boom"))
        resp = client.get("/test")
        assert resp.status_code == 500
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "internal_error"
