from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from forge_api.infrastructure.database.base import Base


class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OAuthIdentityModel(Base):
    __tablename__ = "oauth_identities"
    __table_args__ = (UniqueConstraint("provider", "subject"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SessionModel(Base):
    __tablename__ = "sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    refresh_hash: Mapped[str] = mapped_column(String(128), unique=True)
    family_id: Mapped[UUID] = mapped_column(default=uuid4, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    device_name: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AuditEventModel(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), index=True
    )
    event: Mapped[str] = mapped_column(String(64), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    reason: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class WorkspaceModel(Base):
    __tablename__ = "workspaces"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MembershipModel(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ─── Repository domain models ──────────────────────────────────────


class RepositoryModel(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        Index("ix_repositories_workspace_id", "workspace_id"),
        Index("ix_repositories_provider", "provider"),
        Index("ix_repositories_clone_status", "clone_status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    owner: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(16))
    remote_url: Mapped[str | None] = mapped_column(String(2048))
    local_path: Mapped[str | None] = mapped_column(String(1024))
    default_branch: Mapped[str | None] = mapped_column(String(255))
    current_branch: Mapped[str | None] = mapped_column(String(255))
    clone_status: Mapped[str] = mapped_column(String(16), default="pending")
    sync_status: Mapped[str] = mapped_column(String(16), default="idle")
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    description: Mapped[str | None] = mapped_column(String(1000))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    last_commit_hash: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RepositoryBranchModel(Base):
    __tablename__ = "repository_branches"
    __table_args__ = (
        UniqueConstraint("repository_id", "name", name="uq_repo_branch_name"),
        Index("ix_repository_branches_repository_id", "repository_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    commit_hash: Mapped[str | None] = mapped_column(String(64))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_protected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RepositorySyncJobModel(Base):
    __tablename__ = "repository_sync_jobs"
    __table_args__ = (
        Index("ix_repository_sync_jobs_repository_id", "repository_id"),
        Index("ix_repository_sync_jobs_status", "status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE")
    )
    job_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RepositoryEventModel(Base):
    __tablename__ = "repository_events"
    __table_args__ = (
        Index("ix_repository_events_repository_id", "repository_id"),
        Index("ix_repository_events_event_type", "event_type"),
        Index("ix_repository_events_created_at", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
