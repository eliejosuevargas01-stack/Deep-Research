"""add jina_base_url to app_settings for custom Cloudflare Worker proxy

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "app_settings", sa.Column("jina_base_url", sa.String(2048), nullable=True)
    )


def downgrade():
    op.drop_column("app_settings", "jina_base_url")