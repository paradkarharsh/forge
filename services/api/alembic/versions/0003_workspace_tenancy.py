"""add workspace slug and description columns

Revision ID: 0003_workspace_tenancy
Revises: 0002_audit_oauth_context
Create Date: 2026-08-04
"""
import sqlalchemy as sa

from alembic import op

revision = "0003_workspace_tenancy"
down_revision = "0002_audit_oauth_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("slug", sa.String(140), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column("description", sa.String(500), nullable=True),
    )

    # Backfill existing rows: use the workspace id hex as a slug placeholder.
    op.execute("UPDATE workspaces SET slug = REPLACE(id::text, '-', '') WHERE slug IS NULL")

    op.alter_column("workspaces", "slug", nullable=False)
    op.create_unique_constraint("uq_workspaces_slug", "workspaces", ["slug"])
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_constraint("uq_workspaces_slug", "workspaces", type_="unique")
    op.drop_column("workspaces", "description")
    op.drop_column("workspaces", "slug")
