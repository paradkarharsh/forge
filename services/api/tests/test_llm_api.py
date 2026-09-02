"""Integration tests for FP7 LLM API endpoints and Conversation Service."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from forge_api.domain.security import AccessClaims
from forge_api.presentation.http.dependencies import (
    get_conversation_service,
    validated_claims,
)
from tests.test_llm_conversation import (
    FakeAuditLogger,
    FakeConversationRepository,
    FakeMessageRepository,
    FakeUsageEventRepository,
    ModelRegistry,
    _create_service,
)


@pytest.fixture
def auth_headers(fake_tokens, fake_users, fake_sessions):
    import asyncio

    user = asyncio.run(fake_users.create(email="llm_user@example.com", password_hash=None))
    expires = datetime.now(UTC) + timedelta(days=1)
    session = asyncio.run(
        fake_sessions.create(
            user_id=user.id,
            family_id=uuid4(),
            refresh_hash="hash",
            expires_at=expires,
            device_name="test",
            ip_address="127.0.0.1",
            user_agent="test",
        )
    )
    claims = AccessClaims(user_id=user.id, session_id=session.id)
    token = fake_tokens.create_access_token(claims)
    return {"Authorization": f"Bearer {token}"}, user, session


def test_unauthenticated_request_rejected(test_client):
    """Verify unauthenticated requests to protected endpoints return 401."""
    wid = uuid4()
    # Stateless complete without auth
    resp1 = test_client.post(
        "/v1/llm/complete",
        json={"model": "fake/echo", "messages": [{"role": "user", "content": "Hi"}]},
    )
    assert resp1.status_code == 401
    assert resp1.json()["success"] is False

    # Conversation create without auth
    resp2 = test_client.post(
        f"/v1/workspaces/{wid}/conversations",
        json={"title": "Unauthorized Conv"},
    )
    assert resp2.status_code == 401
    assert resp2.json()["success"] is False


def test_list_llm_models(test_client, auth_headers):
    headers, user, session = auth_headers
    response = test_client.get("/v1/llm/models", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    models = data["data"]
    assert len(models) >= 1
    model_ids = [m["model_id"] for m in models]
    assert "fake/echo" in model_ids


def test_stateless_complete_llm(test_client, auth_headers):
    headers, user, session = auth_headers
    claims = AccessClaims(user_id=user.id, session_id=session.id)

    test_client.app.dependency_overrides[validated_claims] = lambda: claims
    try:
        payload = {
            "model": "fake/echo",
            "messages": [{"role": "user", "content": "Hello LLM"}],
        }
        response = test_client.post("/v1/llm/complete", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        result = data["data"]
        assert "content" in result
        assert result["model"] == "fake/echo"
    finally:
        test_client.app.dependency_overrides.clear()


def test_conversation_api_endpoints_lifecycle(test_client, auth_headers):
    """Verify full conversation HTTP API lifecycle: create, list, get, messages, delete."""
    headers, user, session = auth_headers
    claims = AccessClaims(user_id=user.id, session_id=session.id)
    workspace_id = uuid4()

    fake_repos = {
        "conversations": FakeConversationRepository(),
        "messages": FakeMessageRepository(),
        "usage_events": FakeUsageEventRepository(),
        "registry": ModelRegistry(),
        "audit": FakeAuditLogger(),
    }
    svc = _create_service(fake_repos)

    test_client.app.dependency_overrides[validated_claims] = lambda: claims
    test_client.app.dependency_overrides[get_conversation_service] = lambda: svc

    try:
        # 1. Create conversation
        create_resp = test_client.post(
            f"/v1/workspaces/{workspace_id}/conversations",
            json={"title": "Sprint 7 Planning"},
            headers=headers,
        )
        assert create_resp.status_code == 201
        created_data = create_resp.json()["data"]
        conv_id = created_data["id"]
        assert created_data["title"] == "Sprint 7 Planning"
        assert created_data["workspace_id"] == str(workspace_id)

        # 2. List conversations
        list_resp = test_client.get(
            f"/v1/workspaces/{workspace_id}/conversations",
            headers=headers,
        )
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["meta"]["total"] == 1
        assert len(list_data["data"]) == 1

        # 3. Get conversation
        get_resp = test_client.get(
            f"/v1/workspaces/{workspace_id}/conversations/{conv_id}",
            headers=headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["id"] == conv_id

        # 4. List messages (empty initially)
        msg_resp = test_client.get(
            f"/v1/workspaces/{workspace_id}/conversations/{conv_id}/messages",
            headers=headers,
        )
        assert msg_resp.status_code == 200
        assert msg_resp.json()["meta"]["total"] == 0

        # 5. Delete conversation
        del_resp = test_client.delete(
            f"/v1/workspaces/{workspace_id}/conversations/{conv_id}",
            headers=headers,
        )
        assert del_resp.status_code == 204
    finally:
        test_client.app.dependency_overrides.clear()
