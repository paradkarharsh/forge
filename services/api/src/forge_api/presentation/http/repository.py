"""Repository routes.

Full CRUD for repositories plus import, clone, branch discovery, and
status tracking. All responses use the global ``ok()`` / exception-handler
contracts.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from forge_api.application.indexing.index_service import RepositoryIndexService
from forge_api.application.indexing.search_service import SearchService
from forge_api.application.repositories.background_jobs import BackgroundJobService
from forge_api.application.repositories.clone_service import RepositoryCloneService
from forge_api.application.repositories.import_service import RepositoryImportService
from forge_api.application.repositories.repository_service import RepositoryService
from forge_api.domain.errors import ValidationError
from forge_api.domain.indexing import (
    ChunkRecord,
    DependencyRecord,
    FileRecord,
    SymbolRecord,
)
from forge_api.domain.repository import RepositoryRecord
from forge_api.presentation.http.contracts import ok
from forge_api.presentation.http.dependencies import (
    client_ip,
    client_user_agent,
    get_background_job_service,
    get_branch_repository,
    get_clone_service,
    get_import_service,
    get_index_service,
    get_repository_service,
    get_search_service,
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


class SearchRepositoryInput(BaseModel):
    query: str = Field(min_length=1, max_length=512)
    limit: int = Field(default=20, ge=1, le=100)
    language: str | None = Field(default=None, max_length=64)
    file_pattern: str | None = Field(default=None, max_length=2048)


class SymbolsQueryInput(BaseModel):
    query: str | None = Field(default=None, max_length=512)
    kind: str | None = Field(default=None, max_length=32)
    limit: int = Field(default=50, ge=1, le=500)


class FilesQueryInput(BaseModel):
    pattern: str | None = Field(default=None, max_length=2048)
    language: str | None = Field(default=None, max_length=64)
    limit: int = Field(default=50, ge=1, le=1000)


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


def _file_view(f: FileRecord) -> dict:
    return {
        "id": str(f.id),
        "path": f.path,
        "language": f.language,
        "size_bytes": f.size_bytes,
        "line_count": f.line_count,
        "commit_hash": f.commit_hash,
        "indexed_at": f.indexed_at.isoformat() if f.indexed_at else None,
    }


def _symbol_view(s: SymbolRecord) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "kind": s.kind.value,
        "signature": s.signature,
        "line_start": s.line_start,
        "line_end": s.line_end,
        "parent_symbol_id": str(s.parent_symbol_id) if s.parent_symbol_id else None,
    }


def _dependency_view(d: DependencyRecord) -> dict:
    return {
        "id": str(d.id),
        "target_path": d.target_path,
        "target_file_id": str(d.target_file_id) if d.target_file_id else None,
        "kind": d.kind.value,
        "is_external": d.is_external,
    }


def _chunk_view(c: ChunkRecord) -> dict:
    return {
        "id": str(c.id),
        "chunk_index": c.chunk_index,
        "content": c.content,
        "line_start": c.line_start,
        "line_end": c.line_end,
        "token_count": c.token_count,
        "has_embedding": c.embedding is not None,
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
    jobs: BackgroundJobService = Depends(get_background_job_service),
):
    repo = await svc.clone_repository(
        repository_id=body.repository_id,
        user_id=claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    # Automatically enqueue indexing for the freshly cloned repository.
    try:
        index_job = await jobs.enqueue_index(repository_id=body.repository_id)
        job_id = str(index_job.id)
    except Exception:
        job_id = None
    return ok(_repository_view(repo), meta={"index_job_id": job_id})


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


# ─── Repository intelligence ────────────────────────────────────────


@router.post("/{repository_id}/index", status_code=202)
async def index_repository(
    repository_id: UUID,
    claims=Depends(validated_claims),
    jobs: BackgroundJobService = Depends(get_background_job_service),
):
    job = await jobs.enqueue_index(repository_id=repository_id)
    return ok({"job_id": str(job.id), "status": job.status.value})


@router.get("/{repository_id}/index/status")
async def get_index_status(
    repository_id: UUID,
    claims=Depends(validated_claims),
    svc: RepositoryIndexService = Depends(get_index_service),
):
    status = await svc.get_index_status(repository_id, user_id=claims.user_id)
    return ok(status)


@router.post("/{repository_id}/search")
async def search_repository(
    repository_id: UUID,
    body: SearchRepositoryInput,
    claims=Depends(validated_claims),
    svc: SearchService = Depends(get_search_service),
):
    result = await svc.search_semantic(
        repository_id,
        user_id=claims.user_id,
        query=body.query,
        limit=body.limit,
    )
    results = []
    for item in result["results"]:
        if body.language and item["language"] != body.language:
            continue
        if body.file_pattern and not (item["file_path"] or "").startswith(
            body.file_pattern
        ):
            continue
        results.append(
            {
                "file_path": item["file_path"],
                "language": item["language"],
                "chunk": _chunk_view(item["chunk"]),
            }
        )
    return ok({"available": result["available"], "results": results})


@router.get("/{repository_id}/symbols")
async def list_or_search_symbols(
    repository_id: UUID,
    query: str | None = None,
    kind: str | None = None,
    limit: int = 50,
    claims=Depends(validated_claims),
    svc: SearchService = Depends(get_search_service),
):
    if query:
        symbols = await svc.search_symbols(
            repository_id,
            user_id=claims.user_id,
            query=query,
            kind=kind,
            limit=limit,
        )
    else:
        symbols = await svc.list_symbols(
            repository_id, user_id=claims.user_id, kind=kind
        )
    return ok([_symbol_view(s) for s in symbols])


@router.get("/{repository_id}/files")
async def list_files(
    repository_id: UUID,
    pattern: str | None = None,
    language: str | None = None,
    limit: int = 50,
    claims=Depends(validated_claims),
    svc: SearchService = Depends(get_search_service),
):
    files = await svc.search_files(
        repository_id,
        user_id=claims.user_id,
        pattern=pattern,
        language=language,
        limit=limit,
    )
    return ok([_file_view(f) for f in files])


@router.get("/{repository_id}/files/{path:path}/symbols")
async def get_file_symbols(
    repository_id: UUID,
    path: str,
    claims=Depends(validated_claims),
    svc: SearchService = Depends(get_search_service),
):
    data = await svc.get_file(
        repository_id, user_id=claims.user_id, file_path=path
    )
    return ok(
        {
            "file": _file_view(data["file"]),
            "symbols": [_symbol_view(s) for s in data["symbols"]],
            "chunks": [_chunk_view(c) for c in data["chunks"]],
        }
    )


@router.get("/{repository_id}/files/{path:path}/dependencies")
async def get_file_dependencies(
    repository_id: UUID,
    path: str,
    claims=Depends(validated_claims),
    svc: SearchService = Depends(get_search_service),
):
    data = await svc.get_dependencies(
        repository_id, user_id=claims.user_id, file_path=path
    )
    return ok(
        {
            "file": _file_view(data["file"]),
            "outgoing": [_dependency_view(d) for d in data["outgoing"]],
            "incoming": [_dependency_view(d) for d in data["incoming"]],
        }
    )
