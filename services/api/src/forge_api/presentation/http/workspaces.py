"""Workspace routes."""
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from forge_api.application.workspaces.workspace_service import WorkspaceService
from forge_api.presentation.http.contracts import ok
from forge_api.presentation.http.dependencies import (
    client_ip,
    client_user_agent,
    current_claims,
    get_workspace_service,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)


@router.get("")
async def list_workspaces(
    claims=Depends(current_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    rows = await svc.list_workspaces(claims.user_id)
    return ok(
        [
            {"id": str(w.id), "name": w.name, "role": role.value}
            for w, role in rows
        ]
    )


@router.post("", status_code=201)
async def create_workspace(
    body: WorkspaceInput,
    request: Request,
    claims=Depends(current_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    workspace, role = await svc.create_workspace(
        name=body.name,
        owner_id=claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    return ok({"id": str(workspace.id), "name": workspace.name, "role": role.value})


@router.patch("/{workspace_id}")
async def rename_workspace(
    workspace_id: UUID,
    body: WorkspaceInput,
    request: Request,
    claims=Depends(current_claims),
    svc: WorkspaceService = Depends(get_workspace_service),
):
    workspace = await svc.rename_workspace(
        workspace_id=workspace_id,
        user_id=claims.user_id,
        name=body.name,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    return ok({"id": str(workspace.id), "name": workspace.name})
