"""add agent hardening columns and indexes for heartbeat, retention, and usage

Revision ID: 0009_agent_hardening
Revises: 0008_agent_engine
Create Date: 2026-09-03
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_agent_hardening"
down_revision = "0008_agent_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── agent_sessions: heartbeat, worker_id & retention indexes ─────
    op.add_column(
        "agent_sessions",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_sessions",
        sa.Column("worker_id", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_agent_sessions_last_heartbeat_at",
        "agent_sessions",
        ["last_heartbeat_at"],
    )
    op.create_index(
        "ix_agent_sessions_completed_at",
        "agent_sessions",
        ["completed_at"],
    )

    # ─── usage_events: agent_session_id linkage ────────────────────────
    op.add_column(
        "usage_events",
        sa.Column(
            "agent_session_id",
            sa.Uuid(),
            sa.ForeignKey("agent_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_usage_events_agent_session_id",
        "usage_events",
        ["agent_session_id"],
    )


def downgrade() -> None:
    # ─── usage_events ──────────────────────────────────────────────────
    op.drop_index("ix_usage_events_agent_session_id", table_name="usage_events")
    op.drop_column("usage_events", "agent_session_id")

    # ─── agent_sessions ──────────────────────────────────────────────
    op.drop_index("ix_agent_sessions_completed_at", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_last_heartbeat_at", table_name="agent_sessions")
    op.drop_column("agent_sessions", "worker_id")
    op.drop_column("agent_sessions", "last_heartbeat_at")
