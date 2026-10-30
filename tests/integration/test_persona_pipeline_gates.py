"""Testes de integração focados para portões do pipeline com subconjuntos de personas por pesquisa.

Cobre os requisitos de:
1. Ciclo completo de 2 personas: plan (n=2, personas=['historiador', 'cetico']) -> search (2 executadas)
   -> audit (elegível, não reprova por personas não selecionadas) -> writer (aprovado e concluído).
2. Bloqueio estrito de Auditor e Writer quando persona SELECIONADA está ausente.
3. Bloqueio estrito de Auditor e Writer quando evidências da persona SELECIONADA estão malformadas.
4. Compatibilidade conservadora com planos legados (sem snapshot) exigindo todas as 4 personas canônicas.
5. Isolamento estrito entre pesquisas concorrentes com diferentes subconjuntos de personas (sem contaminação cruzada).
6. Retentativa focada de persona selecionada ausente com recomposição bem-sucedida para 'coletado' e aprovação na auditoria.
7. Tarefas de reparo da auditoria nunca adicionam personas não selecionadas silenciosamente.
8. Helper síncrono do pipeline autônomo (execute_sync_pipeline / PipelineRunner.run) com plano de 2 personas.
9. Resiliência a metadados_planejamento corrompidos ou malformados com fallback seguro ao padrão conservador.
"""

import json
from typing import Any, Dict, List
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from app.core.personas import resolve_required_search_personas
from app.core.pipeline_runner import PipelineRunner, execute_sync_pipeline
from app.db.models import ConteudoColetado, Pesquisa, Ponto
from app.db.research_repository import ResearchRepository
from app.db.session import get_sessionmaker
from app.main import app
from tests.mocks.http_mock import create_mock_transport


@pytest_asyncio.fixture(autouse=True)
async def setup_integration():
    """Garante ambiente de teste isolado e banco inicializado."""
    from app.main import _setup_integration_test_env
    _setup_integration_test_env()
    from app.db.init_db import init_db
    from app.db.session import get_engine
    await init_db(get_engine())


# ==============================================================================
# 1. Ciclo Completo 2 Personas: Plan -> Search -> Audit -> Writer
# ==============================================================================

