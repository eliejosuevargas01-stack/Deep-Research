"""add callback_url and openai_base_url to app_settings

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("app_settings", sa.Column("callback_url", sa.String(2048), nullable=True))
    op.add_column("app_settings", sa.Column("openai_base_url", sa.String(2048), nullable=True))


def downgrade():
    op.drop_column("app_settings", "openai_base_url")
    op.drop_column("app_settings", "callback_url")
