"""add repository tables

Revision ID: 0004_repository_onboarding
Revises: 0003_workspace_tenancy
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_repository_onboarding"
down_revision = "0003_workspace_tenancy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── repositories ───────────────────────────────────────────────
    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("remote_url", sa.String(2048), nullable=True),
        sa.Column("local_path", sa.String(1024), nullable=True),
        sa.Column("default_branch", sa.String(255), nullable=True),
        sa.Column("current_branch", sa.String(255), nullable=True),
        sa.Column("clone_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("sync_status", sa.String(16), nullable=False, server_default="idle"),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="private"),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("last_commit_hash", sa.String(64), nullable=True),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_repositories_workspace_id", "repositories", ["workspace_id"])
    op.create_index("ix_repositories_provider", "repositories", ["provider"])
    op.create_index("ix_repositories_clone_status", "repositories", ["clone_status"])

    # ─── repository_branches ────────────────────────────────────────
    op.create_table(
        "repository_branches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("commit_hash", sa.String(64), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_protected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("repository_id", "name", name="uq_repo_branch_name"),
    )
    op.create_index(
        "ix_repository_branches_repository_id", "repository_branches", ["repository_id"]
    )

    # ─── repository_sync_jobs ───────────────────────────────────────
    op.create_table(
        "repository_sync_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_repository_sync_jobs_repository_id", "repository_sync_jobs", ["repository_id"]
    )
    op.create_index("ix_repository_sync_jobs_status", "repository_sync_jobs", ["status"])

    # ─── repository_events ──────────────────────────────────────────
    op.create_table(
        "repository_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_repository_events_repository_id", "repository_events", ["repository_id"]
    )
    op.create_index("ix_repository_events_event_type", "repository_events", ["event_type"])
    op.create_index("ix_repository_events_created_at", "repository_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("repository_events")
    op.drop_table("repository_sync_jobs")
    op.drop_table("repository_branches")
    op.drop_table("repositories")
