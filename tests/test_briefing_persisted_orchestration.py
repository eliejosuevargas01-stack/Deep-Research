"""Testes da orquestração persistida (T024). Tx1 curta, I/O fora de Tx, CAS Tx2 e política de órfãos."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.briefing.domain import BriefingStatus
from app.briefing.service import orchestrate_persisted_briefing
from app.briefing.storage import get_briefing, get_briefing_versions
from app.models.domain_models import Base


class TestPersistedOrchestration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:", echo=False
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False
        )

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_full_success_persisted_flow(self):
        serp = AsyncMock()
        serp.search.return_value = [{"title": "R1", "url": "https://a.com", "description": "D1"}]
        points_payload = json.dumps([
            {"title": f"P{i}", "description": f"Desc {i}"} for i in range(5)
        ])
        llm = AsyncMock(return_value=points_payload)
        
        result = await orchestrate_persisted_briefing(
            self.session_factory,
            "Tema de teste valido com mais de tres caracteres",
            serp_client=serp,
            llm_complete=llm,
            prompt_loader=lambda: "System Prompt",
        )
        self.assertEqual(result.status, BriefingStatus.DRAFT)
        self.assertEqual(result.version, 2)
        self.assertEqual(len(result.points), 5)

        async with self.session_factory() as session:
            db_record = await get_briefing(session, result.id)
            self.assertIsNotNone(db_record)
            self.assertEqual(db_record.status, BriefingStatus.DRAFT)
            self.assertEqual(db_record.version, 2)
            
            versions = await get_briefing_versions(session, result.id)
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0].version, 2)
            self.assertEqual(versions[0].status, "draft")

    async def test_llm_exhaustion_persisted_as_failed(self):
        serp = AsyncMock()
        serp.search.return_value = [{"title": "R1", "url": "https://a.com", "description": "D1"}]
        llm = AsyncMock(return_value="malformed output")
        
        result = await orchestrate_persisted_briefing(
            self.session_factory,
            "Tema valido para exaustao",
            serp_client=serp,
            llm_complete=llm,
            prompt_loader=lambda: "System Prompt",
            llm_attempts=2,
        )
        self.assertEqual(result.status, BriefingStatus.FAILED)
        self.assertEqual(result.version, 2)
        self.assertEqual(len(result.points), 0)

        async with self.session_factory() as session:
            db_record = await get_briefing(session, result.id)
            self.assertEqual(db_record.status, BriefingStatus.FAILED)
            self.assertEqual(db_record.error, "Geração de briefing indisponível")

    async def test_persisted_invalid_content_retry_then_success(self):
        serp = AsyncMock()
        serp.search.return_value = [{"title": "R1", "url": "https://a.com", "description": "D1"}]
        invalid_json_1_point = json.dumps([{"title": "P1", "description": "D1"}])
        valid_json_3_points = json.dumps([
            {"title": f"P{i}", "description": f"Desc {i}"} for i in range(3)
        ])
        llm = AsyncMock(side_effect=[invalid_json_1_point, valid_json_3_points])

        result = await orchestrate_persisted_briefing(
            self.session_factory,
            "Tema valido para tentativa recuperada",
            serp_client=serp,
            llm_complete=llm,
            prompt_loader=lambda: "System Prompt",
            llm_attempts=4,
        )
        self.assertEqual(result.status, BriefingStatus.DRAFT)
        self.assertEqual(result.version, 2)
        self.assertEqual(len(result.points), 3)
        self.assertEqual(serp.search.call_count, 1)
        self.assertEqual(llm.call_count, 2)

        async with self.session_factory() as session:
            db_record = await get_briefing(session, result.id)
            self.assertEqual(db_record.status, BriefingStatus.DRAFT)
            self.assertEqual(db_record.version, 2)

            versions = await get_briefing_versions(session, result.id)
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0].version, 2)
            self.assertEqual(versions[0].status, "draft")

    async def test_persisted_invalid_content_exhaustion(self):
        serp = AsyncMock()
        serp.search.return_value = [{"title": "R1", "url": "https://a.com", "description": "D1"}]
        invalid_json_8_points = json.dumps([
            {"title": f"P{i}", "description": f"D{i}"} for i in range(8)
        ])
        invalid_json_bad_fields = json.dumps([
            {"title": "", "description": "D1"},
            {"title": "P2", "description": ""},
            {"title": "P3", "description": "D3"},
        ])
        llm = AsyncMock(side_effect=[invalid_json_8_points, invalid_json_bad_fields])

        result = await orchestrate_persisted_briefing(
            self.session_factory,
            "Tema valido para exaustao por conteudo invalido",
            serp_client=serp,
            llm_complete=llm,
            prompt_loader=lambda: "System Prompt",
            llm_attempts=2,
        )
        self.assertEqual(result.status, BriefingStatus.FAILED)
        self.assertEqual(result.version, 2)
        self.assertEqual(len(result.points), 0)
        self.assertEqual(serp.search.call_count, 1)
        self.assertEqual(llm.call_count, 2)

        async with self.session_factory() as session:
            db_record = await get_briefing(session, result.id)
            self.assertEqual(db_record.status, BriefingStatus.FAILED)
            self.assertEqual(db_record.error, "Geração de briefing indisponível")
            self.assertEqual(db_record.version, 2)

    async def test_task_cancellation_marks_emergency_failed(self):
        serp = AsyncMock()
        serp.search.return_value = []
        
        async def slow_llm(*args, **kwargs):
            await asyncio.sleep(10)
            return "[]"

        task = asyncio.create_task(
            orchestrate_persisted_briefing(
                self.session_factory,
                "Tema valido para cancelamento",
                serp_client=serp,
                llm_complete=slow_llm,
                prompt_loader=lambda: "System Prompt",
            )
        )
        await asyncio.sleep(0.05)
        task.cancel()
        
        with self.assertRaises(asyncio.CancelledError):
            await task

        async with self.session_factory() as session:
            from sqlalchemy import select
            from app.models.domain_models import BriefingRecord
            res = await session.execute(select(BriefingRecord))
            records = list(res.scalars().all())
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].status, "failed")
            self.assertEqual(records[0].version, 2)
            self.assertIn("abortado ou cancelado", records[0].error)
