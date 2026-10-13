"""research_step_results table and canonical status migration

Revision ID: 0007
Revises: 0006
"""
import json
import uuid

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

RESEARCH_STATUS_MAP = {
    "scouting": "BRIEFING",
    "revising": "BRIEFING",
    "pending_approval": "PENDING_APPROVAL",
    "approved": "SCRAPER",
    "in_progress": "SCRAPER",
    "completed": "DONE",
    "completed_but_callback_failed": "DONE",
    "blocked": "FAILED",
    "failed": "FAILED",
    "interrupted": "FAILED",
}

BRIEFING_STATUS_MAP = {
    "generating": "BRIEFING",
    "draft": "PENDING_APPROVAL",
    "approved": "SCRAPER",
    "failed": "FAILED",
}


RESEARCH_BACKFILL_SQL = sa.text(
    "INSERT INTO research (id, theme, status, briefing_draft, created_at, updated_at) "
    "VALUES (:id, :theme, :status, '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
).bindparams(sa.bindparam("id", type_=sa.Uuid))

POINT_BACKFILL_SQL = sa.text(
    "INSERT INTO research_points "
    "(id, research_id, position, title, description, dependencies, "
    "is_parallelizable, status, attempt_count, audit) "
    "VALUES (:id, :research_id, :position, :title, :description, "
    "'[]', TRUE, 'SCRAPER_PENDING', 0, '{}')"
).bindparams(
    sa.bindparam("id", type_=sa.Uuid),
    sa.bindparam("research_id", type_=sa.Uuid),
)

POINTS_EXIST_SQL = sa.text(
    "SELECT COUNT(*) FROM research_points WHERE research_id = :rid"
).bindparams(sa.bindparam("rid", type_=sa.Uuid))


def upgrade():
    op.create_table(
        "research_step_results",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "research_id",
            sa.Uuid,
            sa.ForeignKey("research.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            sa.Uuid,
            sa.ForeignKey("research_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_title", sa.Text, nullable=False),
        sa.Column("result", sa.Text, nullable=False),
        sa.Column("used_urls", sa.JSON, nullable=False),
        sa.Column("read_urls", sa.JSON, nullable=False),
        sa.Column("worker", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_research_step_results_research_id",
        "research_step_results",
        ["research_id"],
    )
    op.create_index(
        "ix_research_step_results_step_id",
        "research_step_results",
        ["step_id"],
    )

    with op.batch_alter_table("research_points") as batch_op:
        batch_op.alter_column(
            "title",
            type_=sa.Text(),
            existing_type=sa.String(500),
        )

    conn = op.get_bind()

    # ponytail: JSON/UUID coercion handles sqlite tests; postgres returns native types already.
    def _as_points(raw):
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return list(raw)
        return json.loads(raw)

    def _as_uuid(raw):
        return raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))

    # 0. SEARCH_SUCCESS represented completed research; investigation now awaits audit.
    conn.execute(
        sa.text(
            "UPDATE research_points SET status = 'AUDIT_PENDING' "
            "WHERE status = 'SEARCH_SUCCESS'"
        )
    )

    # 1. Migrate legacy research.status values to canonical set.
    for old, new in RESEARCH_STATUS_MAP.items():
        conn.execute(
            sa.text("UPDATE research SET status = :new WHERE status = :old"),
            {"new": new, "old": old},
        )

    # 2. Backfill orphan briefings (Feature 001 pre-alignment): no matching research row.
    briefings = conn.execute(
        sa.text(
            "SELECT b.id, b.theme, b.status FROM briefings b "
            "WHERE NOT EXISTS (SELECT 1 FROM research r WHERE r.id = b.id)"
        )
    ).fetchall()
    for b_id, theme, b_status in briefings:
        conn.execute(
            RESEARCH_BACKFILL_SQL,
            {
                "id": _as_uuid(b_id),
                "theme": theme,
                "status": BRIEFING_STATUS_MAP.get(b_status, "FAILED"),
            },
        )

    # 3. Backfill research_points for approved briefings.
    approved = conn.execute(
        sa.text(
            "SELECT b.id, b.points_json FROM briefings b "
            "WHERE b.status = 'approved'"
        )
    ).fetchall()
    for b_id, points_json in approved:
        # Skip briefings that already have points (re-run safety).
        existing = conn.execute(
            POINTS_EXIST_SQL,
            {"rid": _as_uuid(b_id)},
        ).scalar()
        if existing:
            continue
        points = _as_points(points_json)
        for idx, point in enumerate(points):
            conn.execute(
                POINT_BACKFILL_SQL,
                {
                    "id": uuid.uuid4(),
                    "research_id": _as_uuid(b_id),
                    "position": idx + 1,
                    "title": point.get("title"),
                    "description": point.get("description"),
                },
            )


def downgrade():
    with op.batch_alter_table("research_points") as batch_op:
        batch_op.alter_column(
            "title",
            type_=sa.String(500),
            existing_type=sa.Text(),
        )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE research_points SET status = 'SEARCH_SUCCESS' "
            "WHERE status = 'AUDIT_PENDING'"
        )
    )
    for canonical, legacy in {
        "BRIEFING": "scouting",
        "PENDING_APPROVAL": "pending_approval",
        "SCRAPER": "approved",
        "DONE": "completed",
        "FAILED": "failed",
    }.items():
        conn.execute(
            sa.text("UPDATE research SET status = :legacy WHERE status = :canonical"),
            {"canonical": canonical, "legacy": legacy},
        )
    op.drop_index(
        "ix_research_step_results_step_id", table_name="research_step_results"
    )
    op.drop_index(
        "ix_research_step_results_research_id", table_name="research_step_results"
    )
    op.drop_table("research_step_results")
