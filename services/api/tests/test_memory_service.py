"""MemoryService unit tests.

Covers CRUD, workspace RBAC, user-memory isolation, search (semantic +
tag), tags, stale marking, lifecycle transitions, and graceful behavior
when embeddings are unavailable.
"""

from uuid import uuid4

import pytest

from forge_api.application.memory.memory_service import MemoryService
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import AuthorizationError, NotFoundError, ValidationError
from forge_api.infrastructure.embedding import NullEmbedder


def _build_service(fake_memories, fake_workspaces, fake_audit, embedding=None):
    return MemoryService(
        memories=fake_memories,
        workspaces=fake_workspaces,
        embedding=embedding or NullEmbedder(),
        audit=fake_audit,
    )


async def _workspace_with_member(ws, *, role: WorkspaceRole = WorkspaceRole.OWNER):
    workspace_id = uuid4()
    await ws.create(name="w", slug="w")
    user_id = uuid4()
    await ws.add_member(workspace_id=workspace_id, user_id=user_id, role=role)
    return workspace_id, user_id


async def _owner_service(fake_memories, fake_workspaces, fake_audit):
    ws = fake_workspaces
    workspace_id, user_id = await _workspace_with_member(ws)
    svc = _build_service(fake_memories, ws, fake_audit)
    return svc, workspace_id, user_id


# ─── Create ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_workspace_memory_by_owner(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid,
        user_id=uid,
        memory_type="decision",
        scope="workspace",
        content="use repository ports",
    )
    assert m.scope == "workspace"
    assert m.status.value == "active"
    assert m.created_by == uid
    assert fake_audit.events[-1]["event"].value == "memory.created"


