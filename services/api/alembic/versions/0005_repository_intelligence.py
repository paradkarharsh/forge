"""add repository intelligence tables

Revision ID: 0005_repository_intelligence
Revises: 0004_repository_onboarding
Create Date: 2026-08-10
"""
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "0005_repository_intelligence"
down_revision = "0004_repository_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vector storage requires the pgvector extension. The Docker init script
    # installs it, but adding it here makes the migration self-contained for
    # databases provisioned at runtime (e.g. the integration test database).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ─── index metadata on repositories ──────────────────────────────
    op.add_column(
        "repositories",
        sa.Column("index_status", sa.String(16), server_default="pending", nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("file_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("symbol_count", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_repositories_index_status", "repositories", ["index_status"]
    )

    # ─── repository_files ────────────────────────────────────────────
    op.create_table(
        "repository_files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(2048), nullable=False),
        sa.Column("language", sa.String(64), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=True),
        sa.Column("commit_hash", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("repository_id", "path", name="uq_repo_file_path"),
    )
    op.create_index(
        "ix_repository_files_repository_id", "repository_files", ["repository_id"]
    )
    op.create_index("ix_repository_files_language", "repository_files", ["language"])

    # ─── repository_symbols ──────────────────────────────────────────
    op.create_table(
        "repository_symbols",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "file_id",
            sa.Uuid(),
            sa.ForeignKey("repository_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("signature", sa.String(2048), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column(
            "parent_symbol_id",
            sa.Uuid(),
            sa.ForeignKey("repository_symbols.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_repository_symbols_file_id", "repository_symbols", ["file_id"])
    op.create_index(
        "ix_repository_symbols_repository_id", "repository_symbols", ["repository_id"]
    )
    op.create_index("ix_repository_symbols_kind", "repository_symbols", ["kind"])
    op.create_index("ix_repository_symbols_name", "repository_symbols", ["name"])

    # ─── repository_dependencies ─────────────────────────────────────
    op.create_table(
        "repository_dependencies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id",
            sa.Uuid(),
            sa.ForeignKey("repository_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_path", sa.String(2048), nullable=False),
        sa.Column(
            "target_file_id",
            sa.Uuid(),
            sa.ForeignKey("repository_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("is_external", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        "ix_repository_dependencies_repository_id",
        "repository_dependencies",
        ["repository_id"],
    )
    op.create_index(
        "ix_repository_dependencies_source_file_id",
        "repository_dependencies",
        ["source_file_id"],
    )

    # ─── repository_chunks ───────────────────────────────────────────
    op.create_table(
        "repository_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "file_id",
            sa.Uuid(),
            sa.ForeignKey("repository_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.UniqueConstraint("file_id", "chunk_index", name="uq_repo_chunk_file_index"),
    )
    op.create_index("ix_repository_chunks_file_id", "repository_chunks", ["file_id"])
    op.create_index(
        "ix_repository_chunks_repository_id", "repository_chunks", ["repository_id"]
    )


def downgrade() -> None:
    op.drop_table("repository_chunks")
    op.drop_table("repository_dependencies")
    op.drop_table("repository_symbols")
    op.drop_table("repository_files")
    op.drop_index("ix_repositories_index_status", table_name="repositories")
    op.drop_column("repositories", "symbol_count")
    op.drop_column("repositories", "file_count")
    op.drop_column("repositories", "indexed_at")
    op.drop_column("repositories", "index_status")