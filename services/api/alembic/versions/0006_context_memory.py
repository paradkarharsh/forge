"""add context and memory engine tables

Revision ID: 0006_context_memory
Revises: 0005_repository_intelligence
Create Date: 2026-08-11
"""
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "0006_context_memory"
down_revision = "0005_repository_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("memory_type", sa.String(32), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            server_default="active",
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(1024), nullable=True),
        sa.Column("source_file_path", sa.String(2048), nullable=True),
        sa.Column("source_symbol_name", sa.String(512), nullable=True),
        sa.Column("source_commit_hash", sa.String(64), nullable=True),
        sa.Column(
            "confidence",
            sa.Float(),
            server_default=sa.text("1.0"),
            nullable=False,
        ),
        sa.Column(
            "tags",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql",
            ),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
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
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # B-tree indexes
    op.create_index("ix_memories_workspace_id", "memories", ["workspace_id"])
    op.create_index("ix_memories_repository_id", "memories", ["repository_id"])
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index("ix_memories_scope", "memories", ["scope"])
    op.create_index("ix_memories_memory_type", "memories", ["memory_type"])
    op.create_index("ix_memories_status", "memories", ["status"])
    op.create_index(
        "ix_memories_source_file_path", "memories", ["source_file_path"]
    )

    # GIN index for JSONB tags containment queries
    op.execute(
        "CREATE INDEX ix_memories_tags ON memories USING GIN (tags)"
    )


def downgrade() -> None:
    op.drop_table("memories")
