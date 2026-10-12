"""T022: storage assíncrono Tx1/CAS Tx2 com SQLite isolado (nunca DB real)."""

import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.briefing.domain import (
    BriefingPoint,
    BriefingStatus,
    approve_briefing,
    complete_briefing,
    edit_briefing,
    new_briefing,
)
from app.briefing.storage import (
    BriefingVersionConflictError,
    create_generating_briefing,
    get_briefing,
    get_briefing_versions,
    save_briefing_transition,
)
from app.models.domain_models import Base


def _pts(n=3):
    return tuple(BriefingPoint(f"t{i}", f"d{i}") for i in range(n))


class TestStorageCycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_full_cycle_generating_draft_edit_approved(self):
        async with self.Session() as db:
            gen = new_briefing("tema valido para ciclo")
            await create_generating_briefing(db, gen)
            got = await get_briefing(db, gen.id)
            assert got is not None
            self.assertEqual(got, gen)
            self.assertEqual(got.status, BriefingStatus.GENERATING)

            draft = complete_briefing(gen, _pts(3))
            await save_briefing_transition(db, gen, draft)
            b2 = await get_briefing(db, gen.id)
            assert b2 is not None
            self.assertEqual(b2.version, 2)
            hist = await get_briefing_versions(db, gen.id)
            self.assertEqual([v.version for v in hist], [2])

            edited = edit_briefing(draft, _pts(4))
            await save_briefing_transition(db, draft, edited)
            approved = approve_briefing(edited, datetime.now(timezone.utc))
            await save_briefing_transition(db, edited, approved)

            final = await get_briefing(db, gen.id)
            assert final is not None
            self.assertEqual(final.status, BriefingStatus.APPROVED)
            self.assertEqual(final.version, 4)
            versions = [v.version for v in await get_briefing_versions(db, gen.id)]
            self.assertEqual(versions, [2, 3, 4])
            self.assertEqual(versions, sorted(versions))

    async def test_get_missing_returns_none_and_history_empty(self):
        async with self.Session() as db:
            self.assertIsNone(await get_briefing(db, uuid.uuid4()))
            self.assertEqual(await get_briefing_versions(db, uuid.uuid4()), [])

    async def test_points_json_only_clean_points_and_uuid_preserved(self):
        async with self.Session() as db:
            gen = new_briefing("tema valido uuid")
            await create_generating_briefing(db, gen)
            draft = complete_briefing(gen, _pts(3))
            await save_briefing_transition(db, gen, draft)
            got = await get_briefing(db, gen.id)
            assert got is not None
            self.assertEqual(got.id, gen.id)
            self.assertEqual(got.points, _pts(3))
            hist = await get_briefing_versions(db, gen.id)
            blob = list(hist[0].points_json)
            self.assertEqual(
                blob, [{"title": f"t{i}", "description": f"d{i}"} for i in range(3)]
            )
            for row in blob:
                self.assertEqual(set(row.keys()), {"title", "description"})

    async def test_stale_cas_raises_and_preserves_state(self):
        async with self.Session() as db:
            gen = new_briefing("tema valido conflito")
            await create_generating_briefing(db, gen)
            draft = complete_briefing(gen, _pts(3))
            await save_briefing_transition(db, gen, draft)
            edited = edit_briefing(draft, _pts(4))
            await save_briefing_transition(db, draft, edited)
            # stale: tenta transitar a partir de `draft` (v2) quando atual é v3
            stale = edit_briefing(draft, _pts(5))
            with self.assertRaises(BriefingVersionConflictError):
                await save_briefing_transition(db, draft, stale)
            kept = await get_briefing(db, gen.id)
            assert kept is not None
            self.assertEqual(kept.version, 3)
            self.assertEqual(kept.points, _pts(4))
            self.assertEqual(
                [v.version for v in await get_briefing_versions(db, gen.id)], [2, 3]
            )


if __name__ == "__main__":
    unittest.main()
