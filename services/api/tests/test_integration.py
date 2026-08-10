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
from fastapi.testclient import TestClient

# Reset the shared in-memory rate limiter before every test in this module.
pytestmark = pytest.mark.usefixtures("_reset_rate_limiter")

PG_HOST = os.getenv("TEST_PG_HOST", "localhost")
PG_PORT = os.getenv("TEST_PG_PORT", "5432")
PG_USER = os.getenv("POSTGRES_USER", "forge")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change-me-before-production")

TEST_DB = "forge_test"


def _test_db_url() -> str:
    return f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{TEST_DB}"


async def _user_id_by_email(email: str) -> str:
    """Resolve a user id from the integration database by email."""
    conn = await asyncpg.connect(dsn=_test_db_url().replace("+asyncpg", ""))
    try:
        row = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email.lower())
        assert row is not None, f"user {email} not found"
        return str(row["id"])
    finally:
        await conn.close()


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
        assert resp.json()["error"]["code"] == "email_taken"


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


class TestWorkspaceTenancyHttp:
    """End-to-end workspace CRUD with membership management."""

    def test_create_and_get_workspace(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "ws-create@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}

        # Create workspace
        resp = client.post(
            "/v1/workspaces",
            json={"name": "Test Workspace", "slug": "test-ws", "description": "My desc"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Test Workspace"
        assert data["slug"] == "test-ws"
        assert data["description"] == "My desc"
        assert data["role"] == "owner"
        ws_id = data["id"]

        # Get by ID
        resp = client.get(f"/v1/workspaces/{ws_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["slug"] == "test-ws"

        # Get by slug
        resp = client.get("/v1/workspaces/by-slug/test-ws", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == ws_id

    def test_list_workspaces(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "ws-list@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}

        client.post(
            "/v1/workspaces",
            json={"name": "WS A", "slug": "ws-list-a"},
            headers=headers,
        )
        client.post(
            "/v1/workspaces",
            json={"name": "WS B", "slug": "ws-list-b"},
            headers=headers,
        )

        resp = client.get("/v1/workspaces", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 2

    def test_update_workspace(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "ws-update@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}

        create = client.post(
            "/v1/workspaces",
            json={"name": "Before", "slug": "ws-update-test"},
            headers=headers,
        )
        ws_id = create.json()["data"]["id"]

        resp = client.patch(
            f"/v1/workspaces/{ws_id}",
            json={"name": "After", "description": "Updated"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "After"
        assert resp.json()["data"]["description"] == "Updated"

    def test_delete_workspace(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "ws-delete@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}

        create = client.post(
            "/v1/workspaces",
            json={"name": "To Delete", "slug": "ws-delete-test"},
            headers=headers,
        )
        ws_id = create.json()["data"]["id"]

        resp = client.delete(f"/v1/workspaces/{ws_id}", headers=headers)
        assert resp.status_code == 204

        # Should be gone
        resp = client.get(f"/v1/workspaces/{ws_id}", headers=headers)
        assert resp.status_code == 404

    def test_duplicate_slug_returns_conflict(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "ws-slug-dupe@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}

        client.post(
            "/v1/workspaces",
            json={"name": "First", "slug": "unique-slug-test"},
            headers=headers,
        )
        resp = client.post(
            "/v1/workspaces",
            json={"name": "Second", "slug": "unique-slug-test"},
            headers=headers,
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "slug_taken"

    def test_membership_crud(self, integration_client) -> None:
        client = integration_client
        owner_token = _register(client, "ws-owner-mem@example.com")
        member_token = _register(client, "ws-member-mem@example.com")
        owner_headers = {"Host": "localhost", "Authorization": f"Bearer {owner_token}"}
        member_headers = {"Host": "localhost", "Authorization": f"Bearer {member_token}"}

        # Create workspace as owner.
        create = client.post(
            "/v1/workspaces",
            json={"name": "Members Test", "slug": "members-test"},
            headers=owner_headers,
        )
        assert create.status_code == 201
        ws_id = create.json()["data"]["id"]

        # Member cannot see the workspace yet.
        resp = client.get("/v1/workspaces", headers=member_headers)
        assert all(w["id"] != ws_id for w in resp.json()["data"])

        # Resolve the member's user id from the database.
        member_id = asyncio.run(_user_id_by_email("ws-member-mem@example.com"))

        # Owner adds the member.
        resp = client.post(
            f"/v1/workspaces/{ws_id}/members",
            json={"user_id": member_id, "role": "member"},
            headers=owner_headers,
        )
        assert resp.status_code == 201

        # Owner now sees two members.
        resp = client.get(f"/v1/workspaces/{ws_id}/members", headers=owner_headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

        # Member can now see the workspace.
        resp = client.get("/v1/workspaces", headers=member_headers)
        assert any(w["id"] == ws_id for w in resp.json()["data"])

        # Owner changes the member's role to admin.
        resp = client.patch(
            f"/v1/workspaces/{ws_id}/members/{member_id}",
            json={"role": "admin"},
            headers=owner_headers,
        )
        assert resp.status_code == 200

        # Owner removes the member.
        resp = client.delete(
            f"/v1/workspaces/{ws_id}/members/{member_id}", headers=owner_headers
        )
        assert resp.status_code == 204

        # Only the owner remains.
        resp = client.get(f"/v1/workspaces/{ws_id}/members", headers=owner_headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        # Member can no longer see the workspace.
        resp = client.get("/v1/workspaces", headers=member_headers)
        assert all(w["id"] != ws_id for w in resp.json()["data"])


def _create_workspace(client, headers, slug: str) -> str:
    resp = client.post(
        "/v1/workspaces",
        json={"name": "Repo WS", "slug": slug},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


class TestRepositoryTenancyHttp:
    """End-to-end repository CRUD, import, archive, and restore."""

    def test_repository_crud_lifecycle(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "repo-crud@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}
        ws_id = _create_workspace(client, headers, "repo-crud-ws")

        # Create
        resp = client.post(
            "/v1/repositories",
            json={
                "workspace_id": ws_id,
                "name": "widget",
                "owner": "alice",
                "provider": "github",
                "remote_url": "https://github.com/alice/widget",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["name"] == "widget"
        assert data["provider"] == "github"
        assert data["clone_status"] == "pending"
        repo_id = data["id"]

        # List
        resp = client.get(f"/v1/repositories?workspace_id={ws_id}", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        # Get
        resp = client.get(f"/v1/repositories/{repo_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == repo_id

        # Update
        resp = client.patch(
            f"/v1/repositories/{repo_id}",
            json={"name": "widget-v2", "description": "updated"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "widget-v2"
        assert resp.json()["data"]["description"] == "updated"

        # Branch listing (empty until clone)
        resp = client.get(f"/v1/repositories/{repo_id}/branches", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"] == []

        # Status
        resp = client.get(f"/v1/repositories/{repo_id}/status", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["clone_status"] == "pending"

        # Archive -> hidden from default list
        resp = client.post(f"/v1/repositories/{repo_id}/archive", headers=headers)
        assert resp.status_code == 204
        resp = client.get(f"/v1/repositories?workspace_id={ws_id}", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0

        # Include archived in list
        resp = client.get(
            f"/v1/repositories?workspace_id={ws_id}&include_archived=true",
            headers=headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        # Restore -> visible again
        resp = client.post(f"/v1/repositories/{repo_id}/restore", headers=headers)
        assert resp.status_code == 200
        resp = client.get(f"/v1/repositories?workspace_id={ws_id}", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        # Delete (soft) -> not found
        resp = client.delete(f"/v1/repositories/{repo_id}", headers=headers)
        assert resp.status_code == 204
        resp = client.get(f"/v1/repositories/{repo_id}", headers=headers)
        assert resp.status_code == 404

    def test_import_github_and_local(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "repo-import@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}
        ws_id = _create_workspace(client, headers, "repo-import-ws")

        resp = client.post(
            "/v1/repositories/import",
            json={
                "workspace_id": ws_id,
                "provider": "github",
                "url": "https://github.com/octocat/Hello-World",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["provider"] == "github"
        assert resp.json()["data"]["name"] == "Hello-World"

        resp = client.post(
            "/v1/repositories/import",
            json={
                "workspace_id": ws_id,
                "provider": "local",
                "path": "/tmp/forge-test-folder",
                "name": "local-repo",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["provider"] == "local"
        assert resp.json()["data"]["local_path"] == "/tmp/forge-test-folder"

    def test_repository_authorization(self, integration_client) -> None:
        client = integration_client
        owner_token = _register(client, "repo-authz-owner@example.com")
        outsider_token = _register(client, "repo-authz-out@example.com")
        owner_headers = {"Host": "localhost", "Authorization": f"Bearer {owner_token}"}
        outsider_headers = {"Host": "localhost", "Authorization": f"Bearer {outsider_token}"}

        ws_id = _create_workspace(client, owner_headers, "repo-authz-ws")
        create = client.post(
            "/v1/repositories",
            json={
                "workspace_id": ws_id,
                "name": "private-repo",
                "owner": "alice",
                "provider": "github",
            },
            headers=owner_headers,
        )
        assert create.status_code == 201
        repo_id = create.json()["data"]["id"]

        # Outsider (not a member) cannot access the repository.
        resp = client.get(f"/v1/repositories/{repo_id}", headers=outsider_headers)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "authorization_error"

        # Outsider cannot list workspace repositories.
        resp = client.get(f"/v1/repositories?workspace_id={ws_id}", headers=outsider_headers)
        assert resp.status_code == 403

        # Outsider cannot delete.
        resp = client.delete(f"/v1/repositories/{repo_id}", headers=outsider_headers)
        assert resp.status_code == 403

        # Outsider cannot archive.
        resp = client.post(f"/v1/repositories/{repo_id}/archive", headers=outsider_headers)
        assert resp.status_code == 403
