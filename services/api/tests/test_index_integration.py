"""End-to-end repository intelligence integration tests.

Exercises the full stack against live PostgreSQL/Redis: register → create
workspace → create repository → real git clone of a local source repo →
index (files, symbols, dependencies, chunks) → structural + semantic search
endpoints. Skips automatically when PostgreSQL is unreachable.
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
        json={"name": "FP5 WS", "slug": slug},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _make_source_repo() -> str:
    """Create a tiny git repository on disk and return its path."""
    tmp = Path(tempfile.mkdtemp(prefix="forge_fp5_src_"))
    (tmp / "app.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "def greet(name):\n"
        "    return 'hi ' + name\n"
        "\n"
        "class Greeter:\n"
        "    def run(self):\n"
        "        return 1\n",
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


class TestIndexingEndToEnd:
    async def test_clone_index_parse_search(self, integration_client) -> None:
        client = integration_client
        token = _register(client, "fp5-e2e@example.com")
        headers = {"Host": "localhost", "Authorization": f"Bearer {token}"}
        ws_id = _create_workspace(client, headers, "fp5-e2e-ws")

        source = _make_source_repo()

        # Create the repository record.
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

        # Clone from the local path (no network needed).
        resp = client.post(
            "/v1/repositories/clone",
            json={"repository_id": repo_id},
            headers=headers,
        )
        assert resp.status_code == 202, resp.text
        assert resp.json()["meta"].get("index_job_id") is not None

        # Enqueue and run the index pipeline directly.
        resp = client.post(f"/v1/repositories/{repo_id}/index", headers=headers)
        assert resp.status_code == 202, resp.text
        stats = await _index_via_service(repo_id)
        assert stats["files"] >= 2  # app.py + README.md
        assert stats["symbols"] >= 3  # greet, Greeter, run
        assert stats["dependencies"] >= 2  # os, pathlib
        assert stats["chunks"] >= 1

        # Index status is now ready.
        resp = client.get(f"/v1/repositories/{repo_id}/index/status", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["index_status"] == "ready"

        # Files listing.
        resp = client.get(f"/v1/repositories/{repo_id}/files", headers=headers)
        assert resp.status_code == 200
        paths = {f["path"] for f in resp.json()["data"]}
        assert "app.py" in paths and "README.md" in paths

        # Symbol search.
        resp = client.get(
            f"/v1/repositories/{repo_id}/symbols?query=greet", headers=headers
        )
        assert resp.status_code == 200
        assert any(s["name"] == "greet" for s in resp.json()["data"])

        # File symbols.
        resp = client.get(
            f"/v1/repositories/{repo_id}/files/app.py/symbols", headers=headers
        )
        assert resp.status_code == 200
        names = {s["name"] for s in resp.json()["data"]["symbols"]}
        assert "Greeter" in names and "greet" in names

        # Dependencies.
        resp = client.get(
            f"/v1/repositories/{repo_id}/files/app.py/dependencies", headers=headers
        )
        assert resp.status_code == 200
        outgoing = {d["target_path"] for d in resp.json()["data"]["outgoing"]}
        assert "os" in outgoing

        # Semantic search degrades gracefully without embeddings.
        resp = client.post(
            f"/v1/repositories/{repo_id}/search",
            json={"query": "greet"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["available"] is False

    def test_index_authorization(self, integration_client) -> None:
        client = integration_client
        owner = _register(client, "fp5-authz-owner@example.com")
        outsider = _register(client, "fp5-authz-out@example.com")
        owner_headers = {"Host": "localhost", "Authorization": f"Bearer {owner}"}
        outsider_headers = {"Host": "localhost", "Authorization": f"Bearer {outsider}"}

        ws_id = _create_workspace(client, owner_headers, "fp5-authz-ws")
        resp = client.post(
            "/v1/repositories",
            json={
                "workspace_id": ws_id,
                "name": "private",
                "owner": "alice",
                "provider": "github",
            },
            headers=owner_headers,
        )
        repo_id = resp.json()["data"]["id"]

        # Outsider cannot view symbols or index status.
        for path in (
            f"/v1/repositories/{repo_id}/symbols",
            f"/v1/repositories/{repo_id}/index/status",
        ):
            resp = client.get(path, headers=outsider_headers)
            assert resp.status_code == 403, (path, resp.status_code)