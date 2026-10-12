"""Isolated unit tests for the 0006 briefing storage migration.

Uses a temporary SQLite database so the dev/production DB is never touched.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config


ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "..", "alembic.ini"
)


def _make_config(db_url: str) -> Config:
    cfg = Config(file_=os.path.abspath(ALEMBIC_INI))
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _fresh_sqlite_urls() -> tuple[str, str, str]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    async_url = f"sqlite+aiosqlite:///{path}"
    sync_url = f"sqlite:///{path}"
    return path, async_url, sync_url


class BriefingMigrationTests(unittest.TestCase):
    def setUp(self):
        self.db_path, self.async_url, self.sync_url = _fresh_sqlite_urls()
        self.cfg = _make_config(self.async_url)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except OSError:
                pass

    def test_upgrade_and_downgrade_reversible(self):
        with patch("app.core.config.settings.DATABASE_URL", self.async_url):
            command.upgrade(self.cfg, "head")
            command.downgrade(self.cfg, "0005")

    def test_tables_present_after_upgrade(self):
        with patch("app.core.config.settings.DATABASE_URL", self.async_url):
            command.upgrade(self.cfg, "head")

        from sqlalchemy import create_engine, inspect

        engine = create_engine(self.sync_url)
        insp = inspect(engine)
        tables = sorted(insp.get_table_names())
        self.assertIn("briefings", tables)
        self.assertIn("briefing_versions", tables)

        cols = {c["name"] for c in insp.get_columns("briefing_versions")}
        self.assertIn("briefing_id", cols)

        uniques = {
            constraint["name"]
            for constraint in insp.get_unique_constraints("briefing_versions")
        }
        self.assertIn("uq_briefing_version", uniques)

        indexes = {
            index["name"] for index in insp.get_indexes("briefing_versions")
        }
        self.assertIn("ix_briefing_versions_briefing_id_version", indexes)

        engine.dispose()

    def test_tables_absent_after_downgrade(self):
        with patch("app.core.config.settings.DATABASE_URL", self.async_url):
            command.upgrade(self.cfg, "head")
            command.downgrade(self.cfg, "0005")

        from sqlalchemy import create_engine, inspect

        engine = create_engine(self.sync_url)
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        self.assertNotIn("briefings", tables)
        self.assertNotIn("briefing_versions", tables)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