@pytest.mark.asyncio
async def test_full_pipeline_with_2_personas_subset_succeeds_end_to_end():
    """Valida o ciclo completo ponta-a-ponta para um plano com subconjunto de 2 personas (historiador + cetico).
    
    Verifica que:
    - O plano é criado com 2 pontos e snapshot ['historiador', 'cetico'].
    - A busca executa as 2 personas e marca os pontos com status 'coletado' (e não 'parcial').
    - A auditoria avalia e NÃO reprova por ausência de 'visionario' ou 'futurista'.
    - O Writer é liberado (pronto_para_writer == True), redige o relatório e atinge status 'concluido'.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 55001)),
        base_url="http://localhost:8000",
    ) as client:
        # 1. Planejamento com n_pontos=2 e personas=['historiador', 'cetico']
        resp_plan = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Diferenças entre Energia Solar Fotovoltaica e Solar Térmica Residencial",
                "n_pontos": 2,
                "personas": ["historiador", "cetico"],
            },
        )
        assert resp_plan.status_code == 201
        plan_data = resp_plan.json()
        id_pesquisa = plan_data["id_pesquisa"]
        assert plan_data["n_pontos"] == 2
        assert len(plan_data["pontos"]) == 2
        assert plan_data["preferencias"]["personas"] == ["historiador", "cetico"]

        # 2. Busca web concorrente para a pesquisa
        resp_search = await client.post(
            "/api/v1/search",
            json={"id_pesquisa": id_pesquisa},
        )
        assert resp_search.status_code == 200
        search_data = resp_search.json()
        assert search_data["total_pontos_processados"] == 2
        assert search_data["total_falhas_coleta"] == 0
        assert search_data["status_pesquisa"] == "coletado"

        for p_res in search_data["resumo_coletas"]:
            assert p_res["status"] == "coletado", (
                f"Ponto {p_res['ponto_n']} deveria ter status 'coletado', recebido: {p_res['status']} com diag: {p_res.get('diagnostico')}"
            )
            assert len(p_res["personas"]) == 2
            personas_exec = [item["persona"] for item in p_res["personas"]]
            assert sorted(personas_exec) == ["cetico", "historiador"]

        # 3. Auditoria de Qualidade
        resp_audit = await client.post(
            "/api/v1/audit",
            json={"id_pesquisa": id_pesquisa, "criterios_minimos": 11},
        )
        assert resp_audit.status_code == 200
        audit_data = resp_audit.json()
        assert audit_data["total_pontos"] == 2
        assert audit_data["aprovados"] == 2
        assert audit_data["reprovados"] == 0
        assert audit_data["pronto_para_writer"] is True
        assert audit_data["status_geral"] in ("auditado", "aprovado")

        for aud in audit_data["auditorias"]:
            assert aud["status"] == "aprovado"
            assert aud["valido"] is True
            # Garante que não houve reprovação por ausência de unselected roles
            assert aud["pontos_fracos"] is None

        # 4. Redação do Dossiê Final
        resp_writer = await client.post(
            "/api/v1/writer",
            json={"id_pesquisa": id_pesquisa},
        )
        assert resp_writer.status_code == 200
        writer_data = resp_writer.json()
        assert writer_data["status"] == "concluido"
        assert writer_data["dossier_final"] is not None
        assert len(writer_data["dossier_final"]) > 100
        assert writer_data["qualidade_artigo"]["avaliacao_valida"] is True
        assert writer_data["qualidade_artigo"]["criterios_aprovados"] >= 11


# ==============================================================================
# 2. Bloqueio Estrito por Ausência de Persona SELECIONADA
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_and_writer_block_when_selected_persona_is_missing():
    """Valida que quando uma persona que FOI selecionada (ex: 'cetico') falta na coleta,
    a Auditoria reprova o ponto e o Writer é estritamente bloqueado.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 55002)),
        base_url="http://localhost:8000",
    ) as client:
        # 1. Cria plano com historiador e cetico
        resp_plan = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Impactos do Uso de Células de Combustível de Hidrogênio",
                "n_pontos": 1,
                "personas": ["historiador", "cetico"],
            },
        )
        assert resp_plan.status_code == 201
        id_pesquisa = resp_plan.json()["id_pesquisa"]
        ponto_id = resp_plan.json()["pontos"][0]["ponto_id"]

        # Executa a busca
        resp_search = await client.post("/api/v1/search", json={"id_pesquisa": id_pesquisa})
        assert resp_search.status_code == 200

    # 2. Simula corrupção/omissão da persona 'cetico' na coleta do banco
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        coletas = await repo.get_collected_content_for_point(id_pesquisa, ponto_id)
        assert len(coletas) > 0
        ultima_coleta = coletas[-1]
        assert ultima_coleta.metadados_coleta is not None
        meta = json.loads(ultima_coleta.metadados_coleta)
        # Remove intencionalmente 'cetico' dos resultados
        if "cetico" in meta.get("resultados_personas", {}):
            del meta["resultados_personas"]["cetico"]
        if "cetico" in meta.get("diario_acoes", {}):
            del meta["diario_acoes"]["cetico"]

        await db.execute(
            update(ConteudoColetado)
            .where(ConteudoColetado.id == ultima_coleta.id)
            .values(metadados_coleta=json.dumps(meta))
        )
        await db.commit()

    # 3. Auditoria deve REPROVAR o ponto por ausência da persona selecionada 'cetico'
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 55002)),
        base_url="http://localhost:8000",
    ) as client:
        resp_audit = await client.post(
            "/api/v1/audit",
            json={"id_pesquisa": id_pesquisa},
        )
        assert resp_audit.status_code == 200
        audit_data = resp_audit.json()
        assert audit_data["pronto_para_writer"] is False
        assert audit_data["aprovados"] == 0
        assert audit_data["reprovados"] == 1
        ponto_aud = audit_data["auditorias"][0]
        assert ponto_aud["status"] == "reprovado"
        assert "cetico" in ponto_aud["pontos_fracos"]
        assert "coleta incompleta" in ponto_aud["pontos_fracos"].lower()

        # 4. Writer DEVE ser estritamente bloqueado (HTTP 400 por UNAPPROVED_POINTS)
        resp_writer = await client.post(
            "/api/v1/writer",
            json={"id_pesquisa": id_pesquisa},
        )
        assert resp_writer.status_code == 400
        assert "UNAPPROVED_POINTS" in resp_writer.text or "READINESS_FAILED" in resp_writer.text


