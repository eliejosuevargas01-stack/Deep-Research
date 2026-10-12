"""create briefings and briefing_versions tables

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "briefings",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("theme", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("points_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "briefing_versions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "briefing_id",
            sa.Uuid,
            sa.ForeignKey("briefings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("points_json", sa.JSON, nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("briefing_id", "version", name="uq_briefing_version"),
    )
    op.create_index(
        "ix_briefing_versions_briefing_id_version",
        "briefing_versions",
        ["briefing_id", "version"],
    )


def downgrade():
    op.drop_index(
        "ix_briefing_versions_briefing_id_version", table_name="briefing_versions"
    )
    op.drop_table("briefing_versions")
    op.drop_table("briefings")