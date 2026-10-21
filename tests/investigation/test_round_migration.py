"""RED migration tests for investigation_round + investigation_merges (T008/T011).

Mirrors tests/investigation/test_investigation_migration.py: SQLite temp file,
Alembic programmatic upgrade/downgrade, no real DB.

The migration 0008 does NOT exist yet — tests fail (RED).
"""
import os
import tempfile
import unittest
from unittest.mock import patch
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


ALEMBIC_INI = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
)


class InvestigationRoundMigrationTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_url = "sqlite+aiosqlite:///" + self.db_path
        self.sync_url = "sqlite:///" + self.db_path
        self.cfg = Config(ALEMBIC_INI)
        self.cfg.set_main_option("script_location", "alembic")
        self.cfg.set_main_option("sqlalchemy.url", self.sync_url)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    # ------------------------------------------------------------------
    # 1. Clean upgrade 0007 -> 0008: new columns / index / table created
    # ------------------------------------------------------------------
    def test_upgrade_0007_to_0008_creates_columns_index_and_merges_table(self):
        # Resolve current head dynamically from the graph at runtime
        self.assertEqual(self.cfg.get_main_option("sqlalchemy.url"), self.sync_url)
        with patch(
            "app.core.config.settings.DATABASE_URL", self.db_url
        ):
            command.upgrade(self.cfg, "0007")

        engine = create_engine(self.sync_url)

        # Seed one research + point so we can confirm nullable cols on rows.
        research_id, point_id = uuid.uuid4(), uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO research (id, theme, status, briefing_draft, "
                    "created_at, updated_at) VALUES (:id, 'scraper', 'BRIEFING', '{}', "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": str(research_id)},
            )
            conn.execute(
                text(
                    "INSERT INTO research_points (id, research_id, position, title, "
                    "description, dependencies, is_parallelizable, status, "
                    "attempt_count, audit) VALUES (:id, :rid, 1, 't', 'd', '[]', 0, "
                    "'SCRAPER_PENDING', 0, '{}')"
                ),
                {"id": str(point_id), "rid": str(research_id)},
            )

        engine.dispose()

        with patch(
            "app.core.config.settings.DATABASE_URL", self.db_url
        ):
            command.upgrade(self.cfg, "head")

        engine = create_engine(self.sync_url)

        # research_points.investigation_round
        rp_cols = {
            c["name"]: c for c in inspect(engine).get_columns("research_points")
        }
        self.assertIn("investigation_round", rp_cols)

        # research_step_results.round
        rsr_cols = {
            c["name"]: c for c in inspect(engine).get_columns("research_step_results")
        }
        self.assertIn("round", rsr_cols)

        # investigation_merges table exists with expected columns
        tables = inspect(engine).get_table_names()
        self.assertIn("investigation_merges", tables)
        merge_cols = {c["name"] for c in inspect(engine).get_columns("investigation_merges")}
        for expected in ("id", "research_id", "step_id", "round", "content", "created_at"):
            self.assertIn(expected, merge_cols)

        # UNIQUE (research_id, step_id, round) -> constraint present
        uniq = {
            c["name"]
            for c in inspect(engine).get_unique_constraints("investigation_merges")
        }
        self.assertEqual(len(uniq), 1)

        # Historical NULL rows preserved without error
        with engine.connect() as conn:
            val = conn.execute(
                text("SELECT investigation_round FROM research_points WHERE id=:id"),
                {"id": str(point_id)},
            ).scalar()
            self.assertIsNone(val)

        engine.dispose()

    # ------------------------------------------------------------------
    # 2. Downgrade 0008 -> 0007 removes new columns/tabela
    # ------------------------------------------------------------------
    def test_downgrade_removes_new_columns_and_merges_table(self):
        with patch(
            "app.core.config.settings.DATABASE_URL", self.db_url
        ):
            command.upgrade(self.cfg, "head")
            command.downgrade(self.cfg, "0007")

        engine = create_engine(self.sync_url)
        rp_cols = {c["name"] for c in inspect(engine).get_columns("research_points")}
        rsr_cols = {c["name"] for c in inspect(engine).get_columns("research_step_results")}
        tables = inspect(engine).get_table_names()

        self.assertNotIn("investigation_round", rp_cols)
        self.assertNotIn("round", rsr_cols)
        self.assertNotIn("investigation_merges", tables)
        engine.dispose()

    # ------------------------------------------------------------------
    # 3. Re-upgrade after downgrade: structure restored
    # ------------------------------------------------------------------
    def test_reupgrade_after_downgrade_restores_structure(self):
        with patch(
            "app.core.config.settings.DATABASE_URL", self.db_url
        ):
            command.upgrade(self.cfg, "head")
            command.downgrade(self.cfg, "0007")
            command.upgrade(self.cfg, "head")

        engine = create_engine(self.sync_url)
        rp_cols = {c["name"] for c in inspect(engine).get_columns("research_points")}
        rsr_cols = {c["name"] for c in inspect(engine).get_columns("research_step_results")}
        tables = inspect(engine).get_table_names()

        self.assertIn("investigation_round", rp_cols)
        self.assertIn("round", rsr_cols)
        self.assertIn("investigation_merges", tables)
        engine.dispose()

    # ------------------------------------------------------------------
    # 4. PostgreSQL ephemeral: clean, populated, downgrade, reupgrade (T012)
    # ------------------------------------------------------------------
    def test_postgres_ephemeral_clean_and_populated_lifecycle(self):
        import shutil, subprocess, asyncio
        from sqlalchemy.ext.asyncio import create_async_engine

        if not shutil.which("docker"):
            self.skipTest("Docker is not available for ephemeral PostgreSQL test")

        port = 55432
        container_name = f"ephemeral_pg_0008_{os.getpid()}"
        password = uuid.uuid4().hex

        run_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:5432",
            "-e", f"POSTGRES_PASSWORD={password}",
            "postgres:16-alpine",
        ]
        try:
            subprocess.run(run_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            self.skipTest("Failed to spawn docker ephemeral container")

        try:
            # Wait for readiness
            ready = False
            for _ in range(40):
                res = subprocess.run(
                    ["docker", "exec", "-e", f"PGPASSWORD={password}", container_name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                if res.returncode == 0:
                    ready = True
                    break
                import time
                time.sleep(0.5)

            if not ready:
                self.skipTest("Ephemeral PostgreSQL container failed readiness probe")

            # Create clean and populated test databases
            subprocess.run(
                ["docker", "exec", "-e", f"PGPASSWORD={password}", container_name, "psql", "-h", "127.0.0.1", "-U", "postgres", "-c", "CREATE DATABASE clean_migration_test;"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["docker", "exec", "-e", f"PGPASSWORD={password}", container_name, "psql", "-h", "127.0.0.1", "-U", "postgres", "-c", "CREATE DATABASE populated_migration_test;"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

            # 4a. Clean upgrade test
            clean_url = f"postgresql+asyncpg://postgres:{password}@localhost:{port}/clean_migration_test"
            clean_cfg = Config(ALEMBIC_INI)
            clean_cfg.set_main_option("script_location", "alembic")
            clean_cfg.set_main_option("sqlalchemy.url", clean_url)

            with patch("app.core.config.settings.DATABASE_URL", clean_url):
                command.upgrade(clean_cfg, "head")

            async def _check_clean():
                engine = create_async_engine(clean_url)
                async with engine.connect() as conn:
                    tables = await conn.run_sync(lambda sc: inspect(sc).get_table_names())
                    self.assertIn("investigation_merges", tables)
                    self.assertIn("research_step_results", tables)
                    self.assertIn("research_points", tables)

                    rp_cols = await conn.run_sync(lambda sc: {c["name"]: c for c in inspect(sc).get_columns("research_points")})
                    self.assertIn("investigation_round", rp_cols)
                    self.assertTrue(rp_cols["investigation_round"]["nullable"])

                    rsr_cols = await conn.run_sync(lambda sc: {c["name"]: c for c in inspect(sc).get_columns("research_step_results")})
                    self.assertIn("round", rsr_cols)
                    self.assertTrue(rsr_cols["round"]["nullable"])

                    m_cols = await conn.run_sync(lambda sc: {c["name"] for c in inspect(sc).get_columns("investigation_merges")})
                    for exp in ("id", "research_id", "step_id", "round", "content", "created_at"):
                        self.assertIn(exp, m_cols)

                    m_uniques = await conn.run_sync(lambda sc: inspect(sc).get_unique_constraints("investigation_merges"))
                    self.assertTrue(any(set(u["column_names"]) == {"research_id", "step_id", "round"} for u in m_uniques))

                    rsr_uniques = await conn.run_sync(lambda sc: inspect(sc).get_unique_constraints("research_step_results"))
                    self.assertTrue(any(set(u["column_names"]) == {"research_id", "step_id", "round", "worker"} for u in rsr_uniques))

                rid, pid = uuid.uuid4(), uuid.uuid4()
                async with engine.begin() as conn:
                    await conn.execute(text("INSERT INTO research (id, theme, status, briefing_draft, created_at, updated_at) VALUES (:id, 'clean test', 'SCRAPER', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": rid})
                    await conn.execute(text("INSERT INTO research_points (id, research_id, position, title, description, dependencies, is_parallelizable, status, attempt_count, audit, investigation_round) VALUES (:id, :rid, 1, 'pt 1', 'desc', '[]', true, 'AUDIT_PENDING', 0, '{}', 1)"), {"id": pid, "rid": rid})
                    await conn.execute(text("INSERT INTO investigation_merges (id, research_id, step_id, round, content, created_at) VALUES (:id, :rid, :sid, 1, '{\"test\": true}', CURRENT_TIMESTAMP)"), {"id": uuid.uuid4(), "rid": rid, "sid": pid})

                with self.assertRaises(Exception):
                    async with engine.begin() as conn:
                        await conn.execute(text("INSERT INTO investigation_merges (id, research_id, step_id, round, content, created_at) VALUES (:id, :rid, :sid, 1, '{\"dup\": true}', CURRENT_TIMESTAMP)"), {"id": uuid.uuid4(), "rid": rid, "sid": pid})

                await engine.dispose()

            asyncio.run(_check_clean())

            # 4b. Populated upgrade, downgrade and re-upgrade test
            pop_url = f"postgresql+asyncpg://postgres:{password}@localhost:{port}/populated_migration_test"
            pop_cfg = Config(ALEMBIC_INI)
            pop_cfg.set_main_option("script_location", "alembic")
            pop_cfg.set_main_option("sqlalchemy.url", pop_url)

            with patch("app.core.config.settings.DATABASE_URL", pop_url):
                command.upgrade(pop_cfg, "0007")

            rid_done = uuid.uuid4()
            pid_done = uuid.uuid4()
            srid_legacy = uuid.uuid4()
            rep_id = uuid.uuid4()
            ev_id = uuid.uuid4()

            async def _seed_and_test_populated():
                engine = create_async_engine(pop_url)
                async with engine.begin() as conn:
                    await conn.execute(text("INSERT INTO research (id, theme, status, briefing_draft, created_at, updated_at) VALUES (:id, 'done theme', 'DONE', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": rid_done})
                    await conn.execute(text("INSERT INTO research_points (id, research_id, position, title, description, dependencies, is_parallelizable, status, attempt_count, audit) VALUES (:id, :rid, 1, 'done pt', 'desc', '[]', true, 'AUDIT_PENDING', 2, '{}')"), {"id": pid_done, "rid": rid_done})
                    await conn.execute(text("INSERT INTO research_step_results (id, research_id, step_id, step_title, result, used_urls, read_urls, worker, status, created_at) VALUES (:id, :rid, :sid, 'done pt', 'legacy analysis text', '[]', '[]', 'historian', 'AUDIT_PENDING', CURRENT_TIMESTAMP)"), {"id": srid_legacy, "rid": rid_done, "sid": pid_done})
                    await conn.execute(text("INSERT INTO reports (id, research_id, content_markdown, citation_metrics, audit_findings, generated_at) VALUES (:id, :rid, '# Done Report', '{}', '{}', CURRENT_TIMESTAMP)"), {"id": rep_id, "rid": rid_done})
                    await conn.execute(text("INSERT INTO evidences (id, research_point_id, persona, source_url, source_title, excerpt, claim, analysis, accessed_at, version) VALUES (:id, :pid, 'historian', 'https://ex.com/p', 'T', 'Exc', 'Cl', 'analysis text', CURRENT_TIMESTAMP, 1)"), {"id": ev_id, "pid": pid_done})

                async with engine.connect() as conn:
                    counts = {
                        "res": (await conn.execute(text("SELECT count(*) FROM research"))).scalar(),
                        "pt": (await conn.execute(text("SELECT count(*) FROM research_points"))).scalar(),
                        "rsr": (await conn.execute(text("SELECT count(*) FROM research_step_results"))).scalar(),
                        "rep": (await conn.execute(text("SELECT count(*) FROM reports"))).scalar(),
                        "ev": (await conn.execute(text("SELECT count(*) FROM evidences"))).scalar(),
                    }
                await engine.dispose()
                return counts

            counts = asyncio.run(_seed_and_test_populated())

            # Upgrade to head (0008)
            with patch("app.core.config.settings.DATABASE_URL", pop_url):
                command.upgrade(pop_cfg, "head")

            async def _verify_populated_upgrade():
                engine = create_async_engine(pop_url)
                async with engine.connect() as conn:
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM research"))).scalar(), counts["res"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM research_points"))).scalar(), counts["pt"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM research_step_results"))).scalar(), counts["rsr"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM reports"))).scalar(), counts["rep"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM evidences"))).scalar(), counts["ev"])

                    row = (await conn.execute(text("SELECT round, result FROM research_step_results WHERE id = :id"), {"id": srid_legacy})).fetchone()
                    self.assertIsNotNone(row)
                    assert row is not None
                    self.assertIsNone(row[0])
                    self.assertEqual(row[1], "legacy analysis text")

                    pt_row = (await conn.execute(text("SELECT investigation_round, status FROM research_points WHERE id = :id"), {"id": pid_done})).fetchone()
                    self.assertIsNotNone(pt_row)
                    assert pt_row is not None
                    self.assertIsNone(pt_row[0])
                    self.assertEqual(pt_row[1], "AUDIT_PENDING")
                await engine.dispose()

            asyncio.run(_verify_populated_upgrade())

            # Downgrade to 0007
            with patch("app.core.config.settings.DATABASE_URL", pop_url):
                command.downgrade(pop_cfg, "0007")

            async def _verify_downgrade():
                engine = create_async_engine(pop_url)
                async with engine.connect() as conn:
                    tables = await conn.run_sync(lambda sc: inspect(sc).get_table_names())
                    self.assertNotIn("investigation_merges", tables)
                    rp_cols = await conn.run_sync(lambda sc: {c["name"] for c in inspect(sc).get_columns("research_points")})
                    self.assertNotIn("investigation_round", rp_cols)
                    rsr_cols = await conn.run_sync(lambda sc: {c["name"] for c in inspect(sc).get_columns("research_step_results")})
                    self.assertNotIn("round", rsr_cols)

                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM research"))).scalar(), counts["res"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM research_points"))).scalar(), counts["pt"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM research_step_results"))).scalar(), counts["rsr"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM reports"))).scalar(), counts["rep"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM evidences"))).scalar(), counts["ev"])
                await engine.dispose()

            asyncio.run(_verify_downgrade())

            # Re-upgrade to head
            with patch("app.core.config.settings.DATABASE_URL", pop_url):
                command.upgrade(pop_cfg, "head")

            async def _verify_reupgrade():
                engine = create_async_engine(pop_url)
                async with engine.connect() as conn:
                    tables = await conn.run_sync(lambda sc: inspect(sc).get_table_names())
                    self.assertIn("investigation_merges", tables)
                    rp_cols = await conn.run_sync(lambda sc: {c["name"] for c in inspect(sc).get_columns("research_points")})
                    self.assertIn("investigation_round", rp_cols)
                    rsr_cols = await conn.run_sync(lambda sc: {c["name"] for c in inspect(sc).get_columns("research_step_results")})
                    self.assertIn("round", rsr_cols)

                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM research"))).scalar(), counts["res"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM research_points"))).scalar(), counts["pt"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM research_step_results"))).scalar(), counts["rsr"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM reports"))).scalar(), counts["rep"])
                    self.assertEqual((await conn.execute(text("SELECT count(*) FROM evidences"))).scalar(), counts["ev"])
                await engine.dispose()

            asyncio.run(_verify_reupgrade())

        finally:
            subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()
