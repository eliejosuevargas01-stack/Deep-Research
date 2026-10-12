"""QA mantido F-test-01..03: conteúdo, histórico e cancelamento persistidos."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.briefing.domain import BriefingPoint, BriefingStatus
from app.briefing.service import orchestrate_persisted_briefing
from app.briefing.storage import get_briefing, get_briefing_versions
from app.models.domain_models import Base, BriefingRecord, BriefingVersion


POINTS = [
    {"title": "Custos e benefícios", "description": "Comparar custos sem antecipar conclusão."},
    {"title": "Riscos técnicos", "description": "Investigar limites, falhas e recuperação."},
    {"title": "Impacto social", "description": "Examinar efeitos distintos por público."},
]
SAFE_ERROR = "Geração de briefing indisponível"
CANARY = "QA_PRIVATE_PAYLOAD_DO_NOT_PERSIST"


class TestPersistedOrchestrationQA(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.addAsyncCleanup(self.engine.dispose)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.initial = []

        async def search(theme):
            # Tx1 já comitada: identidade e ausência de histórico antes do I/O.
            async with self.session_factory() as session:
                records = list((await session.scalars(select(BriefingRecord))).all())
                generating = [record for record in records if record.status == "generating"]
                self.assertEqual(len(generating), 1)
                initial = await get_briefing(session, generating[0].id)
                assert initial is not None
                self.assertEqual(initial.theme, theme)
                self.assertEqual(initial.version, 1)
                self.assertEqual(initial.points, ())
                self.assertIsNone(initial.error)
                self.assertEqual(await get_briefing_versions(session, initial.id), [])
                self.initial.append(initial)
            return [{"title": "Fonte", "url": "https://example.invalid", "description": "Resumo"}]

        self.serp = AsyncMock()
        self.serp.search.side_effect = search

    async def run_flow(self, llm):
        return await orchestrate_persisted_briefing(
            self.session_factory,
            "Tema válido para QA persistido",
            serp_client=self.serp,
            llm_complete=llm,
            prompt_loader=lambda: "Prompt local de QA",
            llm_attempts=4,
        )

    async def assert_terminal(self, result, status, points, error):
        self.assertEqual(result.id, self.initial[-1].id)
        self.assertEqual(result.status, status)
        self.assertEqual(result.version, 2)
        self.assertEqual(result.error, error)
        self.assertEqual(result.points, tuple(BriefingPoint(**point) for point in points))
        async with self.session_factory() as session:
            current = await get_briefing(session, result.id)
            self.assertEqual(current, result)
            record = await session.get(BriefingRecord, result.id)
            assert record is not None
            self.assertEqual(record.points_json, points)
            history = await get_briefing_versions(session, result.id)
            self.assertEqual(len(history), 1)
            row = history[0]
            self.assertEqual(row.briefing_id, result.id)
            self.assertEqual(row.version, 2)
            self.assertEqual(row.status, status.value)
            self.assertEqual(row.points_json, points)
            self.assertEqual(row.error, error)
            self.assertEqual(row.error, record.error)
            self.assertIsNone(row.approved_at)

    async def test_success_preserves_exact_points_in_return_current_and_history(self):
        """F-test-01: títulos, descrições e ordem, não só contagem."""
        llm = AsyncMock(return_value=json.dumps(POINTS, ensure_ascii=False))
        result = await self.run_flow(llm)
        await self.assert_terminal(result, BriefingStatus.DRAFT, POINTS, None)
        self.serp.search.assert_awaited_once()
        llm.assert_awaited_once()

    async def test_invalid_content_retry_preserves_exact_recovered_points(self):
        """F-test-01: JSON válido com um ponto inválido não deixa parcial."""
        invalid = json.dumps([{"title": CANARY, "description": "Inválido por quantidade"}])
        llm = AsyncMock(side_effect=[invalid, json.dumps(POINTS, ensure_ascii=False)])
        result = await self.run_flow(llm)
        await self.assert_terminal(result, BriefingStatus.DRAFT, POINTS, None)
        self.serp.search.assert_awaited_once()
        self.assertEqual(llm.await_count, 2)
        self.assertEqual(llm.await_args_list[0], llm.await_args_list[1])

    async def history_snapshot(self):
        async with self.session_factory() as session:
            rows = list((await session.scalars(select(BriefingVersion))).all())
            return {
                row.id: (row.briefing_id, row.version, row.status, row.points_json,
                         row.error, row.approved_at, row.created_at)
                for row in rows
            }

    async def assert_exhaustion_appends_safe_history(self, invalid):
        # Histórico preexistente deve permanecer byte-equivalente em seus campos.
        seed = await self.run_flow(AsyncMock(return_value=json.dumps(POINTS)))
        before = await self.history_snapshot()
        self.assertEqual(len(before), 1)
        attempts = []

        async def llm(system, user):
            attempts.append((system, user))
            async with self.session_factory() as session:
                pending = await get_briefing(session, self.initial[-1].id)
                assert pending is not None
                self.assertEqual(pending.status, BriefingStatus.GENERATING)
                self.assertEqual(pending.version, 1)
                self.assertEqual(pending.points, ())
                self.assertEqual(await get_briefing_versions(session, pending.id), [])
            self.assertEqual(await self.history_snapshot(), before)
            return invalid

        self.serp.search.reset_mock()
        result = await self.run_flow(llm)
        self.assertNotEqual(result.id, seed.id)
        await self.assert_terminal(result, BriefingStatus.FAILED, [], SAFE_ERROR)
        self.serp.search.assert_awaited_once()
        self.assertEqual(len(attempts), 4)
        self.assertTrue(all(attempt == attempts[0] for attempt in attempts))
        after = await self.history_snapshot()
        self.assertEqual(len(after), 2)
        self.assertEqual({key: after[key] for key in before}, before)
        self.assertEqual(len(after.keys() - before.keys()), 1)
        self.assertNotIn(CANARY, repr(after))

    async def test_four_domain_invalid_attempts_append_failed_safe_history(self):
        """F-test-02: exaustão por conteúdo parseável inválido."""
        await self.assert_exhaustion_appends_safe_history(
            json.dumps([{"title": CANARY, "description": "Somente um ponto"}])
        )

    async def test_external_cancellation_after_llm_entry_commits_emergency_history(self):
        """F-test-03: Event confirma entrada; cancelamento propaga após emergência."""
        entered = asyncio.Event()
        blocked = asyncio.Event()

        async def wait_llm(system, user):
            entered.set()
            await blocked.wait()
            self.fail("LLM bloqueado não deve completar após cancelamento")

        llm = AsyncMock(side_effect=wait_llm)
        task = asyncio.create_task(self.run_flow(llm))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            self.assertFalse(task.done())
            self.assertFalse(blocked.is_set())
            self.assertTrue(task.cancel())
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(task.cancelled())
            # Outra sessão observa commit da transação de emergência.
            async with self.session_factory() as session:
                records = list((await session.scalars(select(BriefingRecord))).all())
                self.assertEqual(len(records), 1)
                current = await get_briefing(session, records[0].id)
            await self.assert_terminal(
                current, BriefingStatus.FAILED, [], "Processamento abortado ou cancelado"
            )
            self.serp.search.assert_awaited_once()
            llm.assert_awaited_once()
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