# ==============================================================================
# 3. Bloqueio Estrito por Evidências Malformadas em Persona SELECIONADA
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_and_writer_block_when_selected_persona_evidence_is_malformed():
    """Valida que quando uma persona selecionada possui análise vazia ou conclusões malformadas,
    o Auditor reprova por inconsistência e o Writer bloqueia com READINESS_FAILED.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 55003)),
        base_url="http://localhost:8000",
    ) as client:
        resp_plan = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Avanços em Nanomateriais para Dessalinização de Água",
                "n_pontos": 1,
                "personas": ["historiador", "cetico"],
            },
        )
        assert resp_plan.status_code == 201
        id_pesquisa = resp_plan.json()["id_pesquisa"]
        ponto_id = resp_plan.json()["pontos"][0]["ponto_id"]

        resp_search = await client.post("/api/v1/search", json={"id_pesquisa": id_pesquisa})
        assert resp_search.status_code == 200

    # Injeta análise vazia na persona 'historiador'
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        coletas = await repo.get_collected_content_for_point(id_pesquisa, ponto_id)
        ultima_coleta = coletas[-1]
        assert ultima_coleta.metadados_coleta is not None
        meta = json.loads(ultima_coleta.metadados_coleta)
        meta["resultados_personas"]["historiador"]["analise"] = "   "  # Análise vazia
        await db.execute(
            update(ConteudoColetado)
            .where(ConteudoColetado.id == ultima_coleta.id)
            .values(metadados_coleta=json.dumps(meta))
        )
        await db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 55003)),
        base_url="http://localhost:8000",
    ) as client:
        # Auditoria reprova por inconsistência
        resp_audit = await client.post("/api/v1/audit", json={"id_pesquisa": id_pesquisa})
        assert resp_audit.status_code == 200
        audit_data = resp_audit.json()
        assert audit_data["pronto_para_writer"] is False
        ponto_aud = audit_data["auditorias"][0]
        assert ponto_aud["status"] == "reprovado"
        assert "análise vazia" in ponto_aud["pontos_fracos"].lower() or "inconsistência" in ponto_aud["pontos_fracos"].lower()

        # Writer bloqueia
        resp_writer = await client.post("/api/v1/writer", json={"id_pesquisa": id_pesquisa})
        assert resp_writer.status_code == 400


# ==============================================================================
# 4. Compatibilidade Conservadora: Pesquisa Legada Sem Snapshot Exige 4 Personas
# ==============================================================================

@pytest.mark.asyncio
async def test_legacy_research_without_snapshot_strictly_requires_all_4_personas():
    """Pesquisas legadas criadas sem snapshot de preferências continuam exigindo todas as 4 personas canônicas.
    
    Se uma pesquisa legada tiver apenas 2 personas na coleta, a Auditoria deve REPROVAR
    explicitamente pelas duas ausentes, preservando 100% dos portões de qualidade legados.
    """
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        # Cria pesquisa sem metadados_planejamento (legada)
        pesquisa = await repo.create_research(
            tema="Pesquisa Legada Criada Sem Snapshot",
            pontos_textos=["Ponto Único Legado"],
            plano_estruturado={"pedido_original": "Pesquisa Legada Criada Sem Snapshot"},
            metadados_planejamento=None,
        )
        id_pesquisa = pesquisa.id_pesquisa
        pontos = await repo.list_points(id_pesquisa)
        ponto = pontos[0]

        # Simula coleta com apenas historiador e cetico
        meta_coleta = {
            "versao": 1,
            "fontes": {
                "src_1": {
                    "source_id": "src_1",
                    "url": "https://example.org/doc1",
                    "status": "read_ok",
                    "body_hash": "hash1",
                    "length": 500,
                    "accessed_at": "2026-10-26T12:00:00Z",
                }
            },
            "trechos": {
                "chk_1": {
                    "chunk_id": "chk_1",
                    "source_id": "src_1",
                    "text": "Evidência comprovada",
                    "text_hash": "thash1",
                    "start_offset": 0,
                    "end_offset": 20,
                }
            },
            "selecao_contexto": {
                "historiador": {"selected_chunk_ids": ["chk_1"], "total_delivered_chars": 20, "budget_chars": 8000},
                "cetico": {"selected_chunk_ids": ["chk_1"], "total_delivered_chars": 20, "budget_chars": 8000},
            },
            "diario_acoes": {
                "historiador": [{"acao": "buscar"}],
                "cetico": [{"acao": "buscar"}],
            },
            "resultados_personas": {
                "historiador": {
                    "analise": "Análise substantiva do historiador com fontes.",
                    "sucesso": True,
                    "conclusoes": [{"claim_id": "c1", "afirmacao": "Fato H", "evidencias": ["chk_1"]}],
                },
                "cetico": {
                    "analise": "Análise substantiva do cético com fontes.",
                    "sucesso": True,
                    "conclusoes": [{"claim_id": "c2", "afirmacao": "Fato C", "evidencias": ["chk_1"]}],
                },
            },
        }

        await repo.save_collected_content(
            id_pesquisa=id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesquisa.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteúdo consolidado parcial",
            urls_lidas=["https://example.org/doc1"],
            urls_fonte=["https://example.org/doc1"],
            status_ponto="parcial",
            metadados_coleta=meta_coleta,
        )

    # Executa a auditoria na pesquisa legada
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 55004)),
        base_url="http://localhost:8000",
    ) as client:
        resp_audit = await client.post("/api/v1/audit", json={"id_pesquisa": id_pesquisa})
        assert resp_audit.status_code == 200
        audit_data = resp_audit.json()
        assert audit_data["pronto_para_writer"] is False
        assert audit_data["aprovados"] == 0
        ponto_aud = audit_data["auditorias"][0]
        assert ponto_aud["status"] == "reprovado"
        # Deve acusar ausência de 'futurista' e 'visionario'
        assert "futurista" in ponto_aud["pontos_fracos"]
        assert "visionario" in ponto_aud["pontos_fracos"]


# ==============================================================================
# 5. Segurança de Pesquisas Concorrentes e Não Contaminação Cruzada
# ==============================================================================

@pytest.mark.asyncio
async def test_independent_researches_do_not_cross_contaminate_persona_contracts():
    """Duas pesquisas simultâneas com personas diferentes (A: ['historiador']; B: ['visionario', 'futurista'])
    devem ser auditadas independentemente respeitando seus respectivos snapshots isolados.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 55005)),
        base_url="http://localhost:8000",
    ) as client:
        # Pesquisa A
        resp_a = await client.post(
            "/api/v1/plan",
            json={"tema": "História da Tipografia Móvel", "n_pontos": 1, "personas": ["historiador"]},
        )
        assert resp_a.status_code == 201
        id_a = resp_a.json()["id_pesquisa"]

        # Pesquisa B
        resp_b = await client.post(
            "/api/v1/plan",
            json={"tema": "Futuro da Fusão Nuclear Comercial", "n_pontos": 1, "personas": ["visionario", "futurista"]},
        )
        assert resp_b.status_code == 201
        id_b = resp_b.json()["id_pesquisa"]

        # Busca para A
        r_search_a = await client.post("/api/v1/search", json={"id_pesquisa": id_a})
        assert r_search_a.status_code == 200
        assert r_search_a.json()["resumo_coletas"][0]["status"] == "coletado"
        assert [p["persona"] for p in r_search_a.json()["resumo_coletas"][0]["personas"]] == ["historiador"]

        # Busca para B
        r_search_b = await client.post("/api/v1/search", json={"id_pesquisa": id_b})
        assert r_search_b.status_code == 200
        assert r_search_b.json()["resumo_coletas"][0]["status"] == "coletado"
        assert sorted([p["persona"] for p in r_search_b.json()["resumo_coletas"][0]["personas"]]) == ["futurista", "visionario"]

        # Auditoria para A: deve aprovar sem exigir visionario/futurista
        r_audit_a = await client.post("/api/v1/audit", json={"id_pesquisa": id_a})
        assert r_audit_a.status_code == 200
        assert r_audit_a.json()["pronto_para_writer"] is True
        assert r_audit_a.json()["aprovados"] == 1

        # Auditoria para B: deve aprovar sem exigir historiador/cetico
        r_audit_b = await client.post("/api/v1/audit", json={"id_pesquisa": id_b})
        assert r_audit_b.status_code == 200
        assert r_audit_b.json()["pronto_para_writer"] is True
        assert r_audit_b.json()["aprovados"] == 1


