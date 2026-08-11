"""End-to-end context & memory engine integration tests.

Exercises the full stack against live PostgreSQL/Redis: register → create
workspace → create repository → clone → index → create workspace /
repository / user memories → search → assemble context (including
repository intelligence) → RBAC → user-memory isolation → post-reindex
invalidation → Redis conversation context.  Skips automatically when
PostgreSQL is unreachable.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forge_api.infrastructure.database import create_session_factory
from forge_api.infrastructure.settings import get_settings
from forge_api.presentation.http.dependencies import create_index_services

# Reset the shared in-memory rate limiter before every test in this module.
pytestmark = pytest.mark.usefixtures("_reset_rate_limiter")


def _register(client: TestClient, email: str) -> str:
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "supersecure12"},
        headers={"Host": "localhost"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["access_token"]


def _create_workspace(client: TestClient, headers, slug: str) -> str:
    resp = client.post(
        "/v1/workspaces",
        json={"name": "FP6 WS", "slug": slug},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _make_source_repo() -> str:
    """Create a tiny git repository on disk and return its path."""
    tmp = Path(tempfile.mkdtemp(prefix="forge_fp6_src_"))
    (tmp / "app.py").write_text(
        "import os\n"
        "def greet(name):\n"
        "    return 'hi ' + name\n",
        encoding="utf-8",
    )
    (tmp / "README.md").write_text("# Demo repo\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp), "config", "user.email", "t@example.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )
    subprocess.run(["git", "-C", str(tmp), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp), "commit", "-qm", "init"],
        check=True, capture_output=True,
    )
    return str(tmp)


async def _index_via_service(repository_id) -> dict:
    """Run the indexing pipeline directly (the background worker is disabled)."""
    settings = get_settings()
    async with create_session_factory(settings)() as db:
        svc, jobs = create_index_services(db)
        job = await jobs.claim_next_index_job()
        assert job is not None, "no pending index job found"
        await jobs.start_job(job.id)
        stats = await svc.index_repository(repository_id)
        await jobs.complete_job(job.id)
        await db.commit()
        return {
            "files": stats.files_indexed,
            "symbols": stats.symbols,
            "dependencies": stats.dependencies,
            "chunks": stats.chunks,
        }


def _onboard(client: TestClient, headers, slug: str):
    """Register-free helper to create workspace + repo + index."""
    ws_id = _create_workspace(client, headers, slug)
    source = _make_source_repo()
    resp = client.post(
        "/v1/repositories",
        json={
            "workspace_id": ws_id,
            "name": "demo",
            "owner": "alice",
            "provider": "github",
            "remote_url": source,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    repo_id = resp.json()["data"]["id"]
    resp = client.post(
        "/v1/repositories/clone",
        json={"repository_id": repo_id},
        headers=headers,
    )
    assert resp.status_code == 202, resp.text
    resp = client.post(f"/v1/repositories/{repo_id}/index", headers=headers)
    assert resp.status_code == 202, resp.text
    return ws_id, repo_id


class TestMemoryContextEndToEnd:
    async def test_full_memory_context_flow(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "fp6-e2e@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}
        ws_id, repo_id = _onboard(client, headers, "fp6-e2e-ws")

        # Index and capture repository intelligence.
        stats = await _index_via_service(repo_id)
        assert stats["files"] >= 2
        assert stats["symbols"] >= 1

        # Create workspace / repository / user memories.
        resp = client.post(
            f"/v1/workspaces/{ws_id}/memories",
            json={
                "memory_type": "decision",
                "scope": "workspace",
                "content": "prefer repository ports",
                "tags": ["architecture"],
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        ws_memory_id = resp.json()["data"]["id"]

        resp = client.post(
            f"/v1/workspaces/{ws_id}/memories",
            json={
                "memory_type": "annotation",
                "scope": "repository",
                "repository_id": repo_id,
                "content": "greet is a helper",
                "source_file_path": "app.py",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        repo_memory_id = resp.json()["data"]["id"]

        resp = client.post(
            f"/v1/workspaces/{ws_id}/memories",
            json={
                "memory_type": "preference",
                "scope": "user",
                "content": "prefer async tests",
                "tags": ["pref"],
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        user_memory_id = resp.json()["data"]["id"]

        # List memories (workspace-level excludes user memories).
        resp = client.get(f"/v1/workspaces/{ws_id}/memories", headers=headers)
        assert resp.status_code == 200
        contents = {m["content"] for m in resp.json()["data"]}
        assert "prefer repository ports" in contents
        assert "prefer async tests" not in contents

        # User-scoped listing returns the owner's user memory.
        resp = client.get(
            f"/v1/workspaces/{ws_id}/memories?scope=user", headers=headers
        )
        assert resp.status_code == 200
        assert any(m["content"] == "prefer async tests" for m in resp.json()["data"])

        # Get one memory.
        resp = client.get(
            f"/v1/workspaces/{ws_id}/memories/{ws_memory_id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["memory_type"] == "decision"

        # Tag search.
        resp = client.post(
            f"/v1/workspaces/{ws_id}/memories/search",
            json={"tags": ["architecture"]},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["available"] is False
        assert any(
            r["content"] == "prefer repository ports"
            for r in resp.json()["data"]["results"]
        )

        # Assemble context — repository intelligence + memories included.
        resp = client.post(
            "/v1/context/assemble",
            json={
                "workspace_id": ws_id,
                "repository_id": repo_id,
                "query": "greet",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        sources = {e["source"] for e in data["entries"]}
        assert "memory" in sources
        assert "repository_symbol" in sources

        # File retrieval is driven by path-matching queries.
        resp = client.post(
            "/v1/context/assemble",
            json={
                "workspace_id": ws_id,
                "repository_id": repo_id,
                "query": "*.py",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert "repository_file" in {e["source"] for e in resp.json()["data"]["entries"]}

        # Update + archive a memory.
        resp = client.patch(
            f"/v1/workspaces/{ws_id}/memories/{ws_memory_id}",
            json={"content": "prefer repository ports (updated)"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["content"] == "prefer repository ports (updated)"

        # Delete a memory.
        resp = client.delete(
            f"/v1/workspaces/{ws_id}/memories/{user_memory_id}", headers=headers
        )
        assert resp.status_code == 204
        resp = client.get(
            f"/v1/workspaces/{ws_id}/memories/{user_memory_id}", headers=headers
        )
        assert resp.status_code == 404

        _ = repo_memory_id  # used by invalidation test

    async def test_user_memory_isolation_and_rbac(self, integration_client) -> None:
        client = integration_client
        owner = _register(client, "fp6-rbac-owner@example.com")
        outsider = _register(client, "fp6-rbac-out@example.com")
        member = _register(client, "fp6-rbac-member@example.com")
        owner_headers = {"Host": "localhost", "Authorization": f"Bearer {owner}"}
        outsider_headers = {"Host": "localhost", "Authorization": f"Bearer {outsider}"}
        member_headers = {"Host": "localhost", "Authorization": f"Bearer {member}"}

        ws_id = _create_workspace(client, owner_headers, "fp6-rbac-ws")

        # Owner creates a user memory.
        resp = client.post(
            f"/v1/workspaces/{ws_id}/memories",
            json={
                "memory_type": "preference",
                "scope": "user",
                "content": "owner private note",
            },
            headers=owner_headers,
        )
        assert resp.status_code == 201, resp.text
        memory_id = resp.json()["data"]["id"]

        # Outsider (not a member) is blocked entirely.
        resp = client.get(
            f"/v1/workspaces/{ws_id}/memories/{memory_id}", headers=outsider_headers
        )
        assert resp.status_code == 403

        # Add the member user to the workspace.
        settings = get_settings()
        async with create_session_factory(settings)() as db:
            from forge_api.infrastructure.user_repository import SqlUserRepository

            member_record = await SqlUserRepository(db).find_by_email(
                "fp6-rbac-member@example.com"
            )
            member_id = str(member_record.id)
        resp = client.post(
            f"/v1/workspaces/{ws_id}/members",
            json={"user_id": member_id, "role": "member"},
            headers=owner_headers,
        )
        assert resp.status_code in (201, 200), resp.text

        # A member who is not the owner cannot read the owner's user memory.
        resp = client.get(
            f"/v1/workspaces/{ws_id}/memories/{memory_id}", headers=member_headers
        )
        assert resp.status_code == 403

        # The owner can read their own user memory.
        resp = client.get(
            f"/v1/workspaces/{ws_id}/memories/{memory_id}", headers=owner_headers
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["content"] == "owner private note"

    async def test_reindex_invalidates_linked_memories(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "fp6-invalid@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}
        ws_id, repo_id = _onboard(client, headers, "fp6-invalid-ws")
        await _index_via_service(repo_id)

        # Linked repository memory (references app.py) + unrelated workspace memory.
        resp = client.post(
            f"/v1/workspaces/{ws_id}/memories",
            json={
                "memory_type": "annotation",
                "scope": "repository",
                "repository_id": repo_id,
                "content": "notes on app.py",
                "source_file_path": "app.py",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        linked_id = resp.json()["data"]["id"]
        resp = client.post(
            f"/v1/workspaces/{ws_id}/memories",
            json={
                "memory_type": "decision",
                "scope": "workspace",
                "content": "unrelated decision",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        unrelated_id = resp.json()["data"]["id"]

        # Modify app.py and re-run the index.
        settings = get_settings()
        async with create_session_factory(settings)() as db:
            from forge_api.infrastructure.repository_repository import (
                SqlRepositoryRepository,
            )
            repo = await SqlRepositoryRepository(db).get(repo_id)
            src = Path(repo.local_path)
            (src / "app.py").write_text(
                "import os\n"
                "def greet(name):\n"
                "    return 'HELLO ' + name\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(src), "add", "."], check=True, capture_output=True
            )
            subprocess.run(
                ["git", "-C", str(src), "commit", "-qm", "change"],
                check=True, capture_output=True,
            )
            await db.commit()

        await _index_via_service(repo_id)

        # Linked memory is stale; unrelated memory stays active.
        resp = client.get(
            f"/v1/workspaces/{ws_id}/memories/{linked_id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "stale"

        resp = client.get(
            f"/v1/workspaces/{ws_id}/memories/{unrelated_id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "active"

    async def test_conversation_context_redis(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "fp6-conv@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}
        conversation_id = "11111111-1111-1111-1111-111111111111"

        # Append two entries.
        for content in ("first turn", "second turn"):
            resp = client.post(
                f"/v1/context/conversation/{conversation_id}",
                json={"role": "user", "content": content},
                headers=headers,
            )
            if resp.status_code == 503:
                pytest.skip("Redis is unreachable; conversation context unavailable")
            assert resp.status_code == 201, resp.text

        resp = client.get(
            f"/v1/context/conversation/{conversation_id}", headers=headers
        )
        if resp.status_code == 503:
            pytest.skip("Redis is unreachable; conversation context unavailable")
        assert resp.status_code == 200
        assert [e["content"] for e in resp.json()["data"]] == [
            "first turn",
            "second turn",
        ]

        resp = client.delete(
            f"/v1/context/conversation/{conversation_id}", headers=headers
        )
        assert resp.status_code == 204
        resp = client.get(
            f"/v1/context/conversation/{conversation_id}", headers=headers
        )
        assert resp.json()["data"] == []
