import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from app.db.init_db import init_db
from app.db.models import GenerationAttempt
from app.db.research_repository import ResearchRepository
from app.db.session import get_sessionmaker


@pytest.mark.asyncio
async def test_tokens_accumulate_from_generation_attempts(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    from app.db import session as db_session

    db_session._engine = None
    db_session._sessionmaker = None
    await init_db()

    sf = get_sessionmaker()
    async with sf() as s:
        repo = ResearchRepository(s)
        rid = str(uuid.uuid4())
        await repo.create_research(
            tema="teste",
            pontos_textos=["p1"],
            id_pesquisa=rid,
            generation_attempts=[
                {
                    "id": str(uuid.uuid4()),
                    "etapa": "plan",
                    "model_requested": "m",
                    "prompt_hash": "h1",
                    "messages": [],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                }
            ],
        )
        p = await repo.get_research(rid)
        assert p.tokens_prompt == 10
        assert p.tokens_completion == 5
        assert p.tokens_total == 15

        # second attempt
        await repo.persist_generation_attempts(
            id_pesquisa=rid,
            ponto_id=None,
            generation_attempts=[
                {
                    "id": str(uuid.uuid4()),
                    "etapa": "search",
                    "model_requested": "m",
                    "prompt_hash": "h2",
                    "messages": [],
                    "usage": {"input_tokens": 7, "output_tokens": 3},
                }
            ],
            default_etapa="search",
            default_persona="historiador",
        )
        await s.commit()
        p2 = await repo.get_research(rid)
        assert p2.tokens_prompt == 17
        assert p2.tokens_completion == 8
        assert p2.tokens_total == 25


def test_modelo_pesquisa_mantem_coluna_de_redacao():
    """W1 copiou um models.py antigo; sem esta coluna o UPDATE do retry estourava 500."""
    from app.db.models import Pesquisa

    assert "metadados_redacao" in Pesquisa.__table__.columns
    assert "tokens_total" in Pesquisa.__table__.columns