# ==============================================================================
# 6. Tarefas de Reparo da Auditoria Nunca Adicionam Personas Não Selecionadas
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_repair_tasks_never_target_unselected_roles():
    """Quando um critério é reprovado na auditoria, as tarefas projetadas em 'personas_alvo'
    devem ser estritamente restritas às personas selecionadas da pesquisa.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 55006)),
        base_url="http://localhost:8000",
    ) as client:
        # Plano com apenas 'historiador' e 'cetico'
        resp_plan = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Marcos Regulatórios de IA na Europa",
                "n_pontos": 1,
                "personas": ["historiador", "cetico"],
            },
        )
        assert resp_plan.status_code == 201
        id_pesquisa = resp_plan.json()["id_pesquisa"]
        ponto_id = resp_plan.json()["pontos"][0]["ponto_id"]

        await client.post("/api/v1/search", json={"id_pesquisa": id_pesquisa})

    # Consulta evidências reais do banco para usar claim_ids e source_ids válidos da coleta
    session_factory = get_sessionmaker()
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        coletas = await repo.get_collected_content_for_point(id_pesquisa, ponto_id)
        assert len(coletas) > 0
        assert coletas[-1].metadados_coleta is not None
        meta = json.loads(coletas[-1].metadados_coleta)
        real_claims = []
        for r_p in meta.get("resultados_personas", {}).values():
            for c in r_p.get("conclusoes", []):
                if c.get("claim_id"):
                    real_claims.append(str(c["claim_id"]))
        real_sources = list(meta.get("fontes", {}).keys())

    claim_to_use = real_claims[0] if real_claims else "clm_1"
    source_to_use = real_sources[0] if real_sources else "src_1"

    # Força a resposta da auditoria a simular critérios reprovados com personas_pertinentes que incluem não-selecionadas
    import httpx
    from tests.mocks.http_mock import MockNetwork
    mock_net = MockNetwork()

    def audit_llm_handler(request):
        # Retorna critérios reprovados sugerindo 'visionario' e 'futurista' (não selecionadas)
        criterios = [
            {
                "id": i,
                "aprovado": False if i in (1, 2) else True,
                "justificativa": f"Justificativa {i}",
                "claim_ids": [claim_to_use],
                "source_ids": [source_to_use],
                "lacuna": "Falta comprovação primária",
                "correcao": "Buscar mais evidências",
                "personas_pertinentes": ["visionario", "futurista", "cetico"],
            }
            for i in range(1, 13)
        ]
        content_json = json.dumps({
            "status": "reprovado",
            "resumo_auditoria": "Reprovado para teste de tarefas",
            "criterios": criterios,
        }, ensure_ascii=False)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-audit-mock",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content_json},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    mock_net.custom_handlers["chat/completions"] = audit_llm_handler
    custom_transport = create_mock_transport(mock_net)

    session_factory = get_sessionmaker()
    async with session_factory() as db:
        repo = ResearchRepository(session=db)
        from app.core.auditor import Auditor
        from app.tools.llm_client import LLMClient
        llm = LLMClient(api_key="openai-mock", transport=custom_transport)
        auditor = Auditor(research_repo=repo, llm_client=llm)

        audit_res = await auditor.execute_audit(id_pesquisa=id_pesquisa)
        assert audit_res["status_geral"] == "reprovado"
        ponto_item = audit_res["auditorias"][0]
        assert ponto_item["tarefas"] is not None

        # As tarefas projetadas em personas_alvo NÃO podem conter 'visionario' ou 'futurista'!
        for t in ponto_item["tarefas"]:
            alvos = t.get("personas_alvo", [])
            for p_alvo in alvos:
                assert p_alvo in ("historiador", "cetico"), (
                    f"Persona não selecionada '{p_alvo}' encontrada na tarefa de reparo: {t}"
                )


# ==============================================================================
# 7. Retentativa Focada e Recomposição em Pesquisa de 2 Personas
# ==============================================================================

@pytest.mark.asyncio
async def test_search_retry_missing_selected_role_recomposes_to_coletado():
    """Valida retentativa de uma persona selecionada ausente/falha:
    - Attempt 1: executa apenas 'historiador' -> status é 'parcial' (1/2).
    - Attempt 2: retry executa 'cetico' -> recomposição reúne 'historiador' e 'cetico' -> status vira 'coletado' (2/2).
    """
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 55007)),
        base_url="http://localhost:8000",
    ) as client:
        # Plano de 2 personas
        resp_plan = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Avanços em Baterias de Estado Sólido",
                "n_pontos": 1,
                "personas": ["historiador", "cetico"],
            },
        )
        assert resp_plan.status_code == 201
        id_pesquisa = resp_plan.json()["id_pesquisa"]

        # Tentativa 1: busca direcionada fornecendo explicitamente apenas ['historiador']
        r1 = await client.post(
            "/api/v1/search",
            json={"id_pesquisa": id_pesquisa, "personas": ["historiador"]},
        )
        assert r1.status_code == 200
        ponto_r1 = r1.json()["resumo_coletas"][0]
        assert ponto_r1["status"] == "parcial"
        assert "1/2" in (ponto_r1.get("diagnostico") or "")

        # Tentativa 2: retry direcionado fornecendo a persona faltante ['cetico']
        r2 = await client.post(
            "/api/v1/search",
            json={"id_pesquisa": id_pesquisa, "personas": ["cetico"]},
        )
        assert r2.status_code == 200
        ponto_r2 = r2.json()["resumo_coletas"][0]
        # Agora recomposto com sucesso: ambas historiador e cetico presentes!
        assert ponto_r2["status"] == "coletado"
        assert len(ponto_r2["personas"]) == 2
        personas_presentes = [p["persona"] for p in ponto_r2["personas"]]
        assert sorted(personas_presentes) == ["cetico", "historiador"]


# ==============================================================================
# 8. Pipeline Helper Síncrono (execute_sync_pipeline) com 2 Personas
# ==============================================================================

@pytest.mark.asyncio
async def test_pipeline_helper_sync_with_2_personas_plan():
    """Valida o helper de execução síncrona do pipeline autônomo (execute_sync_pipeline)
    sobre um plano com subconjunto de 2 personas.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 55008)),
        base_url="http://localhost:8000",
    ) as client:
        resp_plan = await client.post(
            "/api/v1/plan",
            json={
                "tema": "Comparativo de Eficiência Térmica e Fotovoltaica",
                "n_pontos": 1,
                "personas": ["historiador", "cetico"],
            },
        )
        assert resp_plan.status_code == 201
        id_pesquisa = resp_plan.json()["id_pesquisa"]

    # Executa o pipeline autônomo síncrono com mock transport
    transport = create_mock_transport()
    res_pipeline = await execute_sync_pipeline(id_pesquisa=id_pesquisa, transport=transport)
    assert res_pipeline["status"] == "concluido"
    assert res_pipeline["dossier_final"] is not None


