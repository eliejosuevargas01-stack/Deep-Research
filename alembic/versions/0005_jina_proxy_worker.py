"""add jina_proxy_url and jina_proxy_timeout_seconds to app_settings

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "app_settings", sa.Column("jina_proxy_url", sa.String(2048), nullable=True)
    )
    op.add_column(
        "app_settings",
        sa.Column("jina_proxy_timeout_seconds", sa.Integer, nullable=True, default=20),
    )


def downgrade():
    op.drop_column("app_settings", "jina_proxy_timeout_seconds")
    op.drop_column("app_settings", "jina_proxy_url")