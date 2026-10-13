"""Migração 0007 em SQLite temporário, sem banco de desenvolvimento."""
import os
import tempfile
import unittest
from unittest.mock import patch
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


ALEMBIC_INI = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))


class InvestigationMigrationTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_url = f"sqlite+aiosqlite:///{self.db_path}"
        self.sync_url = f"sqlite:///{self.db_path}"
        self.cfg = Config(ALEMBIC_INI)
        self.cfg.set_main_option("script_location", "alembic")
        self.cfg.set_main_option("sqlalchemy.url", self.db_url)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_0006_to_0007_backfill_and_downgrade(self):
        research_id, point_id, orphan_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        with patch("app.core.config.settings.DATABASE_URL", self.db_url):
            command.upgrade(self.cfg, "0006")
            engine = create_engine(self.sync_url)
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO research (id, theme, status, briefing_draft, created_at, updated_at) VALUES (:id, 'legacy', 'scouting', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": research_id.hex})
                conn.execute(text("INSERT INTO research (id, theme, status, briefing_draft, created_at, updated_at) VALUES (:id, 'approval', 'pending_approval', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": point_id.hex})
                conn.execute(text("INSERT INTO research_points (id, research_id, position, title, description, dependencies, is_parallelizable, status, attempt_count, audit) VALUES (:id, :rid, 1, 'legacy point', 'desc', '[]', 0, 'SEARCH_SUCCESS', 0, '{}')"), {"id": point_id.hex, "rid": research_id.hex})
                conn.execute(text("INSERT INTO briefings (id, theme, status, version, points_json) VALUES (:id, 'orphan', 'approved', 1, :points)"), {"id": orphan_id.hex, "points": '[{"title":"Backfilled point","description":"Details"}]'})
            engine.dispose()
            command.upgrade(self.cfg, "head")

        engine = create_engine(self.sync_url)
        with engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT status FROM research WHERE id=:id"), {"id": research_id.hex}).scalar(), "BRIEFING")
            self.assertEqual(conn.execute(text("SELECT status FROM research WHERE id=:id"), {"id": point_id.hex}).scalar(), "PENDING_APPROVAL")
            self.assertEqual(conn.execute(text("SELECT status FROM research_points WHERE id=:id"), {"id": point_id.hex}).scalar(), "AUDIT_PENDING")
            rows = conn.execute(text("SELECT title, is_parallelizable, status FROM research_points WHERE research_id=:id"), {"id": orphan_id.hex}).all()
            self.assertEqual(rows, [("Backfilled point", True, "SCRAPER_PENDING")])
            self.assertEqual(conn.execute(text("SELECT status FROM research WHERE id=:id"), {"id": orphan_id.hex}).scalar(), "SCRAPER")
        indexes = {i["name"] for i in inspect(engine).get_indexes("research_step_results")}
        self.assertTrue({"ix_research_step_results_research_id", "ix_research_step_results_step_id"} <= indexes)
        engine.dispose()

        with patch("app.core.config.settings.DATABASE_URL", self.db_url):
            command.downgrade(self.cfg, "0006")
        engine = create_engine(self.sync_url)
        with engine.connect() as conn:
            self.assertNotIn("research_step_results", inspect(engine).get_table_names())
            self.assertEqual(conn.execute(text("SELECT status FROM research_points WHERE id=:id"), {"id": point_id.hex}).scalar(), "SEARCH_SUCCESS")
            self.assertEqual(conn.execute(text("SELECT status FROM research WHERE id=:id"), {"id": research_id.hex}).scalar(), "scouting")
            self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM research_points WHERE research_id=:id"), {"id": orphan_id.hex}).scalar(), 1)
        engine.dispose()
        with patch("app.core.config.settings.DATABASE_URL", self.db_url):
            command.upgrade(self.cfg, "head")
        engine = create_engine(self.sync_url)
        with engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT status FROM research_points WHERE id=:id"), {"id": point_id.hex}).scalar(), "AUDIT_PENDING")
            rows = conn.execute(text("SELECT title, status FROM research_points WHERE research_id=:id"), {"id": orphan_id.hex}).all()
            self.assertEqual(len(rows), 1)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
