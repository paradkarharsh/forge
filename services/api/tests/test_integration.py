"""Integration tests against real PostgreSQL + Redis.

These exercise the full stack: app factory -> routers -> application
services -> SQLAlchemy adapters -> Postgres, with Redis available for the
OAuth state store. They are skipped automatically when the database is not
reachable (run ``docker compose up -d postgres redis`` for validation).
"""
from __future__ import annotations

import asyncio
import os

import asyncpg
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from forge_api.infrastructure.settings import get_settings

PG_HOST = os.getenv("TEST_PG_HOST", "localhost")
PG_PORT = os.getenv("TEST_PG_PORT", "5432")
PG_USER = os.getenv("POSTGRES_USER", "forge")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change-me-before-production")

TEST_DB = "forge_test"


def _admin_dsn() -> str:
    return f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/postgres"


def _test_db_url() -> str:
    return f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{TEST_DB}"


async def _database_reachable() -> bool:
    try:
        conn = await asyncpg.connect(dsn=_admin_dsn(), timeout=2)
        await conn.close()
        return True
    except asyncpg.PostgresError:
        return False


async def _admin_execute(sql: str) -> None:
    conn = await asyncpg.connect(dsn=_admin_dsn())
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


async def _create_database() -> None:
    # CREATE DATABASE cannot run inside a transaction; asyncpg executes
    # this statement directly when issued outside an explicit transaction.
    conn = await asyncpg.connect(dsn=_admin_dsn())
    try:
        await conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    finally:
        await conn.close()


async def _drop_database() -> None:
    try:
        await _admin_execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
    except asyncpg.PostgresError:
        # The maintenance DB itself may be unavailable during teardown.
        pass


@pytest.fixture(scope="session")
def forge_test_database():
    """Provision a dedicated test database and run all migrations."""
    try:
        reachable = asyncio.run(_database_reachable())
    except OSError:
        reachable = False
    if not reachable:
        pytest.skip(
            "PostgreSQL is not reachable. Start it with "
            "`docker compose up -d postgres redis` before running integration tests."
        )

    asyncio.run(_drop_database())
    asyncio.run(_create_database())

    db_url = _test_db_url()
    os.environ["FORGE_DATABASE_URL"] = db_url
    os.environ["FORGE_REDIS_URL"] = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/0")
    os.environ["FORGE_JWT_SECRET"] = "integration-test-secret-at-least-32-chars"

    get_settings.cache_clear()
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield db_url

    get_settings.cache_clear()
    asyncio.run(_drop_database())


@pytest.fixture(scope="session")
def integration_client(forge_test_database) -> TestClient:
    """A fully wired application client against the real database."""
    if forge_test_database is None:
        pytest.skip("integration database unavailable")
    os.environ["FORGE_DATABASE_URL"] = forge_test_database
    get_settings.cache_clear()

    from forge_api.presentation.http.app import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


def _register(client: TestClient, email: str, password: str = "supersecure12"):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": password},
        headers={"Host": "localhost"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    return body["data"]["access_token"]


class TestAuthFlow:
    def test_register_login_issue_token(
        self, integration_client
    ) -> None:
        client = integration_client
        token = _register(client, "alice@example.com")
        assert token

        # Login returns a token in the same envelope.
        resp = client.post(
            "/v1/auth/login",
            json={"email": "alice@example.com", "password": "supersecure12"},
            headers={"Host": "localhost"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_duplicate_register_returns_conflict(
        self, integration_client
    ) -> None:
        client = integration_client
        _register(client, "dupe@example.com")
        resp = client.post(
            "/v1/auth/register",
            json={"email": "dupe@example.com", "password": "supersecure12"},
            headers={"Host": "localhost"},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "conflict"


class TestSessionLifecycleHttp:
    def test_register_lists_session_and_logs_out(
        self, integration_client
    ) -> None:
        client = integration_client
        token = _register(client, "sess@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}

        resp = client.get("/v1/sessions", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"] is not None
        assert len(resp.json()["data"]) >= 1

        # Logout revokes the server-side session.
        resp = client.post("/v1/auth/logout", headers=headers)
        assert resp.status_code == 204

        # The access token's session should now be revoked.
        resp = client.get("/v1/sessions", headers=headers)
        assert resp.status_code == 401

    def test_refresh_rotation_end_to_end(self, integration_client) -> None:
        client = integration_client
        _register(client, "rotate@example.com")
        login = client.post(
            "/v1/auth/login",
            json={"email": "rotate@example.com", "password": "supersecure12"},
            headers={"Host": "localhost"},
        )
        assert login.status_code == 200
        old_cookie = login.cookies.get("forge_refresh")
        assert old_cookie

        # Rotate the refresh token.
        resp = client.post(
            "/v1/auth/refresh",
            cookies={"forge_refresh": old_cookie},
            headers={"Host": "localhost"},
        )
        assert resp.status_code == 200
        new_cookie = resp.cookies.get("forge_refresh")
        assert new_cookie and new_cookie != old_cookie

        # Reusing the OLD (rotated) token is detected and rejected.
        resp = client.post(
            "/v1/auth/refresh",
            cookies={"forge_refresh": old_cookie},
            headers={"Host": "localhost"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["message"] == "Refresh token rejected"