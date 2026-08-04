"""Workspace routes.

Full CRUD for workspaces plus membership management. All responses
use the global ``ok()`` / exception-handler contracts.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from forge_api.application.workspaces.workspace_service import WorkspaceService
from forge_api.domain.auth import WorkspaceRole
from forge_api.presentation.http.contracts import ok
from forge_api.presentation.http.dependencies import (
    client_ip,
    client_user_agent,
    get_workspace_service,
    validated_claims,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# ─── Request bodies ────────────────────────────────────────────────


_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]*[a-z0-9]$"


class CreateWorkspaceInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(
        default=None, min_length=2, max_length=140, pattern=_SLUG_PATTERN
    )
    description: str | None = Field(default=None, max_length=500)


class UpdateWorkspaceInput(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = Field(
        default=None, min_length=2, max_length=140, pattern=_SLUG_PATTERN
    )
    description: str | None = None


class AddMemberInput(BaseModel):
    user_id: UUID
    role: WorkspaceRole = WorkspaceRole.MEMBER


class ChangeMemberRoleInput(BaseModel):
    role: WorkspaceRole


# ─── Helpers ───────────────────────────────────────────────────────


def _workspace_view(w) -> dict:
    return {
        "id": str(w.id),
        "name": w.name,
        "slug": w.slug,
        "description": w.description,
        "created_at": w.created_at.isoformat(),
    }


def _member_view(m) -> dict:
    return {
        "user_id": str(m.user_id),
        "workspace_id": str(m.workspace_id),
        "role": m.role.value,
        "created_at": m.created_at.isoformat(),
    }


# ─── Workspace CRUD ───────────────────────────────────────────────


@router.get("")
async def list_workspaces(
    claims=Depends(validated_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    rows = await svc.list_workspaces(claims.user_id)
    return ok(
        [
            {**_workspace_view(w), "role": role.value}
            for w, role in rows
        ]
    )


@router.post("", status_code=201)
async def create_workspace(
    body: CreateWorkspaceInput,
    request: Request,
    claims=Depends(validated_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    workspace, role = await svc.create_workspace(
        name=body.name,
        owner_id=claims.user_id,
        slug=body.slug,
        description=body.description,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    return ok({**_workspace_view(workspace), "role": role.value})


@router.get("/by-slug/{slug}")
async def get_workspace_by_slug(
    slug: str,
    claims=Depends(validated_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    workspace = await svc.get_workspace_by_slug(slug)
    return ok(_workspace_view(workspace))


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: UUID,
    claims=Depends(validated_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    workspace = await svc.get_workspace(workspace_id)
    return ok(_workspace_view(workspace))


@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: UUID,
    body: UpdateWorkspaceInput,
    request: Request,
    claims=Depends(validated_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    provided = body.model_fields_set
    kwargs = {}
    if "name" in provided:
        kwargs["name"] = body.name
    if "slug" in provided:
        kwargs["slug"] = body.slug
    if "description" in provided:
        kwargs["description"] = body.description
    workspace = await svc.update_workspace(
        workspace_id=workspace_id,
        user_id=claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
        **kwargs,
    )
    return ok(_workspace_view(workspace))


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: UUID,
    request: Request,
    claims=Depends(validated_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    await svc.delete_workspace(
        workspace_id=workspace_id,
        user_id=claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )


# ─── Membership management ─────────────────────────────────────────


@router.get("/{workspace_id}/members")
async def list_members(
    workspace_id: UUID,
    claims=Depends(validated_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    members = await svc.list_members(workspace_id, claims.user_id)
    return ok([_member_view(m) for m in members])


@router.post("/{workspace_id}/members", status_code=201)
async def add_member(
    workspace_id: UUID,
    body: AddMemberInput,
    request: Request,
    claims=Depends(validated_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    await svc.add_member(
        workspace_id=workspace_id,
        actor_id=claims.user_id,
        target_user_id=body.user_id,
        role=body.role,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    return ok({"added": True})


@router.delete("/{workspace_id}/members/{user_id}", status_code=204)
async def remove_member(
    workspace_id: UUID,
    user_id: UUID,
    request: Request,
    claims=Depends(validated_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    await svc.remove_member(
        workspace_id=workspace_id,
        actor_id=claims.user_id,
        target_user_id=user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )


@router.patch("/{workspace_id}/members/{user_id}")
async def change_member_role(
    workspace_id: UUID,
    user_id: UUID,
    body: ChangeMemberRoleInput,
    request: Request,
    claims=Depends(validated_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    await svc.change_member_role(
        workspace_id=workspace_id,
        actor_id=claims.user_id,
        target_user_id=user_id,
        role=body.role,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    return ok({"updated": True})
