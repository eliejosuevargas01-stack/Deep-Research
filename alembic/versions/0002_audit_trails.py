"""append-only audit decisions and operational callback outcomes

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("audit_trails",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("research_id", sa.Uuid(), sa.ForeignKey("research.id", ondelete="CASCADE"), nullable=False),
        sa.Column("point_id", sa.Uuid(), sa.ForeignKey("research_points.id", ondelete="CASCADE")),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("attempt", sa.Integer()),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_audit_trails_research_id", "audit_trails", ["research_id"])


def downgrade():
    op.drop_index("ix_audit_trails_research_id", table_name="audit_trails")
    op.drop_table("audit_trails")
