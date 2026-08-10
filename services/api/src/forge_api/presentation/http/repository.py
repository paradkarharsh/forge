"""Repository routes.

Full CRUD for repositories plus import, clone, branch discovery, and
status tracking. All responses use the global ``ok()`` / exception-handler
contracts.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from forge_api.application.repositories.clone_service import RepositoryCloneService
from forge_api.application.repositories.import_service import RepositoryImportService
from forge_api.application.repositories.repository_service import RepositoryService
from forge_api.domain.errors import ValidationError
from forge_api.domain.repository import RepositoryRecord
from forge_api.presentation.http.contracts import ok
from forge_api.presentation.http.dependencies import (
    client_ip,
    client_user_agent,
    get_branch_repository,
    get_clone_service,
    get_import_service,
    get_repository_service,
    validated_claims,
)

router = APIRouter(prefix="/repositories", tags=["repositories"])


# ─── Request bodies ────────────────────────────────────────────────


class CreateRepositoryInput(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=255)
    owner: str = Field(min_length=1, max_length=255)
    provider: str = Field(min_length=1, max_length=16)
    remote_url: str | None = Field(default=None, max_length=2048)
    local_path: str | None = Field(default=None, max_length=1024)
    default_branch: str | None = Field(default=None, max_length=255)
    visibility: str = Field(default="private", max_length=16)
    description: str | None = Field(default=None, max_length=1000)


class UpdateRepositoryInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    visibility: str | None = Field(default=None, max_length=16)


class ImportRepositoryInput(BaseModel):
    workspace_id: UUID
    provider: str = Field(min_length=1, max_length=16)
    url: str | None = Field(default=None, max_length=2048)
    path: str | None = Field(default=None, max_length=1024)
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    visibility: str = Field(default="private", max_length=16)


class CloneRepositoryInput(BaseModel):
    repository_id: UUID


# ─── Helpers ───────────────────────────────────────────────────────


def _repository_view(r: RepositoryRecord) -> dict:
    return {
        "id": str(r.id),
        "workspace_id": str(r.workspace_id),
        "name": r.name,
        "owner": r.owner,
        "provider": r.provider,
        "remote_url": r.remote_url,
        "local_path": r.local_path,
        "default_branch": r.default_branch,
        "current_branch": r.current_branch,
        "clone_status": r.clone_status.value,
        "sync_status": r.sync_status.value,
        "visibility": r.visibility.value,
        "description": r.description,
        "size_bytes": r.size_bytes,
        "last_commit_hash": r.last_commit_hash,
        "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
        "archived_at": r.archived_at.isoformat() if r.archived_at else None,
    }


def _branch_view(b) -> dict:
    return {
        "id": str(b.id),
        "repository_id": str(b.repository_id),
        "name": b.name,
        "commit_hash": b.commit_hash,
        "is_default": b.is_default,
        "is_protected": b.is_protected,
        "created_at": b.created_at.isoformat(),
    }


# ─── Repository CRUD ──────────────────────────────────────────────


@router.get("")
async def list_repositories(
    workspace_id: UUID,
    include_archived: bool = False,
    claims=Depends(validated_claims),
    svc: RepositoryService = Depends(get_repository_service),
):
    repos = await svc.list_repositories(
        workspace_id, claims.user_id, include_archived=include_archived
    )
    return ok([_repository_view(r) for r in repos])


@router.post("", status_code=201)
async def create_repository(
    body: CreateRepositoryInput,
    request: Request,
    claims=Depends(validated_claims),
    svc: RepositoryService = Depends(get_repository_service),
):
    repo = await svc.create_repository(
        workspace_id=body.workspace_id,
        user_id=claims.user_id,
        name=body.name,
        owner=body.owner,
        provider=body.provider,
        remote_url=body.remote_url,
        local_path=body.local_path,
        default_branch=body.default_branch,
        visibility=body.visibility,
        description=body.description,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    return ok(_repository_view(repo))


@router.get("/{repository_id}")
async def get_repository(
    repository_id: UUID,
    claims=Depends(validated_claims),
    svc: RepositoryService = Depends(get_repository_service),
):
    repo = await svc.get_repository(repository_id, claims.user_id)
    return ok(_repository_view(repo))


@router.patch("/{repository_id}")
async def update_repository(
    repository_id: UUID,
    body: UpdateRepositoryInput,
    request: Request,
    claims=Depends(validated_claims),
    svc: RepositoryService = Depends(get_repository_service),
):
    provided = body.model_fields_set
    kwargs: dict = {}
    if "name" in provided:
        kwargs["name"] = body.name
    if "description" in provided:
        kwargs["description"] = body.description
    if "visibility" in provided:
        kwargs["visibility"] = body.visibility
    repo = await svc.update_repository(
        repository_id=repository_id,
        user_id=claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
        **kwargs,
    )
    return ok(_repository_view(repo))


@router.delete("/{repository_id}", status_code=204)
async def delete_repository(
    repository_id: UUID,
    request: Request,
    claims=Depends(validated_claims),
    svc: RepositoryService = Depends(get_repository_service),
):
    await svc.delete_repository(
        repository_id=repository_id,
        user_id=claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )


# ─── Import ────────────────────────────────────────────────────────


@router.post("/import", status_code=201)
async def import_repository(
    body: ImportRepositoryInput,
    request: Request,
    claims=Depends(validated_claims),
    svc: RepositoryImportService = Depends(get_import_service),
):
    if body.provider == "local":
        if not body.path:
            raise ValidationError("path is required for local imports")
        repo = await svc.import_local(
            workspace_id=body.workspace_id,
            user_id=claims.user_id,
            path=body.path,
            name=body.name,
            description=body.description,
            ip_address=client_ip(request),
            user_agent=client_user_agent(request),
        )
    else:
        if not body.url:
            raise ValidationError("url is required for remote imports")
        repo = await svc.import_github(
            workspace_id=body.workspace_id,
            user_id=claims.user_id,
            url=body.url,
            description=body.description,
            visibility=body.visibility,
            ip_address=client_ip(request),
            user_agent=client_user_agent(request),
        )
    return ok(_repository_view(repo))


# ─── Clone ─────────────────────────────────────────────────────────


@router.post("/clone", status_code=202)
async def clone_repository(
    body: CloneRepositoryInput,
    request: Request,
    claims=Depends(validated_claims),
    svc: RepositoryCloneService = Depends(get_clone_service),
):
    repo = await svc.clone_repository(
        repository_id=body.repository_id,
        user_id=claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    return ok(_repository_view(repo))


# ─── Restore ───────────────────────────────────────────────────────


@router.post("/{repository_id}/archive", status_code=204)
async def archive_repository(
    repository_id: UUID,
    request: Request,
    claims=Depends(validated_claims),
    svc: RepositoryService = Depends(get_repository_service),
):
    await svc.archive_repository(
        repository_id=repository_id,
        user_id=claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )


@router.post("/{repository_id}/restore")
async def restore_repository(
    repository_id: UUID,
    request: Request,
    claims=Depends(validated_claims),
    svc: RepositoryService = Depends(get_repository_service),
):
    repo = await svc.restore_repository(
        repository_id=repository_id,
        user_id=claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    return ok(_repository_view(repo))


# ─── Branches ──────────────────────────────────────────────────────


@router.get("/{repository_id}/branches")
async def list_branches(
    repository_id: UUID,
    claims=Depends(validated_claims),
    repo_svc: RepositoryService = Depends(get_repository_service),
    branch_repo=Depends(get_branch_repository),
):
    # Verify access
    await repo_svc.get_repository(repository_id, claims.user_id)
    branches = await branch_repo.list_by_repository(repository_id)
    return ok([_branch_view(b) for b in branches])


# ─── Status ────────────────────────────────────────────────────────


@router.get("/{repository_id}/status")
async def get_repository_status(
    repository_id: UUID,
    claims=Depends(validated_claims),
    svc: RepositoryCloneService = Depends(get_clone_service),
):
    status = await svc.get_repository_status(repository_id, claims.user_id)
    return ok(status)
