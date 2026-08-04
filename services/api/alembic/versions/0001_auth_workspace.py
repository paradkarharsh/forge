"""create authentication and workspace foundation

Revision ID: 0001_auth_workspace
Revises:
Create Date: 2026-08-03
"""
import sqlalchemy as sa

from alembic import op

revision="0001_auth_workspace"; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
    op.create_table("users",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("email",sa.String(320),nullable=False,unique=True),sa.Column("password_hash",sa.String(255)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_table("workspaces",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("name",sa.String(120),nullable=False),sa.Column("deleted_at",sa.DateTime(timezone=True)))
    op.create_table("workspace_memberships",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("workspace_id",sa.Uuid(),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("role",sa.String(16),nullable=False),sa.UniqueConstraint("workspace_id","user_id"))
    op.create_table("sessions",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("user_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("refresh_hash",sa.String(128),nullable=False,unique=True),sa.Column("family_id",sa.Uuid(),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("revoked_at",sa.DateTime(timezone=True)),sa.Column("replaced_at",sa.DateTime(timezone=True)),sa.Column("device_name",sa.String(255)),sa.Column("ip_address",sa.String(64)),sa.Column("user_agent",sa.String(512)),sa.Column("last_active_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_sessions_family_id","sessions",["family_id"])
    op.create_index("ix_sessions_user_id","sessions",["user_id"])
    op.create_index("ix_sessions_last_active_at","sessions",["last_active_at"])
def downgrade(): op.drop_table("sessions"); op.drop_table("workspace_memberships"); op.drop_table("workspaces"); op.drop_table("users")
