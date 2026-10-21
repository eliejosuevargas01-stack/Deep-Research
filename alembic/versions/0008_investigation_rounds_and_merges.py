"""investigation rounds and merges migration

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("research_points") as batch_op:
        batch_op.add_column(sa.Column("investigation_round", sa.Integer(), nullable=True))

    with op.batch_alter_table("research_step_results") as batch_op:
        batch_op.add_column(sa.Column("round", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_research_step_results_round_worker",
            ["research_id", "step_id", "round", "worker"],
        )

    op.create_table(
        "investigation_merges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "research_id",
            sa.Uuid(),
            sa.ForeignKey("research.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            sa.Uuid(),
            sa.ForeignKey("research_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "research_id",
            "step_id",
            "round",
            name="uq_investigation_merges_research_step_round",
        ),
    )
    op.create_index(
        "ix_investigation_merges_research_id",
        "investigation_merges",
        ["research_id"],
    )
    op.create_index(
        "ix_investigation_merges_step_id",
        "investigation_merges",
        ["step_id"],
    )


def downgrade():
    op.drop_index("ix_investigation_merges_step_id", table_name="investigation_merges")
    op.drop_index("ix_investigation_merges_research_id", table_name="investigation_merges")
    op.drop_table("investigation_merges")

    with op.batch_alter_table("research_step_results") as batch_op:
        batch_op.drop_constraint("uq_research_step_results_round_worker", type_="unique")
        batch_op.drop_column("round")

    with op.batch_alter_table("research_points") as batch_op:
        batch_op.drop_column("investigation_round")