# ==============================================================================
# 9. Fallback Seguro para Metadados de Planejamento Corrompidos
# ==============================================================================

def test_resolve_required_search_personas_fallback_safety():
    """Testa diretamente a função contratual resolve_required_search_personas frente a falhas de entrada."""
    # 1. Metadados None -> fallback conservador (4)
    assert resolve_required_search_personas(None, None) == ["historiador", "visionario", "cetico", "futurista"]

    # 2. JSON inválido -> fallback conservador (4)
    assert resolve_required_search_personas(None, "corrupted { json") == ["historiador", "visionario", "cetico", "futurista"]

    # 3. JSON válido sem preferencias -> fallback conservador (4)
    assert resolve_required_search_personas(None, json.dumps({"outro": 123})) == ["historiador", "visionario", "cetico", "futurista"]

    # 4. JSON válido com personas vazias -> fallback conservador (4)
    assert resolve_required_search_personas(None, json.dumps({"preferencias": {"personas": []}})) == [
        "historiador",
        "visionario",
        "cetico",
        "futurista",
    ]

    # 5. JSON válido com subset válido -> retorna subset exato preservando ordem
    assert resolve_required_search_personas(
        None, json.dumps({"preferencias": {"personas": ["cetico", "historiador"]}})
    ) == ["cetico", "historiador"]

    # 6. Fallback explícito respeitado apenas em dados legados sem snapshot
    assert resolve_required_search_personas(None, None, fallback_personas=["visionario"]) == ["visionario"]

    # 7. Quando snapshot existe, fallback_personas é ignorado
    assert resolve_required_search_personas(
        None, json.dumps({"preferencias": {"personas": ["historiador"]}}), fallback_personas=["visionario"]
    ) == ["historiador"]
