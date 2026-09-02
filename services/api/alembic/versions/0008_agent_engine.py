"""add agent engine tables

Revision ID: 0008_agent_engine
Revises: 0007_llm_context
Create Date: 2026-09-02
"""
import sqlalchemy as sa

from alembic import op

revision = "0008_agent_engine"
down_revision = "0007_llm_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── agent_sessions ──────────────────────────────────────────────
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(32),
            server_default="created",
            nullable=False,
        ),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column(
            "limits",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql"
            ),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metrics",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql"
            ),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "current_step",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql"
            ),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_agent_sessions_workspace_id", "agent_sessions", ["workspace_id"]
    )
    op.create_index(
        "ix_agent_sessions_user_id", "agent_sessions", ["user_id"]
    )
    op.create_index(
        "ix_agent_sessions_status", "agent_sessions", ["status"]
    )
    op.create_index(
        "ix_agent_sessions_created_at", "agent_sessions", ["created_at"]
    )

    # ─── agent_steps ─────────────────────────────────────────────────
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql"
            ),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_agent_steps_session_id", "agent_steps", ["session_id"]
    )
    op.create_index(
        "ix_agent_steps_session_sequence", "agent_steps", ["session_id", "sequence"]
    )

    # ─── agent_tool_calls ────────────────────────────────────────────
    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            sa.Uuid(),
            sa.ForeignKey("agent_steps.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column(
            "arguments",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql"
            ),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            server_default="pending_approval",
            nullable=False,
        ),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql"
            ),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_agent_tool_calls_session_id", "agent_tool_calls", ["session_id"]
    )
    op.create_index(
        "ix_agent_tool_calls_step_id", "agent_tool_calls", ["step_id"]
    )
    op.create_index(
        "ix_agent_tool_calls_status", "agent_tool_calls", ["status"]
    )
    op.create_index(
        "ix_agent_tool_calls_created_at", "agent_tool_calls", ["created_at"]
    )

    # ─── agent_approvals ─────────────────────────────────────────────
    op.create_table(
        "agent_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tool_call_id",
            sa.Uuid(),
            sa.ForeignKey("agent_tool_calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("arguments_hash", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decided_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql"
            ),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_agent_approvals_session_id", "agent_approvals", ["session_id"]
    )
    op.create_index(
        "ix_agent_approvals_tool_call_id", "agent_approvals", ["tool_call_id"]
    )
    op.create_index(
        "ix_agent_approvals_status", "agent_approvals", ["status"]
    )


def downgrade() -> None:
    op.drop_table("agent_approvals")
    op.drop_table("agent_tool_calls")
    op.drop_table("agent_steps")
    op.drop_table("agent_sessions")