@pytest.mark.asyncio
async def test_create_requires_membership(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc = _build_service(fake_memories, fake_workspaces, fake_audit)
    with pytest.raises(AuthorizationError):
        await svc.create_memory(
            workspace_id=uuid4(),
            user_id=uuid4(),
            memory_type="fact",
            scope="workspace",
            content="x",
        )


@pytest.mark.asyncio
async def test_create_workspace_memory_requires_write_role(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    ws = fake_workspaces
    wid, uid = await _workspace_with_member(ws, role=WorkspaceRole.VIEWER)
    svc = _build_service(fake_memories, ws, fake_audit)
    with pytest.raises(AuthorizationError):
        await svc.create_memory(
            workspace_id=wid,
            user_id=uid,
            memory_type="fact",
            scope="workspace",
            content="x",
        )


@pytest.mark.asyncio
async def test_create_user_memory_by_any_member(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    ws = fake_workspaces
    wid, uid = await _workspace_with_member(ws, role=WorkspaceRole.VIEWER)
    svc = _build_service(fake_memories, ws, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid,
        user_id=uid,
        memory_type="preference",
        scope="user",
        content="prefer async tests",
    )
    assert m.scope == "user"
    assert m.user_id == uid


@pytest.mark.asyncio
async def test_create_repository_memory_requires_repository_id(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    with pytest.raises(ValidationError):
        await svc.create_memory(
            workspace_id=wid,
            user_id=uid,
            memory_type="convention",
            scope="repository",
            content="x",
        )


@pytest.mark.asyncio
async def test_create_rejects_invalid_type_and_content(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    with pytest.raises(ValidationError):
        await svc.create_memory(
            workspace_id=wid,
            user_id=uid,
            memory_type="nonsense",
            scope="workspace",
            content="x",
        )
    with pytest.raises(ValidationError):
        await svc.create_memory(
            workspace_id=wid,
            user_id=uid,
            memory_type="fact",
            scope="workspace",
            content="   ",
        )


# ─── Read / list ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_memory_workspace_scoped(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid,
        user_id=uid,
        memory_type="fact",
        scope="workspace",
        content="hello",
    )
    fetched = await svc.get_memory(wid, m.id, uid)
    assert fetched.id == m.id


@pytest.mark.asyncio
async def test_get_memory_rejects_other_user_memory(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    ws = fake_workspaces
    wid, uid1 = await _workspace_with_member(ws, role=WorkspaceRole.OWNER)
    uid2 = uuid4()
    await ws.add_member(workspace_id=wid, user_id=uid2, role=WorkspaceRole.ADMIN)
    svc = _build_service(fake_memories, ws, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid,
        user_id=uid1,
        memory_type="preference",
        scope="user",
        content="private",
    )
    # Even an ADMIN cannot read another user's memory.
    with pytest.raises(AuthorizationError):
        await svc.get_memory(wid, m.id, uid2)


@pytest.mark.asyncio
async def test_get_memory_not_found(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    with pytest.raises(NotFoundError):
        await svc.get_memory(wid, uuid4(), uid)


@pytest.mark.asyncio
async def test_list_memories_default_excludes_user_memories(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    ws = fake_workspaces
    wid, uid = await _workspace_with_member(ws)
    svc = _build_service(fake_memories, ws, fake_audit)
    await svc.create_memory(
        workspace_id=wid, user_id=uid, memory_type="fact", scope="workspace", content="ws"
    )
    await svc.create_memory(
        workspace_id=wid, user_id=uid, memory_type="preference", scope="user", content="user-only"
    )
    listed = await svc.list_memories(workspace_id=wid, user_id=uid)
    contents = {m.content for m in listed}
    assert contents == {"ws"}


@pytest.mark.asyncio
async def test_list_user_memories_only_owner(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    ws = fake_workspaces
    wid, uid1 = await _workspace_with_member(ws)
    uid2 = uuid4()
    await ws.add_member(workspace_id=wid, user_id=uid2, role=WorkspaceRole.MEMBER)
    svc = _build_service(fake_memories, ws, fake_audit)
    await svc.create_memory(
        workspace_id=wid, user_id=uid1, memory_type="preference", scope="user", content="u1"
    )
    await svc.create_memory(
        workspace_id=wid, user_id=uid2, memory_type="preference", scope="user", content="u2"
    )
    for_uid1 = await svc.list_memories(workspace_id=wid, user_id=uid1, scope="user")
    assert {m.content for m in for_uid1} == {"u1"}


@pytest.mark.asyncio
async def test_list_by_tags(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    await svc.create_memory(
        workspace_id=wid,
        user_id=uid,
        memory_type="fact",
        scope="workspace",
        content="a",
        tags=["python", "api"],
    )
    await svc.create_memory(
        workspace_id=wid,
        user_id=uid,
        memory_type="fact",
        scope="workspace",
        content="b",
        tags=["python"],
    )
    listed = await svc.list_memories(workspace_id=wid, user_id=uid, tags=["python", "api"])
    assert {m.content for m in listed} == {"a"}


# ─── Update / lifecycle ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_memory(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid, user_id=uid, memory_type="fact", scope="workspace", content="old"
    )
    updated = await svc.update_memory(workspace_id=wid, memory_id=m.id, user_id=uid, content="new")
    assert updated.content == "new"


@pytest.mark.asyncio
async def test_update_other_user_memory_forbidden_for_member(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    ws = fake_workspaces
    wid, uid1 = await _workspace_with_member(ws)
    uid2 = uuid4()
    await ws.add_member(workspace_id=wid, user_id=uid2, role=WorkspaceRole.MEMBER)
    svc = _build_service(fake_memories, ws, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid, user_id=uid1, memory_type="preference", scope="user", content="private"
    )
    with pytest.raises(AuthorizationError):
        await svc.update_memory(workspace_id=wid, memory_id=m.id, user_id=uid2, content="hacked")


@pytest.mark.asyncio
async def test_delete_memory_soft_delete(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid, user_id=uid, memory_type="fact", scope="workspace", content="x"
    )
    await svc.delete_memory(wid, m.id, uid)
    with pytest.raises(NotFoundError):
        await svc.get_memory(wid, m.id, uid)
    assert fake_audit.events[-1]["event"].value == "memory.deleted"


@pytest.mark.asyncio
async def test_archive_and_restore(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid, user_id=uid, memory_type="fact", scope="workspace", content="x"
    )
    archived = await svc.archive_memory(wid, m.id, uid)
    assert archived.status.value == "archived"
    restored = await svc.restore_memory(wid, m.id, uid)
    assert restored.status.value == "active"


@pytest.mark.asyncio
async def test_reconfirm_stale_memory(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid, user_id=uid, memory_type="fact", scope="workspace", content="x"
    )
    await fake_memories.update(m.id, status="stale")
    reconfirmed = await svc.reconfirm_memory(wid, m.id, uid)
    assert reconfirmed.status.value == "active"


# ─── Search ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_by_tags_without_embeddings(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    await svc.create_memory(
        workspace_id=wid,
        user_id=uid,
        memory_type="fact",
        scope="workspace",
        content="a",
        tags=["python"],
    )
    result = await svc.search_memories(workspace_id=wid, user_id=uid, tags=["python"])
    assert result["available"] is False
    assert len(result["results"]) == 1


@pytest.mark.asyncio
async def test_search_requires_query_or_tags(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    with pytest.raises(ValidationError):
        await svc.search_memories(workspace_id=wid, user_id=uid)


@pytest.mark.asyncio
async def test_search_reports_unavailable_without_embeddings(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    await svc.create_memory(
        workspace_id=wid,
        user_id=uid,
        memory_type="fact",
        scope="workspace",
        content="greet",
        tags=["x"],
    )
    result = await svc.search_memories(workspace_id=wid, user_id=uid, query="greet")
    assert result["available"] is False


@pytest.mark.asyncio
async def test_embedding_unavailable_creation_succeeds_without_vector(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid, user_id=uid, memory_type="fact", scope="workspace", content="x"
    )
    assert m.embedding is None


# ─── Tag validation ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tags_normalized_and_limited(
    fake_memories,
    fake_workspaces,
    fake_audit,
):
    svc, wid, uid = await _owner_service(fake_memories, fake_workspaces, fake_audit)
    m = await svc.create_memory(
        workspace_id=wid,
        user_id=uid,
        memory_type="fact",
        scope="workspace",
        content="x",
        tags=["Python", "  API  "],
    )
    assert m.tags == ["python", "api"]
    with pytest.raises(ValidationError):
        await svc.create_memory(
            workspace_id=wid,
            user_id=uid,
            memory_type="fact",
            scope="workspace",
            content="x",
            tags=[f"tag-{i}" for i in range(30)],
        )
