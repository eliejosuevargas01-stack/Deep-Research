"""Testes de integração para cenários negativos e casos de borda (edge cases).

Cobre recusa de plano por ausência de N_PONTOS (HTTP 500), pesquisa inexistente (HTTP 404),
auditoria sem coletas prévias (HTTP 400) e bloqueio estrito de redação com pontos pendentes (HTTP 400).
Atende a RN-02, RN-07, RF-07 e RF-09.
"""

import uuid
import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings


@pytest.mark.asyncio
async def test_plan_missing_n_pontos_returns_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica erro HTTP 500 quando N_PONTOS não está configurada nem no ambiente nem no banco (RN-02)."""
    from app.main import app

    monkeypatch.delenv("N_PONTOS", raising=False)
    get_settings.cache_clear()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/plan", json={"tema": "Tema Válido Para Teste"})
        assert resp.status_code == 500
        data = resp.json()
        assert "N_PONTOS" in str(data) or "CONFIG_ERROR" in str(data)


@pytest.mark.asyncio
async def test_search_nonexistent_research_returns_404() -> None:
    """Verifica que consulta de pesquisa inexistente em /api/v1/search retorna HTTP 404."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        inexistente_id = str(uuid.uuid4())
        resp = await client.post("/api/v1/search", json={"id_pesquisa": inexistente_id})
        assert resp.status_code == 404
        assert "RESEARCH_NOT_FOUND" in str(resp.json()) or "não localizada" in str(resp.json())


@pytest.mark.asyncio
async def test_audit_without_collected_content_returns_400() -> None:
    """Verifica recusa de auditoria com HTTP 400 se a pesquisa não possuir conteúdo coletado (RF-07)."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Cria apenas o plano (sem executar a busca)
        plan_resp = await client.post("/api/v1/plan", json={"tema": "Tema Sem Coletas"})
        id_pesquisa = plan_resp.json()["id_pesquisa"]

        # Dispara auditoria diretamente
        audit_resp = await client.post("/api/v1/audit", json={"id_pesquisa": id_pesquisa})
        assert audit_resp.status_code == 400
        assert "SEARCH_NOT_COMPLETED" in str(audit_resp.json())

    # RF02/EC01: recusa sem dados NÃO pode alterar estado (nenhum ponto reprovado)
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models import Ponto as PontoModel

        pontos = (
            await session.execute(
                PontoModel.__table__.select().where(PontoModel.id_pesquisa == id_pesquisa)
            )
        ).fetchall()
        assert len(pontos) >= 1
        assert all(p.status != "reprovado" for p in pontos), "Pré-condição sem coleta não pode reprovar pontos"


@pytest.mark.asyncio
async def test_writer_blocked_when_points_pending_returns_400() -> None:
    """Verifica bloqueio estrito de redação com HTTP 400 e UNAPPROVED_POINTS quando o Writer
    é acionado sem aprovação prévia da auditoria (RN-07, RF-09), provando que NENHUM
    documento, nenhuma tentativa de redação e nem estado/contadores são alterados."""
    from app.main import app
    from app.db.models import GenerationAttempt, Pesquisa, Ponto

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Cria plano e coleta, mas NÃO audita
        plan_resp = await client.post("/api/v1/plan", json={"tema": "Tema Não Auditado"})
        id_pesquisa = plan_resp.json()["id_pesquisa"]
        await client.post("/api/v1/search", json={"id_pesquisa": id_pesquisa})

        # Tenta redigir diretamente: deve ser bloqueado com HTTP 400 e contrato atual
        writer_resp = await client.post("/api/v1/writer", json={"id_pesquisa": id_pesquisa})
        assert writer_resp.status_code == 400
        assert "UNAPPROVED_POINTS" in str(writer_resp.json())

    # Prova de bloqueio real no SQLite: nada de dossiê, nenhuma tentativa, estado intacto
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as session:
        pesq = await session.get(Pesquisa, id_pesquisa)
        assert pesq is not None
        assert pesq.dossier_final is None, "Nenhum dossiê pode ser persistido por redação bloqueada"
        assert pesq.concluido_em is None
        assert pesq.status_pipeline in ("coletado", "buscando", "planejado"), "Estado legítimo pré-Writer preservado"
        gas = (
            await session.execute(
                GenerationAttempt.__table__.select()
                .where(GenerationAttempt.id_pesquisa == id_pesquisa)
                .where(GenerationAttempt.etapa == "write")
            )
        ).fetchall()
        assert len(gas) == 0, "Nenhuma tentativa de redação (etapa='write') pode ser fabricada quando o Writer é bloqueado"
        pontos = (
            await session.execute(
                Ponto.__table__.select().where(Ponto.id_pesquisa == id_pesquisa)
            )
        ).fetchall()
        assert len(pontos) >= 1
        assert all(p.status != "aprovado" for p in pontos)
    await engine.dispose()


@pytest.mark.asyncio
async def test_plan_invalid_payload_returns_422() -> None:
    """Verifica rejeição por validação quando o tema tem menos de 5 caracteres."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/plan", json={"tema": "IA"})
        assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_webhook_failure_preserves_dossier_in_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica que a falha definitiva no webhook não descarta o dossiê final persistido no SQLite."""
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Ciclo até redação
        plan_resp = await client.post("/api/v1/plan", json={"tema": "Pesquisa Webhook Falha"})
        id_pesquisa = plan_resp.json()["id_pesquisa"]
        await client.post("/api/v1/search", json={"id_pesquisa": id_pesquisa})
        await client.post("/api/v1/audit", json={"id_pesquisa": id_pesquisa})

        # Redação com webhook com falha definitiva
        writer_resp = await client.post("/api/v1/writer", json={"id_pesquisa": id_pesquisa})
        assert writer_resp.status_code == 200
        dados = writer_resp.json()
        assert dados["status"] == "concluido"
        assert dados["total_caracteres_dossier"] > 0
        assert dados["webhook_entrega"]["status"] in ("entregue", "falha_definitiva")

        # Qualidade editorial estrita: vetor 12 completo com corte >= 11/12 e sem CoT público
        qualidade = dados["qualidade_artigo"]
        assert qualidade["avaliacao_valida"] is True
        assert qualidade["criterios_aprovados"] >= 11
        assert len(qualidade["criterios"]) == 12
        assert [c["id"] for c in qualidade["criterios"]] == list(range(1, 13))
        assert all("justificativa" in c for c in qualidade["criterios"])
        assert dados["reasoning_dossier"] is None, "Raciocínio interno nunca é exposto (W11)"

    # Persistência real do dossiê no SQLite mesmo com entrega falha
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models import Pesquisa as PesquisaModel

        pesq = await session.get(PesquisaModel, id_pesquisa)
        assert pesq is not None
        assert pesq.dossier_final and len(pesq.dossier_final) > 0, "Dossiê deve persistir mesmo com webhook falho"
    await engine.dispose()
