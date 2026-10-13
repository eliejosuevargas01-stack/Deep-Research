"""Sprint 6 QA: real domain/storage, isolated SQLite, no provider or API."""

import copy
import json
import unittest
from datetime import datetime
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.briefing.domain import (
    InvalidTransition, approve_briefing, complete_briefing, edit_briefing,
    new_briefing, reopen_briefing,
)
from app.briefing.storage import (
    BriefingVersionConflictError, create_generating_briefing, get_briefing,
    get_briefing_versions, points_to_json, save_briefing_transition,
)
from app.models.domain_models import Base, BriefingRecord, BriefingVersion, Research


def points(label):
    return [{"title": f"{label} {i}", "description": f"Descrição {label} {i}"}
            for i in range(3)]


def history_snapshot(rows):
    return [copy.deepcopy({column.name: getattr(row, column.name)
                           for column in BriefingVersion.__table__.columns})
            for row in rows]


class TestBriefingStorageQA(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.addAsyncCleanup(self.engine.dispose)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def persist(self, previous, current):
        async with self.Session() as db:
            self.assertEqual(await save_briefing_transition(db, previous, current), current)
            self.assertFalse(db.in_transaction())

    async def read(self, briefing_id):
        async with self.Session() as db:
            return (await get_briefing(db, briefing_id),
                    history_snapshot(await get_briefing_versions(db, briefing_id)))

    async def seed(self):
        generating = new_briefing("Tema QA persistência")
        async with self.Session() as db:
            self.assertEqual(await create_generating_briefing(db, generating), generating)
            self.assertFalse(db.in_transaction())
        self.assertEqual(await self.read(generating.id), (generating, []))
        draft = complete_briefing(generating, points("original"))
        await self.persist(generating, draft)
        return draft

    async def test_saved_edit_approve_reopen_history_is_immutable(self):
        draft = await self.seed()
        edited_points = list(reversed(points("editado")))
        edited = edit_briefing(draft, edited_points)
        # SQLite preserves wall time, not timezone; PostgreSQL is outside this QA.
        approved = approve_briefing(edited, datetime(2026, 10, 11, 12, 30, 45))
        with self.assertRaisesRegex(InvalidTransition, "^Briefing aprovado não pode ser reaberto$"):
            reopen_briefing(approved)
        previous = draft
        _, old_history = await self.read(draft.id)
        for current in (edited, approved):
            await self.persist(previous, current)
            saved, history = await self.read(draft.id)
            self.assertEqual(saved, current)
            self.assertIsInstance(saved.id, UUID)
            self.assertEqual(saved.id, draft.id)
            self.assertEqual(saved.version, previous.version + 1)
            self.assertEqual(history[:-1], old_history)
            self.assertEqual([row["version"] for row in history],
                             list(range(2, current.version + 1)))
            last = history[-1]
            self.assertEqual(last["briefing_id"], draft.id)
            self.assertEqual(last["status"], current.status.value)
            self.assertEqual(last["points_json"], points_to_json(current.points))
            self.assertEqual(last["approved_at"], current.approved_at)
            self.assertIsNone(last["error"])
            previous, old_history = current, history
        self.assertEqual(old_history[0]["points_json"], points("original"))
        self.assertEqual(old_history[1]["points_json"], edited_points)
        self.assertEqual(old_history[2]["approved_at"], approved.approved_at)
        self.assertEqual(saved.approved_at, approved.approved_at)
        with self.assertRaises(InvalidTransition):
            edit_briefing(approved, points("proibido"))
        self.assertEqual(await self.read(draft.id), (approved, old_history))

    async def test_stale_cas_keeps_exact_winner_and_history(self):
        draft = await self.seed()
        winner = edit_briefing(draft, points("vencedor"))
        loser = edit_briefing(draft, points("perdedor"))
        await self.persist(draft, winner)
        expected = await self.read(draft.id)
        async with self.Session() as db:
            with self.assertRaises(BriefingVersionConflictError):
                await save_briefing_transition(db, draft, loser)
            self.assertFalse(db.in_transaction())
        self.assertEqual(await self.read(draft.id), expected)
        self.assertEqual(expected[0], winner)
        self.assertEqual(expected[1][-1]["points_json"], points("vencedor"))

    async def test_history_insert_failure_rolls_back_update_with_caller_rollback(self):
        draft = await self.seed()
        expected = await self.read(draft.id)
        edited = edit_briefing(draft, points("não salvo"))
        observed = []

        def fail_insert(mapper, connection, target):
            # Real UPDATE already executed in same transaction before history flush.
            row = connection.execute(BriefingRecord.__table__.select().where(
                BriefingRecord.id == draft.id)).mappings().one()
            observed.append((row["version"], row["points_json"], target.version))
            raise RuntimeError("injected history INSERT failure")

        event.listen(BriefingVersion, "before_insert", fail_insert)
        try:
            async with self.Session() as db:
                try:
                    with self.assertRaisesRegex(RuntimeError, "injected history INSERT failure"):
                        await save_briefing_transition(db, draft, edited)
                finally:
                    # Caller owns recovery after infrastructure/flush failure.
                    await db.rollback()
                self.assertFalse(db.in_transaction())
        finally:
            event.remove(BriefingVersion, "before_insert", fail_insert)
        self.assertEqual(observed, [(3, points("não salvo"), 3)])
        self.assertEqual(await self.read(draft.id), expected)
        self.assertFalse(event.contains(BriefingVersion, "before_insert", fail_insert))

    async def test_raw_canary_excluded_from_current_and_history_serialization(self):
        draft = await self.seed()
        canary = "RAW_QA_CANARY_NOT_A_SECRET"
        supplied = [dict(point, raw_llm=canary, prompt=canary, api_key=canary)
                    for point in points("limpo")]
        self.assertTrue(all(point["raw_llm"] == canary for point in supplied))
        edited = edit_briefing(draft, supplied)
        await self.persist(draft, edited)
        async with self.Session() as db:
            record = await db.get(BriefingRecord, draft.id)
            rows = await get_briefing_versions(db, draft.id)
            payload = [{column.name: getattr(record, column.name)
                        for column in BriefingRecord.__table__.columns}]
            payload.extend(history_snapshot(rows))
            self.assertNotIn(canary, json.dumps(payload, default=str, ensure_ascii=False))
            self.assertEqual(record.points_json, points("limpo"))
            self.assertEqual(rows[-1].points_json, points("limpo"))
            for row in payload:
                for point in row["points_json"]:
                    self.assertEqual(set(point), {"title", "description"})
        self.assertEqual((await self.read(draft.id))[0], edited)


if __name__ == "__main__":
    unittest.main()
