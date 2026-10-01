"""initial durable research schema

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("research",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("theme", sa.String(500), nullable=False),
        sa.Column("callback_url", sa.String(2048)), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("briefing_draft", sa.JSON(), nullable=False), sa.Column("error", sa.Text()),
        sa.Column("approved_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_research_status", "research", ["status"])
    op.create_table("research_points",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False), sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False), sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("is_parallelizable", sa.Boolean(), nullable=False), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False), sa.Column("audit", sa.JSON(), nullable=False))
    op.create_index("ix_research_points_research_id", "research_points", ["research_id"])
    op.create_table("evidences",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("research_point_id", sa.Uuid(), sa.ForeignKey("research_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("persona", sa.String(24), nullable=False), sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_title", sa.Text(), nullable=False), sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False), sa.Column("analysis", sa.Text(), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("research_point_id", "persona", "source_url", name="uq_evidence_source"))
    op.create_index("ix_evidences_research_point_id", "evidences", ["research_point_id"])
    op.create_table("agent_event_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research.id", ondelete="CASCADE"), nullable=False),
        sa.Column("persona", sa.String(24), nullable=False), sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False), sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_agent_event_logs_research_id", "agent_event_logs", ["research_id"])
    op.create_table("reports",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("content_markdown", sa.Text(), nullable=False), sa.Column("citation_metrics", sa.JSON(), nullable=False),
        sa.Column("audit_findings", sa.JSON(), nullable=False), sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("admin_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_admin_sessions_token_hash", "admin_sessions", ["token_hash"], unique=True)
    op.create_table("app_settings",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("encrypted_credentials", sa.JSON(), nullable=False),
        sa.Column("models", sa.JSON(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    for table in ("app_settings", "admin_sessions", "reports", "agent_event_logs", "evidences", "research_points", "research"):
        op.drop_table(table)
