"""add LLM conversation and usage tables

Revision ID: 0007_llm_context
Revises: 0006_context_memory
Create Date: 2026-08-12
"""
import sqlalchemy as sa

from alembic import op

revision = "0007_llm_context"
down_revision = "0006_context_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── conversations ──────────────────────────────────────────────
    op.create_table(
        "conversations",
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
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(16),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "message_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_conversations_workspace_id", "conversations", ["workspace_id"]
    )
    op.create_index(
        "ix_conversations_user_id", "conversations", ["user_id"]
    )
    op.create_index(
        "ix_conversations_status", "conversations", ["status"]
    )
    op.create_index(
        "ix_conversations_created_at", "conversations", ["created_at"]
    )

    # ─── messages ───────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("finish_reason", sa.String(32), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            server_default="complete",
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql",
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
    )

    op.create_index(
        "ix_messages_conversation_id", "messages", ["conversation_id"]
    )
    op.create_index(
        "ix_messages_role", "messages", ["role"]
    )
    op.create_index(
        "ix_messages_created_at", "messages", ["created_at"]
    )

    # ─── usage_events ───────────────────────────────────────────────
    op.create_table(
        "usage_events",
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
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column(
            "estimated_cost",
            sa.Float(),
            server_default=sa.text("0.0"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB, "postgresql",
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
    )

    op.create_index(
        "ix_usage_events_workspace_id", "usage_events", ["workspace_id"]
    )
    op.create_index(
        "ix_usage_events_user_id", "usage_events", ["user_id"]
    )
    op.create_index(
        "ix_usage_events_provider", "usage_events", ["provider"]
    )
    op.create_index(
        "ix_usage_events_model", "usage_events", ["model"]
    )
    op.create_index(
        "ix_usage_events_created_at", "usage_events", ["created_at"]
    )


def downgrade() -> None:
    op.drop_table("usage_events")
    op.drop_table("messages")
    op.drop_table("conversations")
