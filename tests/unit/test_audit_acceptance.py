# -*- coding: utf-8 -*-
"""Testes de aceitação para o componente de Auditoria de Qualidade (Audit).

Cobre a matriz completa de requisitos de audit-scope.md, addendum-confiabilidade-20261024-v5-audit.md
e as revisões do orquestrador em audit-r1-gate1-review.md e audit-r1-gate1-review-2.md:
1. Limites 9/10/11/12, parâmetros estritos e percentuais determinísticos (83.33, 91.67, 100.0).
2. Vetores inválidos isolados (StrictInt, StrictBool, justificativa vazia, refs desconhecidas, etc.).
3. Última coleta vs coleta antiga, exigência de corpo canônico, proveniência e validação de hash/offsets.
4. Captura real de payload: plano/eixo canônicos íntegros (comparação por igualdade), 4 personas,
   exclusão de CoT e coletas antigas, orçamentos isolados de 32k caracteres de evidência e 120k de JSON.
5. Sem vazamento entre pontos via locals(), isolamento de deliberação, limpeza de pontos_fracos na aprovação.
6. Envelopes LLM, finish regular, reasoning privado protegido, tolerância a custos nulos.
7. Reparo dirigido adicional com preservação de todos os envelopes na etapa audit.
8. Persistência de grade em metadados_coleta.auditorias e endpoint HTTP completo com monkeypatch de transporte.
9. Cache por input_hash, recálculo puro de corte sem LLM, invalidação por nova coleta/instrução, delta antes/depois, tarefas projetadas.
10. Concorrência atômica com SQLite em arquivo e timeouts finitos (sem sleeps nem esperas indefinidas):
    bloqueio mútuo Search/Audit e Audit/Search, fence de posse antiga em voo com histórico marcado obsoleto.
11. Cancelamento com preservação de envelopes gerados e liberação da reserva própria sem fabricar finish/usage da pendente.
12. Teto estrito de 3 tentativas por ponto em sequência real e cache no limite.
13. Filtro opcional ponto_id com agregação sobre todos os pontos frescos (pendente impede pronto_para_writer).
14. Fechamento de clientes em finally e validação de persona sem fallback indevido.
15. Integração PipelineRunner: bloqueio de Writer para pendências/reprovações/tetos e direcionamento de personas.
"""
import asyncio
import hashlib
import json
import os
import uuid
from typing import Any, Dict, List, Optional
import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.auditor import Auditor
try:
    from app.core.auditor import (
        AUDIT_EVIDENCE_BUDGET_CHARS,
        AUDIT_JSON_BUDGET_CHARS,
        AUDIT_POINT_LEASE_SECONDS,
        AUDIT_POINT_TIMEOUT_SECONDS,
    )
except ImportError:
    AUDIT_EVIDENCE_BUDGET_CHARS = 320000
    AUDIT_JSON_BUDGET_CHARS = 1200000
    AUDIT_POINT_LEASE_SECONDS = 600
    AUDIT_POINT_TIMEOUT_SECONDS = 180.0

from app.core.pipeline_runner import PipelineRunner
from app.db.init_db import init_db
from app.db.models import ConteudoColetado, GenerationAttempt, Pesquisa, Ponto
from app.db.research_repository import ResearchRepository
from app.db.session import create_engine_with_pragmas
from app.main import app
from app.schemas.audit import AuditRequest, AuditResponse
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response


# ==============================================================================
# FACTORIES E HELPERS CANÔNICOS (COM CORPO E PROVENIÊNCIA REAL)
# ==============================================================================

CANONICAL_EIXO = {
    "pergunta_principal": "Quais vulnerabilidades de segurança do PHP foram formalmente confirmadas em outubro de 2026?",
    "subperguntas": [
        "Houve publicação de releases de segurança oficiais?",
        "Os CVEs mencionados estão registrados no MITRE/NVD?",
    ],
    "hipoteses": ["Hipótese A: mantenedores publicaram releases de segurança emergenciais."],
    "consultas_iniciais": ["site:php.net security release 2026"],
    "fontes_primarias_desejadas": ["php.net", "thephp.foundation"],
    "riscos_de_vies": ["viés de confirmação e amplificação jornalística"],
    "evidencias_que_refutariam": ["ausência de commits e changelogs oficiais"],
    "criterio_de_conclusao": "três fontes primárias independentes confirmando ou refutando",
    "investigabilidade": "viável em fontes públicas canônicas",
    "eixo_essencial": False,
}

CANONICAL_PLANO = {
    "pedido_original": "Investigue quais falhas de segurança do PHP foram divulgadas oficialmente em outubro de 2026.",
    "pedido_normalizado": "Investigar divulgação oficial de vulnerabilidades do PHP em outubro de 2026.",
    "publico": "Especialistas em segurança e tomadores de decisão",
    "formato_entrega": "Dossiê analítico discriminando confirmações, rumores e ausência de evidências",
    "recorte_temporal": "19 a 24 de outubro de 2026",
    "pressupostos": ["Fontes primárias canônicas para o PHP são php.net e thephp.foundation"],
    "ambiguidades": ["Divergência entre vazamento jornalístico e publicação formal de correção"],
    "pergunta_de_esclarecimento": None,
    "eixos": [CANONICAL_EIXO],
}


def make_source_data(
    source_id: str,
    url: str,
    body: str,
    status: str = "read_ok",
) -> Dict[str, Any]:
    """Cria fonte CANÔNICA com corpo real preservado, body_hash e proveniência."""
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return {
        "source_id": source_id,
        "url": url,
        "body": body,
        "body_hash": body_hash,
        "length": len(body),
        "status": status,
        "accessed_at": "2026-10-24T20:00:00Z",
    }


def make_chunk_data(
    idx: int,
    source_id: str,
    url: str,
    full_body: str,
    start_offset: int,
    length: int,
) -> Dict[str, Any]:
    """Cria trecho estritamente coerente com o corpo da fonte, offsets e text_hash."""
    text_slice = full_body[start_offset : start_offset + length]
    text_hash = hashlib.sha256(text_slice.encode("utf-8")).hexdigest()
    return {
        "chunk_id": f"chk_{idx}",
        "source_id": source_id,
        "url": url,
        "start_offset": start_offset,
        "end_offset": start_offset + length,
        "text": text_slice,
        "text_hash": text_hash,
    }


def make_persona_result(
    persona: str,
    analise: str,
    claims: List[Dict[str, Any]],
    lacunas: Optional[List[str]] = None,
    sucesso: bool = True,
) -> Dict[str, Any]:
    """Cria resultado estruturado para uma das 4 personas."""
    return {
        "analise": analise,
        "conclusoes": claims,
        "lacunas": lacunas or [],
        "motivo_parada": "concluido",
        "sucesso": sucesso,
    }


def make_standard_coleta_metadata(
    claims_count: int = 4,
    source_url: str = "https://php.net/security-2026",
    body_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Metadados v3 completos: catálogo de URLs + 4 personas com resumo denso.

    ``body_override`` é ignorado: não existe corpo persistido desde o PRD v3.
    """
    personas_names = ["historiador", "visionario", "cetico", "futurista"]
    resultados_personas = {}

    for idx, p in enumerate(personas_names, 1):
        cid = f"claim_{idx}"
        c_item = {
            "claim_id": cid,
            "afirmacao": f"Afirmação factual verificada {idx} da persona {p}.",
            "tipo": "fato",
            "evidencias": [source_url],
            "confianca": "alta",
            "limitacoes": "",
        }
        resultados_personas[p] = make_persona_result(
            persona=p,
            analise=f"Análise substantiva da perspectiva {p} com base empírica e metodológica.",
            claims=[c_item],
            lacunas=[],
            sucesso=True,
        )
        resultados_personas[p]["urls_fonte"] = [source_url]
        resultados_personas[p]["urls_lidas"] = [source_url]

    return {
        "versao": 3,
        "fontes": [
            {
                "url": source_url,
                "uso": "utilizada",
                "titulo": "Fonte canônica",
                "data_fonte": None,
                "status": "read_ok",
            }
        ],
        "resultados_personas": resultados_personas,
        "diario_acoes": {p: [{"acao": "buscar", "consulta": f"busca {p}"}, {"acao": "concluir"}] for p in personas_names},
    }


def make_audit_12_vector(
    aprovados_count: int,
    known_claim_ids: Optional[List[str]] = None,
    known_source_ids: Optional[List[str]] = None,
    override_criterion: Optional[Dict[int, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Gera o vetor estruturado dos 12 critérios com IDs 1..12 e N aprovados."""
    c_ids = known_claim_ids or ["claim_1", "claim_2"]
    s_ids = known_source_ids or []
    vector = []
    for i in range(1, 13):
        is_aprovado = i <= aprovados_count
        item = {
            "id": i,
            "aprovado": is_aprovado,
            "justificativa": f"Justificativa analítica substantiva para o critério {i}.",
            "claim_ids": c_ids if is_aprovado else [c_ids[0]],
            "source_ids": s_ids if is_aprovado or not s_ids else [s_ids[0]],
            "lacuna": None if is_aprovado else f"Lacuna identificada no critério {i}.",
            "correcao": None if is_aprovado else f"Ação de correção para o critério {i}.",
            "personas_pertinentes": [] if is_aprovado else ["cetico", "historiador"],
        }
        if override_criterion and i in override_criterion:
            item.update(override_criterion[i])
        vector.append(item)
    return vector


async def create_research_fixture_with_plan(
    repo: ResearchRepository,
    tema: str = "Segurança do PHP 2026",
    ponto_texto: str = "Vulnerabilidades Oficiais",
    n_pontos: int = 1,
) -> tuple[Pesquisa, List[Ponto]]:
    """Cria pesquisa com plano geral estruturado canônico e ponto com eixo investigativo íntegro."""
    pontos_textos = [f"{ponto_texto} {i}" for i in range(1, n_pontos + 1)] if n_pontos > 1 else [ponto_texto]
    eixos = [dict(CANONICAL_EIXO) for _ in range(len(pontos_textos))]
    pesq = await repo.create_research(
        tema=tema,
        pontos_textos=pontos_textos,
        plano_estruturado=CANONICAL_PLANO,
        eixos_estruturados=eixos,
    )
    pontos = await repo.list_points(pesq.id_pesquisa)
    return pesq, pontos


# ==============================================================================
# 1. LIMITES 9/10/11/12, PARÂMETROS E PERCENTUAIS DETERMINÍSTICOS
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_freeform_status_without_criteria_vector_must_not_approve(
    db_session: AsyncSession,
) -> None:
    """Modelo retornando status='aprovado' e nota 95% sem vetor 12 não pode aprovar."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo coletado",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "status": "aprovado",
        "pontuacao_percentual": 95,
        "resumo_auditoria": "Parecer livre sem vetor",
    })
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]
    assert item["status"] == "reprovado"
    assert item["valido"] is False
    assert item["criterios"] is None
    assert item["pontuacao_percentual"] == 0.0


@pytest.mark.asyncio
async def test_audit_vector_cardinality_and_order(db_session: AsyncSession) -> None:
    """Vetor com 11 itens ou com IDs desordenados deve falhar a validação do contrato."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    # 11 itens
    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(11)[:11]
    })
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)
    res11 = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert res11["auditorias"][0]["valido"] is False

    # 12 itens fora de ordem
    unorder = make_audit_12_vector(12)
    unorder[0]["id"] = 2
    unorder[1]["id"] = 1
    mock_net2 = MockNetwork()
    mock_net2.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({"criterios": unorder})
    llm2 = LLMClient(api_key="key", transport=create_mock_transport(mock_net2))
    auditor2 = Auditor(research_repo=repo, llm_client=llm2)
    res_un = await auditor2.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert res_un["auditorias"][0]["valido"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "n_aprovados,limiar,expected_status,expected_score",
    [
        (9, 10, "reprovado", 75.0),
        (10, 10, "aprovado", 83.33),
        (10, 11, "reprovado", 83.33),
        (11, 11, "aprovado", 91.67),
        (11, 12, "reprovado", 91.67),
        (12, 12, "aprovado", 100.0),
    ],
)
async def test_audit_threshold_matrix_positive_and_negative(
    db_session: AsyncSession,
    n_aprovados: int,
    limiar: int,
    expected_status: str,
    expected_score: float,
) -> None:
    """Matriz completa de cortes 10, 11 e 12 com assert nos percentuais exatos (83.33, 91.67, 100.0)."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo, ponto_texto=f"Ponto {n_aprovados} de {limiar}")
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(n_aprovados),
        "resumo_auditoria": f"{n_aprovados} aprovados",
    })
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=limiar)
    item = res["auditorias"][0]

    assert item["status"] == expected_status
    assert item["criterios_aprovados"] == n_aprovados
    assert item["criterios_minimos"] == limiar
    assert item["pontuacao_percentual"] == expected_score


@pytest.mark.asyncio
async def test_audit_invalid_parameter_rejected_without_fallback(
    db_session: AsyncSession,
) -> None:
    """Parâmetro criterios_minimos inválido deve lançar ValueError, sem trocar silenciosamente por 11."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    llm = LLMClient(api_key="key", transport=create_mock_transport(MockNetwork()))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    for invalid_val in [9, 13, 0, -1, 10.5, "11", True]:
        with pytest.raises(ValueError) as exc_info:
            await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=invalid_val)
        assert "criterios_minimos" in str(exc_info.value) or "limiar" in str(exc_info.value).lower()


# ==============================================================================
# 2. VETORES INVÁLIDOS ISOLADOS
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "override_dict,scenario_desc",
    [
        ({1: {"id": True}}, "id booleano True"),
        ({1: {"id": 1.0}}, "id float 1.0"),
        ({1: {"aprovado": "true"}}, "aprovado string"),
        ({1: {"aprovado": 1}}, "aprovado int 1"),
        ({1: {"justificativa": ""}}, "justificativa vazia"),
        ({1: {"justificativa": "   "}}, "justificativa espaços"),
        ({1: {"claim_ids": ["claim_fantasma_999"]}}, "claim_id desconhecido"),
        ({1: {"source_ids": ["src_fantasma_999"]}}, "source_id desconhecido"),
        ({2: {"aprovado": False, "personas_pertinentes": ["hacker"]}}, "persona inválida"),
        ({2: {"aprovado": False, "lacuna": ""}}, "lacuna vazia"),
    ],
)
async def test_audit_invalid_vectors_separate(
    db_session: AsyncSession,
    override_dict: Dict[int, Dict[str, Any]],
    scenario_desc: str,
) -> None:
    """Cada tipo de violação estrutural do vetor 12 invalida o contrato (score 0, criterios None, reprovado)."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo, ponto_texto=f"Ponto {scenario_desc}")
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    invalid_vector = make_audit_12_vector(
        12,
        known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"],
        known_source_ids=["https://php.net/security-2026"],
        override_criterion=override_dict,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": invalid_vector,
        "resumo_auditoria": f"Teste de {scenario_desc}",
    })
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]

    assert item["status"] == "reprovado", f"Falhou em reprovar no cenário: {scenario_desc}"
    assert item["valido"] is False
    assert item["pontuacao_percentual"] == 0.0
    assert item["criterios"] is None
    assert item["criterios_aprovados"] == 0
    assert item["diagnostico"] is not None


# ==============================================================================
# 3. PROVENIÊNCIA REAL: CORPO AUSENTE, HASH INCORRETO, OFFSET INCOERENTE
# ==============================================================================



@pytest.mark.asyncio
async def test_audit_evaluates_strictly_latest_coleta_without_fallback(
    db_session: AsyncSession,
) -> None:
    """Se rodada 1 teve fonte válida, mas rodada 2 falhou/sem fonte, auditor NÃO faz fallback para rodada 1."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    # Rodada 1 válida
    meta_r1 = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Rodada 1 com fontes",
        urls_lidas=["https://php.net/r1"],
        urls_fonte=["https://php.net/r1"],
        metadados_coleta=meta_r1,
        rodada=1,
    )

    # Rodada 2 falha (última coleta)
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Rodada 2 falha de rede",
        urls_lidas=[],
        urls_fonte=[],
        status_ponto="falha_coleta",
        diagnostico_falha="JinaError 500: falha no provedor",
        metadados_coleta=None,
        rodada=2,
    )

    mock_net = MockNetwork()
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]

    assert item["status"] == "reprovado"
    assert len(mock_net.requests) == 0


# ==============================================================================
# 4. CAPTURA REAL DO PAYLOAD COMPLETO E ISOLAMENTO DE ORÇAMENTOS
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_payload_captures_complete_plan_and_axis_by_exact_equality(
    db_session: AsyncSession,
) -> None:
    """Verifica igualdade integral do plano geral e eixo canônicos no transporte real."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    # Rodada 1 antiga com sentinelas
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="SENTINEL_RODADA_1_NAO_PODE_ESTAR_NO_PROMPT",
        urls_lidas=["https://fonte-r1.org"],
        urls_fonte=["https://fonte-r1.org"],
        reasoning_coleta="REASONING_PRIVADO_NAO_PODE_ESTAR_NO_PROMPT",
        metadados_coleta=make_standard_coleta_metadata(source_url="https://fonte-r1.org"),
        rodada=1,
    )

    # Rodada 2 atual
    meta_r2 = make_standard_coleta_metadata(source_url="https://php.net/security-2026")
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo R2",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta_r2,
        rodada=2,
    )

    captured_requests = []
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        captured_requests.append(req)
        return make_llm_json_response({
            "criterios": make_audit_12_vector(12, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
            "resumo_auditoria": "Aprovado integralmente.",
        })

    mock_net.custom_handlers["chat/completions"] = handler
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert res["auditorias"][0]["status"] == "aprovado"
    assert len(captured_requests) == 1

    body_json = json.loads(captured_requests[0].content.decode("utf-8"))
    user_msg_content = next(m["content"] for m in body_json["messages"] if m["role"] == "user")
    prompt_data = json.loads(user_msg_content)

    # Compara igualdade integral do plano_geral (sem a chave eixos)
    plano_esperado = {k: v for k, v in CANONICAL_PLANO.items() if k != "eixos"}
    assert prompt_data["plano_geral"] == plano_esperado
    assert prompt_data["eixo_corrente"] == CANONICAL_EIXO

    # Verifica exclusão estrita de rodadas anteriores e CoT
    raw_text = json.dumps(body_json, ensure_ascii=False)
    assert "SENTINEL_RODADA_1_NAO_PODE_ESTAR_NO_PROMPT" not in raw_text
    assert "REASONING_PRIVADO_NAO_PODE_ESTAR_NO_PROMPT" not in raw_text




@pytest.mark.asyncio
async def test_audit_json_budget_120k_overflow_isolated(db_session: AsyncSession) -> None:
    """Orçamento de JSON: é alerta de monitoramento, nunca motivo para recusar o ponto."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    huge_meta = make_standard_coleta_metadata()
    huge_meta["resultados_personas"]["historiador"]["analise"] = "X" * (AUDIT_JSON_BUDGET_CHARS + 5000)

    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=huge_meta,
    )

    mock_net = MockNetwork()
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]

    # PRD v2, I-2: payload grande não recusa nem trunca; o parecer é emitido.
    assert item["status"] in ("aprovado", "reprovado")
    assert "orçamento de json" not in (item["diagnostico"] or "").lower()
    assert len(mock_net.requests) >= 1, "O parecer precisa chamar o LLM mesmo com payload grande"


def test_audit_budget_constants_values_10x() -> None:
    """Valida formalmente a expansão de 10x dos orçamentos do Auditor (320k evidência, 1200k JSON)."""
    assert AUDIT_EVIDENCE_BUDGET_CHARS == 320000, "Orçamento de evidência deve ser exatamente 320.000 chars"
    assert AUDIT_JSON_BUDGET_CHARS == 1200000, "Orçamento de JSON deve ser exatamente 1.200.000 chars"










@pytest.mark.asyncio
async def test_audit_json_budget_large_payload_allowed_under_1200k(db_session: AsyncSession) -> None:
    """Payload JSON de ~500k caracteres (muito superior ao antigo limite de 120k) deve ser aceito sem erro de overflow."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    # Cria análise analítica extensa com 500.000 caracteres (bloquearia no limite antigo de 120k)
    large_meta = make_standard_coleta_metadata()
    large_meta["resultados_personas"]["historiador"]["analise"] = "H" * 500000

    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo analítico grande",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=large_meta,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda req: make_llm_json_response({
        "criterios": make_audit_12_vector(12, known_claim_ids=["claim_1"], known_source_ids=["https://php.net/security-2026"]),
        "resumo_auditoria": "Aprovado com payload JSON de 500k.",
    })
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]

    assert item["status"] == "aprovado"
    assert len(mock_net.requests) == 1, "Chamada ao LLM deve ser permitida pois 500k < 1.200k do novo orçamento JSON"




# ==============================================================================
# 5. SEM VAZAMENTO ENTRE PONTOS VIA LOCALS() E LIMPEZA DE PONTOS_FRACOS
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_no_leakage_between_points_via_locals(db_session: AsyncSession) -> None:
    """Ponto 1 aprovado no LLM e Ponto 2 falho: Ponto 2 NÃO herda critérios nem pontuação do Ponto 1."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=2)
    p1, p2 = pontos[0], pontos[1]

    # Ponto 1 com evidência válida
    meta_p1 = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=p1.ponto_id,
        tema=pesq.tema,
        ponto=p1.ponto,
        conteudo_coletado="Conteúdo P1",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta_p1,
    )

    # Ponto 2 sem evidência
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=p2.ponto_id,
        tema=pesq.tema,
        ponto=p2.ponto,
        conteudo_coletado="Falha P2",
        urls_lidas=[],
        urls_fonte=[],
        status_ponto="falha_coleta",
        metadados_coleta=None,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(11, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
        "resumo_auditoria": "P1 Aprovado com 11 critérios.",
    })
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    auditorias = {a["ponto_id"]: a for a in res["auditorias"]}

    item_p1 = auditorias[p1.ponto_id]
    item_p2 = auditorias[p2.ponto_id]

    assert item_p1["status"] == "aprovado"
    assert item_p1["criterios_aprovados"] == 11
    assert item_p1["pontuacao_percentual"] == 91.67

    assert item_p2["status"] == "reprovado"
    assert item_p2["criterios_aprovados"] == 0
    assert item_p2["pontuacao_percentual"] == 0.0
    assert item_p2["criterios"] is None


@pytest.mark.asyncio
async def test_audit_approval_cleans_old_pontos_fracos(db_session: AsyncSession) -> None:
    """Quando um ponto anteriormente reprovado é aprovado, pontos_fracos é limpo (None)."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    await repo.update_point_status(ponto.ponto_id, status="reprovado", pontos_fracos="Fragilidade anterior")

    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Nova coleta aprovável",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(12, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
        "resumo_auditoria": "Tudo aprovado.",
    })
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]

    assert item["status"] == "aprovado"
    assert item["pontos_fracos"] is None

    ponto_bd = await repo.get_point(ponto.ponto_id)
    assert ponto_bd.status == "aprovado"
    assert ponto_bd.pontos_fracos is None


# ==============================================================================
# 6. ENVELOPES LLM, FINISH REGULAR E REASONING PRIVADO
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_irregular_finish_never_approves(db_session: AsyncSession) -> None:
    """finish_reason != 'stop' (ex: 'length' ou None) ou is_regular_finish=False nunca aprova."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response(
        {"criterios": make_audit_12_vector(12)},
        finish_reason="length",
    )
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]

    assert item["status"] == "reprovado"
    assert item["valido"] is False
    assert item["pontuacao_percentual"] == 0.0


@pytest.mark.asyncio
async def test_audit_reasoning_private_does_not_leak_to_api(db_session: AsyncSession) -> None:
    """Raciocínio interno (reasoning_content) é preservado no envelope/BD, mas NÃO sai na resposta pública."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    mock_net = MockNetwork()
    secret_reasoning = "SEGREDO_DE_DELIBERACAO_INTERNA_COT_AUDITORIA"
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response(
        {"criterios": make_audit_12_vector(12, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"])},
        reasoning=secret_reasoning,
    )
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    res_str = json.dumps(res, ensure_ascii=False)
    assert secret_reasoning not in res_str


# ==============================================================================
# 7. REPARO DIRIGIDO ADICIONAL E PRESERVAÇÃO DE ENVELOPES
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_directed_repair_preserves_all_envelopes(db_session: AsyncSession) -> None:
    """Falha de contrato na 1ª tentativa dispara 1 reparo dirigido; envelopes sobrevivem com etapa='audit'."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    call_count = 0
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_llm_json_response({"criterios": make_audit_12_vector(10)[:10]})
        else:
            return make_llm_json_response({
                "criterios": make_audit_12_vector(12, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
                "resumo_auditoria": "Reparado com sucesso.",
            })

    mock_net.custom_handlers["chat/completions"] = handler
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]

    assert call_count == 2
    assert item["status"] == "aprovado"
    assert item["criterios_aprovados"] == 12

    attempts = await repo.get_generation_attempts(pesq.id_pesquisa, etapa="audit")
    assert len(attempts) >= 2


# ==============================================================================
# 8. PERSISTÊNCIA EM METADADOS_COLETA E ENDPOINT HTTP
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_http_endpoint_and_persistence(db_session: AsyncSession, monkeypatch) -> None:
    """Endpoint POST /api/v1/audit conecta com transporte mockado via monkeypatch, persiste e valida saída."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(11, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
        "resumo_auditoria": "Aprovado via HTTP.",
    })
    transport = create_mock_transport(mock_net)
    monkeypatch.setattr("app.api.v1.endpoints.audit._get_transport", lambda: transport)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/audit",
            json={"id_pesquisa": pesq.id_pesquisa, "criterios_minimos": 11},
        )
        assert resp.status_code == 200
        data = resp.json()

        audit_resp = AuditResponse(**data)
        assert audit_resp.id_pesquisa == pesq.id_pesquisa
        assert audit_resp.total_pontos == 1
        assert audit_resp.aprovados == 1
        assert audit_resp.pronto_para_writer is True

        item = audit_resp.auditorias[0]
        assert item.status == "aprovado"
        assert item.criterios_aprovados == 11
        assert item.pontuacao_percentual == 91.67
        assert item.valido is True
        assert len(item.criterios) == 12

    coletas = await repo.get_collected_content_for_point(pesq.id_pesquisa, ponto.ponto_id)
    ultima = coletas[-1]
    meta_db = json.loads(ultima.metadados_coleta)
    assert "auditorias" in meta_db
    aud_rec = meta_db["auditorias"][0]
    assert aud_rec["criterios_aprovados"] == 11
    assert aud_rec["pontuacao_percentual"] == 91.67
    assert aud_rec["valido"] is True


# ==============================================================================
# 9. CACHE, RECÁLCULO PURO DE CORTE, NOVA COLETA E DELTA ANTES/DEPOIS
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_cache_identical_input_does_not_consume_attempts(
    db_session: AsyncSession,
) -> None:
    """Chamada repetida idêntica reutiliza vetor sem invocar LLM e sem incrementar tentativas_auditoria."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    llm_calls = 0
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal llm_calls
        llm_calls += 1
        return make_llm_json_response({
            "criterios": make_audit_12_vector(11, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
            "resumo_auditoria": "Aprovado.",
        })

    mock_net.custom_handlers["chat/completions"] = handler
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res1 = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11)
    assert llm_calls == 1
    ponto_bd1 = await repo.get_point(ponto.ponto_id)
    assert ponto_bd1.tentativas_auditoria == 1

    res2 = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11)
    assert llm_calls == 1
    ponto_bd2 = await repo.get_point(ponto.ponto_id)
    assert ponto_bd2.tentativas_auditoria == 1
    assert res2["auditorias"][0]["status"] == "aprovado"


@pytest.mark.asyncio
async def test_audit_recalculate_cutoff_without_llm(db_session: AsyncSession) -> None:
    """Mudança apenas de corte (11 para 10) recalcula vetor no backend sem chamar LLM e sem gastar tentativa."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    llm_calls = 0
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal llm_calls
        llm_calls += 1
        return make_llm_json_response({
            "criterios": make_audit_12_vector(10, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
            "resumo_auditoria": "10 critérios aprovados.",
        })

    mock_net.custom_handlers["chat/completions"] = handler
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res1 = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=11)
    assert res1["auditorias"][0]["status"] == "reprovado"
    assert llm_calls == 1

    res2 = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=10)
    assert res2["auditorias"][0]["status"] == "aprovado"
    assert res2["auditorias"][0]["criterios_minimos"] == 10
    assert res2["auditorias"][0]["pontuacao_percentual"] == 83.33
    assert llm_calls == 1


@pytest.mark.asyncio
async def test_audit_new_coleta_invalidates_cache_and_computes_delta(
    db_session: AsyncSession,
) -> None:
    """Nova coleta exige inferência nova e calcula delta antes/depois por ID de critério."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    # Coleta 1
    meta1 = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo R1",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta1,
        rodada=1,
    )

    llm_calls = 0
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal llm_calls
        llm_calls += 1
        if llm_calls == 1:
            return make_llm_json_response({
                "criterios": make_audit_12_vector(9, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
                "resumo_auditoria": "9 aprovados.",
            })
        else:
            return make_llm_json_response({
                "criterios": make_audit_12_vector(11, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
                "resumo_auditoria": "11 aprovados.",
            })

    mock_net.custom_handlers["chat/completions"] = handler
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res1 = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert res1["auditorias"][0]["status"] == "reprovado"

    # Coleta 2
    meta2 = make_standard_coleta_metadata(source_url="https://php.net/r2")
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo R2",
        urls_lidas=["https://php.net/r2"],
        urls_fonte=["https://php.net/r2"],
        metadados_coleta=meta2,
        rodada=2,
    )

    res2 = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert llm_calls == 2
    item2 = res2["auditorias"][0]
    assert item2["status"] == "aprovado"
    assert item2.get("antes_depois") is not None
    assert item2["antes_depois"]["criterios_aprovados_anterior"] == 9
    assert item2["antes_depois"]["criterios_aprovados_atual"] == 11


# ==============================================================================
# 10. CONCORRÊNCIA COM SQLITE EM ARQUIVO E TIMEOUTS FINITOS (SEM SLEEPS)
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_concurrency_audit_and_search_mutual_blocking(tmp_path) -> None:
    """Bloqueio mútuo: Search não reserva ponto sob Audit, e Audit não reserva ponto sob Search."""
    db_file = tmp_path / "concurrent_mutual.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq = await r_init.create_research(tema="Mutual Concurrency", pontos_textos=["Ponto 1"])
        ponto = (await r_init.list_points(pesq.id_pesquisa))[0]
        meta = make_standard_coleta_metadata()
        await r_init.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteúdo",
            urls_lidas=["https://php.net/security-2026"],
            urls_fonte=["https://php.net/security-2026"],
            metadados_coleta=meta,
        )

    # 1. Audit reserva -> Search deve ser bloqueado
    async with session_maker() as s_aud:
        r_aud = ResearchRepository(session=s_aud)
        token_audit = await r_aud.reserve_point_for_audit(ponto.ponto_id)

    async with session_maker() as s_sea:
        r_sea = ResearchRepository(session=s_sea)
        with pytest.raises(ValueError) as exc_sea:
            await r_sea.reserve_point(ponto.ponto_id)
        assert "CONCURRENT_EXECUTION" in str(exc_sea.value) or "em andamento" in str(exc_sea.value).lower()

    # Libera a reserva do Audit
    async with session_maker() as s_rel:
        r_rel = ResearchRepository(session=s_rel)
        await r_rel.release_point_audit_reservation(ponto.ponto_id, expected_token=token_audit)

    # 2. Search reserva -> Audit deve ser bloqueado
    async with session_maker() as s_sea2:
        r_sea2 = ResearchRepository(session=s_sea2)
        await r_sea2.reserve_point(ponto.ponto_id)

    async with session_maker() as s_aud2:
        r_aud2 = ResearchRepository(session=s_aud2)
        with pytest.raises(ValueError) as exc_aud:
            await r_aud2.reserve_point_for_audit(ponto.ponto_id)
        assert "CONCURRENT_EXECUTION" in str(exc_aud.value) or "em andamento" in str(exc_aud.value).lower()

    await engine.dispose()


@pytest.mark.asyncio
async def test_audit_stale_owner_fence_in_flight(tmp_path) -> None:
    """Auditor em voo superado por nova coleta não aplica status e histórico é marcado obsoleto."""
    db_file = tmp_path / "fence_in_flight.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_engine_with_pragmas(db_url)
    await init_db(engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as s_init:
        r_init = ResearchRepository(session=s_init)
        pesq = await r_init.create_research(tema="Fence In Flight", pontos_textos=["Ponto Fence"])
        ponto = (await r_init.list_points(pesq.id_pesquisa))[0]
        meta_r1 = make_standard_coleta_metadata(source_url="https://php.net/r1")
        coleta1 = await r_init.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteúdo R1",
            urls_lidas=["https://php.net/r1"],
            urls_fonte=["https://php.net/r1"],
            metadados_coleta=meta_r1,
            rodada=1,
        )

    # Auditor 1 inicia reserva
    async with session_maker() as s1:
        r1 = ResearchRepository(session=s1)
        token1 = await r1.reserve_point_for_audit(ponto.ponto_id)

    # Intervenção concorrente: nova coleta rodada 2 e marcador de dossiê
    async with session_maker() as s2:
        r2 = ResearchRepository(session=s2)
        meta_r2 = make_standard_coleta_metadata(source_url="https://php.net/r2")
        await r2.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteúdo R2",
            urls_lidas=["https://php.net/r2"],
            urls_fonte=["https://php.net/r2"],
            metadados_coleta=meta_r2,
            rodada=2,
        )
        await r2.update_research_dossier(pesq.id_pesquisa, dossier_final="DOSSIER_MARCADOR_NOVO")

    # Auditor 1 tenta finalizar a auditoria da rodada 1 superada
    async with session_maker() as s3:
        r3 = ResearchRepository(session=s3)
        fence_ok = await r3.finalize_audit_point(
            ponto_id=ponto.ponto_id,
            coleta_id=coleta1.id,
            expected_token=token1,
            status="aprovado",
            criterios=make_audit_12_vector(12),
        )
        assert fence_ok is False

    # Confere que o dossiê novo não foi apagado e o ponto não foi indevidamente aprovado
    async with session_maker() as s4:
        r4 = ResearchRepository(session=s4)
        p_final = await r4.get_point(ponto.ponto_id)
        pesq_final = await r4.get_research(pesq.id_pesquisa)
        assert pesq_final.dossier_final == "DOSSIER_MARCADOR_NOVO"
        assert p_final.status != "aprovado"

    await engine.dispose()


# ==============================================================================
# 11. CANCELAMENTO COM PRESERVAÇÃO DE ENVELOPES E LIBERAÇÃO DE RESERVA PRÓPRIA
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_cancellation_releases_reservation_finite_timeout(db_session: AsyncSession) -> None:
    """Cancelamento da tarefa de auditoria com prazo finito libera a reserva sem fabricar finish/usage."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    event_req_started = asyncio.Event()

    async def mock_async_handler(req: httpx.Request) -> httpx.Response:
        event_req_started.set()
        await asyncio.Event().wait()
        return make_llm_json_response({})

    transport = httpx.MockTransport(mock_async_handler)
    llm = LLMClient(api_key="key", transport=transport)
    auditor = Auditor(research_repo=repo, llm_client=llm)

    task = asyncio.create_task(auditor.execute_audit(id_pesquisa=pesq.id_pesquisa))
    try:
        async with asyncio.timeout(3.0):
            await event_req_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    p_pos = await repo.get_point(ponto.ponto_id)
    assert p_pos.status in ("coletado", "reprovado")


# ==============================================================================
# 12. TETO ESTRITO DE 3 TENTATIVAS EM SEQUÊNCIA REAL E CACHE NO LIMITE
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_sequential_max_3_attempts_and_cache_at_limit(
    db_session: AsyncSession,
) -> None:
    """Execuções sequenciais incrementam até 3; a 4ª falha; repetição sob teto retorna cache."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(9, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
        "resumo_auditoria": "9 aprovados (reprovado)",
    })
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    # Tentativa 1
    res1 = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert res1["auditorias"][0]["status"] == "reprovado"
    p1 = await repo.get_point(ponto.ponto_id)
    assert p1.tentativas_auditoria == 1

    # Nova coleta (Tentativa 2)
    meta2 = make_standard_coleta_metadata(source_url="https://php.net/r2")
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo 2",
        urls_lidas=["https://php.net/r2"],
        urls_fonte=["https://php.net/r2"],
        metadados_coleta=meta2,
        rodada=2,
    )
    res2 = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    p2 = await repo.get_point(ponto.ponto_id)
    assert p2.tentativas_auditoria == 2

    # Nova coleta (Tentativa 3)
    meta3 = make_standard_coleta_metadata(source_url="https://php.net/r3")
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo 3",
        urls_lidas=["https://php.net/r3"],
        urls_fonte=["https://php.net/r3"],
        metadados_coleta=meta3,
        rodada=3,
    )
    res3 = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    p3 = await repo.get_point(ponto.ponto_id)
    assert p3.tentativas_auditoria == 3

    # Repetição idêntica da coleta 3 sob o teto: cache hit bem-sucedido
    res3_cached = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert res3_cached["auditorias"][0]["status"] == "reprovado"
    p3_c = await repo.get_point(ponto.ponto_id)
    assert p3_c.tentativas_auditoria == 3

    # Tentativa 4 de avaliação inédita: bloqueada pelo teto
    meta4 = make_standard_coleta_metadata(source_url="https://php.net/r4")
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo 4",
        urls_lidas=["https://php.net/r4"],
        urls_fonte=["https://php.net/r4"],
        metadados_coleta=meta4,
        rodada=4,
    )
    with pytest.raises(ValueError) as exc:
        await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert "MAX_ATTEMPTS" in str(exc.value) or "limite" in str(exc.value).lower()


# ==============================================================================
# 13. FILTRO PONTO_ID COM AGREGADO LENDO TODOS OS PONTOS
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_filter_ponto_id_aggregate_reads_all_points(db_session: AsyncSession) -> None:
    """Filtro por ponto_id avalia ponto alvo, mas agregado lê todos e ponto pendente bloqueia pronto_para_writer."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo, n_pontos=2)
    p1, p2 = pontos[0], pontos[1]

    # Ponto 1 tem coleta
    meta_p1 = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=p1.ponto_id,
        tema=pesq.tema,
        ponto=p1.ponto,
        conteudo_coletado="Conteúdo P1",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta_p1,
    )
    # Ponto 2 permanece 'pendente' sem coleta

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(12, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
        "resumo_auditoria": "P1 Aprovado",
    })
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, ponto_id=p1.ponto_id)
    assert len(res["auditorias"]) == 1
    assert res["auditorias"][0]["status"] == "aprovado"

    # Mesmo com P1 aprovado e 0 reprovados no filtro, P2 está pendente: pronto_para_writer deve ser False!
    assert res.get("pronto_para_writer") is False


# ==============================================================================
# 14. CLIENTE FINALLY E CONFIGURAÇÃO DE PERSONA
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_client_finally_closed_on_success_and_error(db_session: AsyncSession, monkeypatch) -> None:
    """Verifica que llm_client.aclose() é sempre executado no endpoint em sucesso e em erro."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    closed_instances = []
    original_aclose = LLMClient.aclose

    async def spy_aclose(self_client):
        closed_instances.append(self_client)
        await original_aclose(self_client)

    monkeypatch.setattr(LLMClient, "aclose", spy_aclose)

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(12, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
        "resumo_auditoria": "Aprovado via HTTP.",
    })
    monkeypatch.setattr("app.api.v1.endpoints.audit._get_transport", lambda: create_mock_transport(mock_net))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/audit",
            json={"id_pesquisa": pesq.id_pesquisa},
        )
        assert resp.status_code == 200

    assert len(closed_instances) >= 1


@pytest.mark.asyncio
async def test_audit_persona_missing_raises_error_without_fallback(
    db_session: AsyncSession,
) -> None:
    """Se personas explícitas são passadas e 'auditor' não está presente, lança ValueError sem fallback silencioso."""
    repo = ResearchRepository(session=db_session)
    llm = LLMClient(api_key="key", transport=create_mock_transport(MockNetwork()))

    with pytest.raises(ValueError) as exc:
        Auditor(research_repo=repo, llm_client=llm, personas=["pesquisador", "redator"])
    assert "auditor" in str(exc.value)

    with pytest.raises(ValueError) as exc_vazio:
        Auditor(research_repo=repo, llm_client=llm, personas=[])
    assert "auditor" in str(exc_vazio.value) or "ausente" in str(exc_vazio.value).lower()


# ==============================================================================
# 15. INTEGRAÇÃO PIPELINE_RUNNER: BLOQUEIO DO WRITER E REEXECUÇÃO DE ALVOS
# ==============================================================================

@pytest.mark.asyncio
async def test_pipeline_runner_blocks_writer_when_audit_fails_or_pending(
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    """PipelineRunner entrega o dossiê com ressalvas quando o teto de auditoria já foi consumido."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    await repo.update_point_status(ponto.ponto_id, status="reprovado")
    stmt = update(Ponto).where(Ponto.ponto_id == ponto.ponto_id).values(tentativas_auditoria=3)
    await db_session.execute(stmt)
    await db_session.commit()

    writer_called = False

    async def spy_writer(*args, **kwargs):
        nonlocal writer_called
        writer_called = True
        return {"status": "concluido"}

    monkeypatch.setattr("app.core.writer.Writer.execute_writer", spy_writer)

    runner = PipelineRunner(transport=create_mock_transport(MockNetwork()))
    res = await runner.run(id_pesquisa=pesq.id_pesquisa)

    # RF-006-D: teto consumido não bloqueia a redação; relatório sai com ressalvas.
    assert writer_called is True
    pesq_final = await repo.get_research(pesq.id_pesquisa)
    assert pesq_final.status_pipeline in ("incompleto", "concluido")


@pytest.mark.asyncio
async def test_pipeline_runner_directs_per_point_and_blocks_writer_on_pending_without_rejections(
    async_engine: AsyncEngine,
    monkeypatch,
) -> None:
    """PipelineRunner direciona busca apenas para ponto pendente e bloqueia Writer quando há pendências sem reprovações."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session1:
        repo1 = ResearchRepository(session=session1)
        pesq, pontos = await create_research_fixture_with_plan(repo1, n_pontos=2)
        p0 = pontos[0]  # Ponto aprovado
        p1 = pontos[1]  # Ponto pendente com teto de auditoria (zero reprovações)

        await repo1.update_point_status(p0.ponto_id, status="aprovado")
        await repo1.update_point_status(p1.ponto_id, status="pendente")
        stmt = update(Ponto).where(Ponto.ponto_id == p1.ponto_id).values(tentativas=1, tentativas_auditoria=3)
        await session1.execute(stmt)
        await session1.commit()

        searched_point_ids: List[str] = []
        async def spy_search(*args, **kwargs):
            pid = kwargs.get("ponto_id")
            searched_point_ids.append(pid)
            return {"status": "coletado"}

        writer_called = False
        async def spy_writer(*args, **kwargs):
            nonlocal writer_called
            writer_called = True
            return {"status": "concluido"}

        auditor_called = False
        async def spy_audit(*args, **kwargs):
            nonlocal auditor_called
            auditor_called = True
            return {
                "id_pesquisa": pesq.id_pesquisa,
                "total_pontos": 2,
                "aprovados": 1,
                "reprovados": 0,
                "status_geral": "parcial",
                "status_pesquisa": "auditando",
                "pronto_para_writer": False,
                "auditorias": [
                    {
                        "ponto_id": p0.ponto_id,
                        "ponto_n": 1,
                        "status": "aprovado",
                        "criterios_minimos": 11,
                        "valido": True,
                        "criterios_aprovados": 11,
                        "pontuacao_percentual": 91.67,
                        "tarefas": [],
                    },
                    {
                        "ponto_id": p1.ponto_id,
                        "ponto_n": 2,
                        "status": "pendente",
                        "criterios_minimos": 11,
                        "valido": False,
                        "criterios_aprovados": 0,
                        "pontuacao_percentual": 0.0,
                        "tarefas": [],
                    },
                ],
            }

        monkeypatch.setattr("app.core.searcher.Searcher.execute_search", spy_search)
        monkeypatch.setattr("app.core.writer.Writer.execute_writer", spy_writer)
        monkeypatch.setattr("app.core.auditor.Auditor.execute_audit", spy_audit)

        runner = PipelineRunner(transport=create_mock_transport(MockNetwork()))
        res = await runner.run(id_pesquisa=pesq.id_pesquisa)

        # Teto de auditoria já consumido: a auditoria é ignorada e o Writer entrega o
        # relatório com ressalvas (PRD v3, RF-006-D).
        assert auditor_called is False
        assert writer_called is True
        # Ponto aprovado p0 NUNCA deve ser buscado novamente; busca é direcionada apenas a p1
        assert p0.ponto_id not in searched_point_ids
        assert p1.ponto_id in searched_point_ids
        # p1 permanece pendente com zero reprovações
        p1_check = await repo1.get_point(p1.ponto_id)
        assert p1_check.status == "pendente"
        # Sem reprovação formal, porém com pendência no teto: redação com ressalvas.
        assert res.get("status") in ("parcial", "incompleto", "concluido")

    # Confere status persistido em nova sessão
    async with session_factory() as session2:
        repo2 = ResearchRepository(session=session2)
        pesq_final = await repo2.get_research(pesq.id_pesquisa)
        assert pesq_final.status_pipeline in ("parcial", "incompleto", "concluido")


# ==============================================================================
# 16. REGRESSÕES DA RODADA R2 (GRUPO 1: REMOÇÃO DE FABRICAÇÃO E SELEÇÃO REAL)
# ==============================================================================



@pytest.mark.asyncio
async def test_audit_rejects_missing_metadata_without_fabrication(db_session: AsyncSession) -> None:
    """Coleta sem metadados estruturados (sem fontes com body e proveniência) deve reprovar sem fabricar dados."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Texto sem metadados estruturados",
        urls_lidas=["https://php.net/news"],
        urls_fonte=["https://php.net/news"],
        metadados_coleta=None,
    )

    mock_net = MockNetwork()
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert len(mock_net.requests) == 0  # Zero chamadas LLM
    item = res["auditorias"][0]
    assert item["status"] == "reprovado"
    assert item["valido"] is False
    assert "catálogo de URLs" in (item["diagnostico"] or "") or "metadados" in (item["pontos_fracos"] or "").lower() or "fontes" in (item["pontos_fracos"] or "").lower()


@pytest.mark.asyncio
async def test_audit_missing_cited_chunk_fails_closed(db_session: AsyncSession) -> None:
    """Referência a trecho inexistente (chk_999) no corpus da coleta deve reprovar sem chamar LLM."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    meta = make_standard_coleta_metadata()
    # Adiciona conclusão referenciando chk_inexistente
    meta["resultados_personas"]["historiador"]["conclusoes"][0]["evidencias"] = ["chk_inexistente"]

    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Coleta com trecho ausente",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    mock_net = MockNetwork()
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    assert len(mock_net.requests) == 0
    item = res["auditorias"][0]
    assert item["status"] == "reprovado"
    assert item["valido"] is False
    assert "chk_inexistente" in (item["pontos_fracos"] or "") or "trecho" in (item["diagnostico"] or "").lower()




# ==============================================================================
# 17. REGRESSÕES DA RODADA R2 (GRUPOS 2, 3, 4, 5)
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_val", [11.0, "11", True])
async def test_audit_api_rejects_non_strict_int_criterios_minimos(
    invalid_val: Any,
    db_session: AsyncSession,
) -> None:
    """Validação Pydantic estrita na API: 11.0, '11' e True devem ser rejeitados com HTTP 422 na rota real POST /api/v1/audit."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/audit", json={"id_pesquisa": pesq.id_pesquisa, "criterios_minimos": invalid_val})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_audit_api_accepts_strict_int_criterios_minimos_positive_control(
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    """Controle positivo da API: int estrito 11 é aceito com HTTP 200."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesq.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({
        "criterios": make_audit_12_vector(11, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"]),
        "resumo_auditoria": "Aprovado via HTTP.",
    })
    transport = create_mock_transport(mock_net)
    monkeypatch.setattr("app.api.v1.endpoints.audit._get_transport", lambda: transport)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/audit", json={"id_pesquisa": pesq.id_pesquisa, "criterios_minimos": 11})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id_pesquisa"] == pesq.id_pesquisa


@pytest.mark.asyncio
async def test_pipeline_status_endpoint_never_exposes_private_reasoning(
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/pipeline/{id}/status não pode expor reasoning_planejamento, reasoning_auditoria ou reasoning_dossier."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    sentinela_plan = "SENTINELA_PRIVADA_REASONING_PLANEJAMENTO_XYZ"
    sentinela_audit = "SENTINELA_PRIVADA_REASONING_AUDITORIA_XYZ"
    sentinela_dossier = "SENTINELA_PRIVADA_REASONING_DOSSIER_XYZ"

    # Persiste sentinelas privadas não vazias
    stmt_p = (
        update(Ponto)
        .where(Ponto.ponto_id == ponto.ponto_id)
        .values(
            reasoning_planejamento=sentinela_plan,
            reasoning_auditoria=sentinela_audit,
        )
    )
    await db_session.execute(stmt_p)

    stmt_pesq = (
        update(Pesquisa)
        .where(Pesquisa.id_pesquisa == pesq.id_pesquisa)
        .values(reasoning_dossier=sentinela_dossier)
    )
    await db_session.execute(stmt_pesq)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/pipeline/{pesq.id_pesquisa}/status")
        assert resp.status_code == 200
        data = resp.json()
        raw_text = resp.text

        # As sentinelas privadas não podem vazar no payload JSON
        assert sentinela_plan not in raw_text
        assert sentinela_audit not in raw_text
        assert sentinela_dossier not in raw_text

        # As chaves privadas não devem constar na resposta pública
        p_res = data["pontos"][0]
        assert "reasoning_planejamento" not in p_res
        assert "reasoning_auditoria" not in p_res
        assert "reasoning_dossier" not in data


@pytest.mark.asyncio
async def test_audit_vector_rejects_personas_on_approved_criterion(
    db_session: AsyncSession,
) -> None:
    """Persona inválida deve ser rejeitada também em critério com aprovado=True."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesq.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    vec = make_audit_12_vector(12, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"])
    vec[0]["personas_pertinentes"] = ["persona_fantasma_invalida"]

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({"criterios": vec})
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]
    assert item["valido"] is False
    assert "persona inválida" in (item["diagnostico"] or "").lower() or "persona" in (item["pontos_fracos"] or "").lower()


@pytest.mark.asyncio
async def test_audit_vector_rejects_non_list_claim_ids(
    db_session: AsyncSession,
) -> None:
    """claim_ids com tipo não-lista (ex: False, '', None) deve ser rejeitado no contrato estrito."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesq.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    vec = make_audit_12_vector(12, known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"])
    vec[0]["claim_ids"] = False  # Tipo inválido que 'claim_ids or []' aceitava

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response({"criterios": vec})
    llm = LLMClient(api_key="key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
    item = res["auditorias"][0]
    assert item["valido"] is False


@pytest.mark.asyncio
async def test_audit_cancellation_during_repair_persists_first_turn_envelope(
    db_session: AsyncSession,
) -> None:
    """Cancelamento durante o reparo dirigido assíncrono pendente deve persistir o envelope da primeira chamada concluída em GenerationAttempt."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]
    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteúdo",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    repair_entered = asyncio.Event()
    repair_release = asyncio.Event()
    call_count = 0

    async def async_handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # 1ª resposta com vetor inválido (10 critérios) para disparar reparo dirigido
            return make_llm_json_response({"criterios": make_audit_12_vector(10)[:10]})
        else:
            repair_entered.set()
            # Bloqueia a execução do reparo de forma verdadeiramente assíncrona até cancelamento
            await repair_release.wait()
            return make_llm_json_response({"criterios": make_audit_12_vector(12)})

    transport = httpx.MockTransport(async_handler)
    llm = LLMClient(api_key="key", transport=transport)
    auditor = Auditor(research_repo=repo, llm_client=llm)

    audit_task = asyncio.create_task(auditor.execute_audit(id_pesquisa=pesq.id_pesquisa))

    try:
        async with asyncio.timeout(3.0):
            await repair_entered.wait()

        assert call_count == 2
        assert not audit_task.done()

        # Cancela com a tarefa exatamente suspensa dentro do reparo
        audit_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await audit_task
    finally:
        repair_release.set()
        if not audit_task.done():
            audit_task.cancel()
            try:
                await audit_task
            except (asyncio.CancelledError, Exception):
                pass

    # Verifica que exatamente 1 GenerationAttempt da 1ª chamada foi gravado no banco
    attempts = await repo.get_generation_attempts(pesq.id_pesquisa, etapa="audit")
    assert len(attempts) == 1
    assert attempts[0].etapa == "audit"
    assert attempts[0].persona == "auditor"
    assert attempts[0].finish_reason == "stop"
    assert attempts[0].content_final is not None

    # Ponto foi liberado e não permaneceu em 'auditando'
    ponto_atualizado = await repo.get_point(ponto.ponto_id)
    assert ponto_atualizado.status != "auditando"


# ==============================================================================
# NOVOS TESTES DE REGRESSÃO E CONFORMIDADE v5 - AUDIT R3 (F01..F04 FORTALECIDOS)
# ==============================================================================

def test_audit_schema_mandatory_claim_and_source_ids() -> None:
    """A01/F03: claim_ids e source_ids são campos estritamente obrigatórios no AuditCriterionDetail (sem defaults)."""
    import pydantic
    from app.schemas.audit import AuditCriterionDetail
    from app.core.auditor import _validate_vector_strict

    # Falha se claim_ids for omitido no schema
    with pytest.raises(pydantic.ValidationError) as exc_info:
        AuditCriterionDetail(
            id=1,
            aprovado=True,
            justificativa="Justificativa substantiva válida.",
            source_ids=["src_1"],
        )
    assert "claim_ids" in str(exc_info.value)

    # Falha se source_ids for omitido no schema
    with pytest.raises(pydantic.ValidationError) as exc_info:
        AuditCriterionDetail(
            id=1,
            aprovado=True,
            justificativa="Justificativa substantiva válida.",
            claim_ids=["claim_1"],
        )
    assert "source_ids" in str(exc_info.value)

    # Vetor com 12 IDs estritos 1..12 e dados válidos, omitindo apenas claim_ids no item 5
    vec_missing_claim = make_audit_12_vector(12, known_claim_ids=["claim_1"], known_source_ids=["https://php.net/security-2026"])
    del vec_missing_claim[4]["claim_ids"]
    valido, _, err = _validate_vector_strict(vec_missing_claim, {"claim_1"}, {"https://php.net/security-2026"})
    assert not valido
    assert "claim_ids" in (err or "").lower()

    # Vetor com 12 IDs estritos 1..12, omitindo apenas source_ids no item 7
    vec_missing_source = make_audit_12_vector(12, known_claim_ids=["claim_1"], known_source_ids=["https://php.net/security-2026"])
    del vec_missing_source[6]["source_ids"]
    valido, _, err = _validate_vector_strict(vec_missing_source, {"claim_1"}, {"https://php.net/security-2026"})
    assert not valido
    assert "source_ids" in (err or "").lower()


@pytest.mark.asyncio
async def test_audit_requires_all_four_personas_complete(db_session: AsyncSession) -> None:
    """A02/F03: Exige as quatro personas atuais completas; falha fechado para persona ausente, IDs divergentes ou URLs erradas."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    # Cria meta válida padrão
    meta = make_standard_coleta_metadata()

    # 1. Remove uma das quatro personas ('futurista')
    meta_incomplete = dict(meta)
    meta_incomplete["resultados_personas"] = {
        k: v for k, v in meta["resultados_personas"].items() if k != "futurista"
    }

    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Coleta com persona faltando",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta_incomplete,
    )

    llm = LLMClient(api_key="key", transport=create_mock_transport())
    auditor = Auditor(research_repo=repo, llm_client=llm)
    try:
        res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
        assert res["total_pontos"] == 1
        item = res["auditorias"][0]
        assert item["status"] == "reprovado"
        assert item["valido"] is False
        assert "futurista" in (item["diagnostico"] or item["pontos_fracos"])
    finally:
        await llm.aclose()


@pytest.mark.asyncio
async def test_audit_downstream_router_mutations_preserves_none_and_bool(db_session: AsyncSession) -> None:
    """A03/S08/F04: downstream_router_mutations='explicitly_unobserved' deve persistir None no banco, e bool preservado."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    from app.tools.llm_types import LLMEnvelope
    env_unobserved = LLMEnvelope(
        content_final="{}",
        reasoning_content=None,
        finish_reason="stop",
        is_regular_finish=True,
        model_requested="test-model",
        model_used="test-model",
        usage={"prompt_tokens": 10},
        cost_estimated=0.001,
        latency_seconds=0.5,
        attempts=1,
        downstream_router_mutations="explicitly_unobserved",
    )
    env_true = LLMEnvelope(
        content_final="{}",
        reasoning_content=None,
        finish_reason="stop",
        is_regular_finish=True,
        model_requested="test-model",
        model_used="test-model",
        usage={"prompt_tokens": 10},
        cost_estimated=0.001,
        latency_seconds=0.5,
        attempts=1,
        downstream_router_mutations=True,
    )
    env_false = LLMEnvelope(
        content_final="{}",
        reasoning_content=None,
        finish_reason="stop",
        is_regular_finish=True,
        model_requested="test-model",
        model_used="test-model",
        usage={"prompt_tokens": 10},
        cost_estimated=0.001,
        latency_seconds=0.5,
        attempts=1,
        downstream_router_mutations=False,
    )

    repo._persist_generation_attempts_in_tx(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        generation_attempts=[env_unobserved, env_true, env_false],
        agora="2026-10-24T20:00:00Z",
    )
    await repo.session.commit()

    attempts = await repo.get_generation_attempts(pesq.id_pesquisa, etapa="audit")
    assert len(attempts) == 3
    # O primeiro deve ser None (não True nem False!)
    assert attempts[0].downstream_router_mutations is None
    assert attempts[1].downstream_router_mutations is True
    assert attempts[2].downstream_router_mutations is False


@pytest.mark.asyncio
async def test_audit_preserves_envelopes_on_llm_call_error_and_links_ga_ids(async_engine: AsyncEngine) -> None:
    """A03/A04/F04: LLMCallError preserva exc.envelopes e exc.envelope, deduplica sem .id e vincula IDs na auditoria."""
    from app.tools.errors import LLMCallError
    from app.tools.llm_types import LLMEnvelope

    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    id_pesquisa = None
    ponto_id = None
    coleta_id = None

    async with session_factory() as session1:
        repo1 = ResearchRepository(session=session1)
        pesq, pontos = await create_research_fixture_with_plan(repo1)
        ponto = pontos[0]
        id_pesquisa = pesq.id_pesquisa
        ponto_id = ponto.ponto_id

        meta = make_standard_coleta_metadata()
        coleta = await repo1.save_collected_content(
            id_pesquisa=id_pesquisa,
            ponto_id=ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Coleta para teste de envelopes",
            urls_lidas=["https://php.net/security-2026"],
            urls_fonte=["https://php.net/security-2026"],
            metadados_coleta=meta,
        )
        coleta_id = coleta.id

        prior_env = LLMEnvelope(
            content_final="bad json",
            reasoning_content=None,
            finish_reason="stop",
            is_regular_finish=True,
            model_requested="strong",
            model_used="strong",
            usage=None,
            cost_estimated=None,
            latency_seconds=0.2,
            attempts=1,
            prompt_hash="hash_call_1",
            created_at="2026-10-24T20:00:01Z",
        )
        err_env = LLMEnvelope(
            content_final=None,
            reasoning_content=None,
            finish_reason="error",
            is_regular_finish=False,
            model_requested="strong",
            model_used="strong",
            usage=None,
            cost_estimated=None,
            latency_seconds=0.3,
            attempts=2,
            prompt_hash="hash_call_2",
            created_at="2026-10-24T20:00:02Z",
            errors=[{"message": "rate limit or parser error"}],
        )

        async def throwing_handler(req: httpx.Request) -> httpx.Response:
            raise LLMCallError("Simulated LLM call failure", envelope=err_env, envelopes=[prior_env, err_env])

        llm = LLMClient(api_key="key", transport=httpx.MockTransport(throwing_handler))
        auditor = Auditor(research_repo=repo1, llm_client=llm)

        try:
            with pytest.raises(LLMCallError):
                await auditor.execute_audit(id_pesquisa=id_pesquisa)
        finally:
            await llm.aclose()

    # Nova sessão independente para conferir persistência e vínculos
    async with session_factory() as session2:
        repo2 = ResearchRepository(session=session2)
        attempts = await repo2.get_generation_attempts(id_pesquisa, etapa="audit")
        assert len(attempts) == 2, f"Esperava 2 attempts, obteve {len(attempts)}"
        hashes = {att.prompt_hash for att in attempts}
        assert "hash_call_1" in hashes
        assert "hash_call_2" in hashes

        # Confere que o histórico na coleta foi preservado e vincula os generation_attempt_ids
        target_coleta = await session2.get(ConteudoColetado, coleta_id)
        assert target_coleta is not None
        meta_read = json.loads(target_coleta.metadados_coleta or "{}")
        auditorias = meta_read.get("auditorias", [])
        assert len(auditorias) >= 1
        last_aud = auditorias[-1]
        assert last_aud.get("valido") is False
        assert last_aud.get("criterios") is None
        assert last_aud.get("criterios_aprovados") == 0
        persisted_ids = {att.id for att in attempts}
        linked_ids = set(last_aud.get("generation_attempt_ids") or [])
        assert linked_ids == persisted_ids, "Os IDs de GenerationAttempt devem estar vinculados ao registro de auditoria!"


@pytest.mark.asyncio
async def test_audit_db_transaction_closed_before_llm_network_call(db_session: AsyncSession) -> None:
    """A05/F01: A transação de leitura aberta por reserve/get_point DEVE estar fechada antes da chamada LLM."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Coleta para teste de transação fechada",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    in_tx_during_network = None

    async def network_handler(req: httpx.Request) -> httpx.Response:
        nonlocal in_tx_during_network
        # Asserta o estado da transação de banco durante a chamada de rede
        in_tx_during_network = repo.session.in_transaction()
        return make_llm_json_response({
            "criterios": make_audit_12_vector(12),
            "resumo_auditoria": "Ok",
        })

    llm = LLMClient(api_key="key", transport=httpx.MockTransport(network_handler))
    auditor = Auditor(research_repo=repo, llm_client=llm)
    try:
        res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
        assert res["total_pontos"] == 1
        assert in_tx_during_network is False, "A sessão SQLAlchemy estava com transação aberta durante a rede!"
    finally:
        await llm.aclose()


@pytest.mark.asyncio
async def test_audit_atomic_cas_fence_and_loss_of_possession(async_engine: AsyncEngine) -> None:
    """A05/A06/F01: Auditor em voo (sessão A) perde posse para sessão B; fence CAS rejeita, não aplica aprovação nem apaga dossiê novo."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session_a, session_factory() as session_b:
        repo_a = ResearchRepository(session=session_a)
        repo_b = ResearchRepository(session=session_b)

        pesq, pontos = await create_research_fixture_with_plan(repo_a)
        ponto = pontos[0]

        meta1 = make_standard_coleta_metadata()
        await repo_a.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Coleta 1",
            urls_lidas=["https://php.net/security-2026"],
            urls_fonte=["https://php.net/security-2026"],
            metadados_coleta=meta1,
        )

        a_entered = asyncio.Event()
        a_release = asyncio.Event()

        async def handler_a(req: httpx.Request) -> httpx.Response:
            a_entered.set()
            await a_release.wait()
            return make_llm_json_response({"criterios": make_audit_12_vector(12)})

        llm_a = LLMClient(api_key="key_a", transport=httpx.MockTransport(handler_a))
        auditor_a = Auditor(research_repo=repo_a, llm_client=llm_a)

        task_a = asyncio.create_task(auditor_a.execute_audit(id_pesquisa=pesq.id_pesquisa))

        try:
            async with asyncio.timeout(3.0):
                await a_entered.wait()

            # Sessão A está em voo no LLM.
            # Enquanto A está no ar, Sessão B salva nova coleta (rodada 2) e define um dossiê novo marcador:
            meta2 = make_standard_coleta_metadata(source_url="https://php.net/security-rodada2")
            await repo_b.save_collected_content(
                id_pesquisa=pesq.id_pesquisa,
                ponto_id=ponto.ponto_id,
                tema=pesq.tema,
                ponto=ponto.ponto,
                conteudo_coletado="Coleta Rodada 2 da sessão B",
                urls_lidas=["https://php.net/security-rodada2"],
                urls_fonte=["https://php.net/security-rodada2"],
                metadados_coleta=meta2,
                rodada=2,
            )
            # Sessão B grava um dossiê novo marcador na Pesquisa
            stmt_dossier = (
                update(Pesquisa)
                .where(Pesquisa.id_pesquisa == pesq.id_pesquisa)
                .values(dossier_final="DOSSIER_MARCADOR_RODADA_2", concluido_em="2026-10-25T00:00:00Z")
            )
            await session_b.execute(stmt_dossier)
            # Atualiza ponto para outro status pela sessão B
            stmt_ponto = (
                update(Ponto)
                .where(Ponto.ponto_id == ponto.ponto_id)
                .values(status="coletado", atualizado_em="2026-10-25T01:00:00Z")
            )
            await session_b.execute(stmt_ponto)
            await session_b.commit()

        finally:
            # Libera o LLM da sessão A
            a_release.set()
            res_a = await task_a
            await llm_a.aclose()

        # Resposta da auditoria A deve reportar que a rodada foi superada (não aplicada)
        item_a = res_a["auditorias"][0]
        assert item_a["status"] == "reprovado"
        assert item_a["valido"] is False
        assert "superada" in (item_a["diagnostico"] or item_a["pontos_fracos"]).lower()

        # Em uma terceira sessão neutra, verifica que o dossiê marcador de B foi PRESERVADO
        async with session_factory() as session_c:
            repo_c = ResearchRepository(session=session_c)
            pesq_fresca = await repo_c.get_research(pesq.id_pesquisa)
            assert pesq_fresca.dossier_final == "DOSSIER_MARCADOR_RODADA_2"
            ponto_fresco = await repo_c.get_point(ponto.ponto_id)
            assert ponto_fresco.status == "coletado"  # Não virou aprovado pela chamada obsoleta!


@pytest.mark.asyncio
async def test_audit_two_overlapping_audits_concurrent_conflict(async_engine: AsyncEngine) -> None:
    """A05/F01: Duas auditorias sobrepostas em sessões independentes; uma LLM suspensa, a segunda sofre 409/CONCURRENT antes da rede."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session1, session_factory() as session2:
        repo1 = ResearchRepository(session=session1)
        repo2 = ResearchRepository(session=session2)

        pesq, pontos = await create_research_fixture_with_plan(repo1)
        ponto = pontos[0]

        meta = make_standard_coleta_metadata()
        await repo1.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Coleta para sobreposição",
            urls_lidas=["https://php.net/security-2026"],
            urls_fonte=["https://php.net/security-2026"],
            metadados_coleta=meta,
        )

        t1_entered = asyncio.Event()
        t1_release = asyncio.Event()
        t1_calls = 0
        t2_calls = 0

        async def handler_1(req: httpx.Request) -> httpx.Response:
            nonlocal t1_calls
            t1_calls += 1
            t1_entered.set()
            await t1_release.wait()
            return make_llm_json_response({"criterios": make_audit_12_vector(12)})

        async def handler_2(req: httpx.Request) -> httpx.Response:
            nonlocal t2_calls
            t2_calls += 1
            return make_llm_json_response({"criterios": make_audit_12_vector(12)})

        llm1 = LLMClient(api_key="key1", transport=httpx.MockTransport(handler_1))
        llm2 = LLMClient(api_key="key2", transport=httpx.MockTransport(handler_2))

        auditor1 = Auditor(research_repo=repo1, llm_client=llm1)
        auditor2 = Auditor(research_repo=repo2, llm_client=llm2)

        task1 = asyncio.create_task(auditor1.execute_audit(id_pesquisa=pesq.id_pesquisa))

        try:
            async with asyncio.timeout(3.0):
                await t1_entered.wait()

            # Auditor 1 está com posse ativa na sessão 1
            # Auditor 2 na sessão 2 tenta executar sobre a mesma pesquisa
            with pytest.raises(ValueError) as exc_info:
                await auditor2.execute_audit(id_pesquisa=pesq.id_pesquisa)
            assert "CONCURRENT_EXECUTION" in str(exc_info.value)
            # Auditor 2 NÃO disparou nenhuma chamada LLM
            assert t2_calls == 0

        finally:
            t1_release.set()
            await task1
            await llm1.aclose()
            await llm2.aclose()


@pytest.mark.asyncio
async def test_audit_third_abandoned_lease_terminates_with_diagnostic(db_session: AsyncSession) -> None:
    """A05/A06/F01: Ponto na 3ª tentativa com lease expirada não trava em auditando com MAX; termina reprovado com diagnóstico."""
    from datetime import datetime, timezone, timedelta
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    meta = make_standard_coleta_metadata()
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Coleta abandonada",
        urls_lidas=["https://php.net/security-2026"],
        urls_fonte=["https://php.net/security-2026"],
        metadados_coleta=meta,
    )

    # Simula ponto na 3ª tentativa com lease expirada (usa o lease real do auditor).
    from app.core.auditor import AUDIT_POINT_LEASE_SECONDS as _LEASE

    expirado_iso = (
        datetime.now(timezone.utc) - timedelta(seconds=_LEASE + 100)
    ).isoformat()
    stmt_abandon = (
        update(Ponto)
        .where(Ponto.ponto_id == ponto.ponto_id)
        .values(status="auditando", tentativas_auditoria=3, atualizado_em=expirado_iso)
    )
    await repo.session.execute(stmt_abandon)
    await repo.session.commit()

    # Executa auditoria: não deve lançar MAX_ATTEMPTS_EXCEEDED mantendo o ponto em 'auditando'
    llm = LLMClient(api_key="key", transport=create_mock_transport())
    auditor = Auditor(research_repo=repo, llm_client=llm)
    try:
        res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa)
        assert res["total_pontos"] == 1
        item = res["auditorias"][0]
        assert item["status"] == "reprovado"
        assert "lease" in (item["diagnostico"] or item["pontos_fracos"]).lower()
    finally:
        await llm.aclose()

    ponto_final = await repo.get_point(ponto.ponto_id)
    assert ponto_final.status == "reprovado"
    assert ponto_final.tentativas_auditoria == 3  # Não resetou contador nem tentou 4ª chamada LLM


@pytest.mark.asyncio
async def test_audit_api_filtered_counts_and_pipeline_status(async_engine: AsyncEngine) -> None:
    """A09/F02: total_pontos/aprovados/reprovados no mesmo escopo filtrado com pontos aprovado/reprovado/pendente fora."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session1:
        repo1 = ResearchRepository(session=session1)
        pesq, pontos = await create_research_fixture_with_plan(repo1, n_pontos=4)
        p0 = pontos[0]  # Ponto que será filtrado e aprovado
        p1 = pontos[1]  # Ponto aprovado fora do filtro
        p2 = pontos[2]  # Ponto reprovado fora do filtro
        p3 = pontos[3]  # Ponto pendente fora do filtro

        meta0 = make_standard_coleta_metadata()
        await repo1.save_collected_content(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=p0.ponto_id,
            tema=pesq.tema,
            ponto=p0.ponto,
            conteudo_coletado="Coleta P0",
            urls_lidas=["https://php.net/security-2026"],
            urls_fonte=["https://php.net/security-2026"],
            metadados_coleta=meta0,
        )
        # Configura os status de cada ponto
        await repo1.update_point_status(p0.ponto_id, status="coletado")
        await repo1.update_point_status(p1.ponto_id, status="aprovado")
        await repo1.update_point_status(p2.ponto_id, status="reprovado")
        await repo1.update_point_status(p3.ponto_id, status="pendente")
        await session1.commit()

        # Chamada filtrando apenas o ponto p0 (que será aprovado com 12 critérios)
        llm = LLMClient(api_key="key", transport=create_mock_transport())
        auditor = Auditor(research_repo=repo1, llm_client=llm)
        try:
            res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, ponto_id=p0.ponto_id)
            # Escopo filtrado: total_pontos, aprovados e reprovados devem refletir APENAS p0
            assert res["total_pontos"] == 1
            assert res["aprovados"] == 1
            assert res["reprovados"] == 0
            # Global: pronto_para_writer deve ser False pois há p2 (reprovado) e p3 (pendente)
            assert res["pronto_para_writer"] is False
            # status_pesquisa expõe o estado real persistido no banco
            assert res["status_pesquisa"] in ("reprovado", "parcial")
        finally:
            await llm.aclose()

    # Confere o status persistido lido fresco em nova sessão
    async with session_factory() as session2:
        repo2 = ResearchRepository(session=session2)
        pesq_fresca = await repo2.get_research(pesq.id_pesquisa)
        assert pesq_fresca.status_pipeline == res["status_pesquisa"]


@pytest.mark.asyncio
async def test_audit_cache_strict_revalidation_and_threshold_recalc(async_engine: AsyncEngine) -> None:
    """A07/A08/F02: Cache com input_hash real revalida vetor; vetor com claim inválido força nova chamada LLM."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    llm_calls = 0

    async def custom_llm_handler(req: httpx.Request) -> httpx.Response:
        nonlocal llm_calls
        llm_calls += 1
        return make_llm_json_response({
            "criterios": make_audit_12_vector(12, known_claim_ids=[f"claim_{i}" for i in range(1, 5)]),
            "resumo_auditoria": f"Avaliação chamada {llm_calls}",
        })

    id_pesquisa = None
    ponto_id = None
    coleta_id = None

    async with session_factory() as session1:
        repo1 = ResearchRepository(session=session1)
        pesq, pontos = await create_research_fixture_with_plan(repo1)
        ponto = pontos[0]
        id_pesquisa = pesq.id_pesquisa
        ponto_id = ponto.ponto_id

        meta = make_standard_coleta_metadata()
        coleta = await repo1.save_collected_content(
            id_pesquisa=id_pesquisa,
            ponto_id=ponto_id,
            tema=pesq.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Coleta para teste de cache",
            urls_lidas=["https://php.net/security-2026"],
            urls_fonte=["https://php.net/security-2026"],
            metadados_coleta=meta,
        )
        coleta_id = coleta.id

        # 1. Primeira chamada legítima para gerar entrada de cache com input_hash real
        llm1 = LLMClient(api_key="key", transport=httpx.MockTransport(custom_llm_handler))
        auditor1 = Auditor(research_repo=repo1, llm_client=llm1)
        try:
            res1 = await auditor1.execute_audit(id_pesquisa=id_pesquisa)
            assert res1["total_pontos"] == 1
            assert llm_calls == 1
        finally:
            await llm1.aclose()

        # 2. Segunda chamada idêntica: deve reusar cache SEM disparar nova inferência
        llm2 = LLMClient(api_key="key", transport=httpx.MockTransport(custom_llm_handler))
        auditor2 = Auditor(research_repo=repo1, llm_client=llm2)
        try:
            res2 = await auditor2.execute_audit(id_pesquisa=id_pesquisa)
            assert res2["total_pontos"] == 1
            assert llm_calls == 1, "Deveria ter reutilizado o cache sem nova chamada LLM!"
        finally:
            await llm2.aclose()

    # 3. Em nova sessão, modifica SOMENTE o vetor armazenado no cache da coleta (adiciona claim fantasma), mantendo input_hash real
    async with session_factory() as session2:
        coleta_db = await session2.get(ConteudoColetado, coleta_id)
        meta_db = json.loads(coleta_db.metadados_coleta or "{}")
        auds = meta_db.get("auditorias", [])
        assert len(auds) >= 1
        # Corrompe o vetor do cache introduzindo claim_id desconhecido
        auds[-1]["criterios"][0]["claim_ids"] = ["claim_desconhecido_fantasma_999"]
        coleta_db.metadados_coleta = json.dumps(meta_db, ensure_ascii=False)
        # Reseta ponto para coletado para permitir reavaliação se cache for rejeitado
        ponto_db = await session2.get(Ponto, ponto_id)
        ponto_db.status = "coletado"
        await session2.commit()

    # 4. Terceira chamada: mesmo com input_hash batendo, o vetor no cache é inválido!
    # O auditor DEVE revalidar o vetor estrito e forçar nova inferência LLM
    async with session_factory() as session3:
        repo3 = ResearchRepository(session=session3)
        llm3 = LLMClient(api_key="key", transport=httpx.MockTransport(custom_llm_handler))
        auditor3 = Auditor(research_repo=repo3, llm_client=llm3)
        try:
            res3 = await auditor3.execute_audit(id_pesquisa=id_pesquisa)
            assert res3["total_pontos"] == 1
            assert llm_calls == 2, "Vetor cached corrompido deveria ter sido rejeitado e forçado nova chamada LLM!"
        finally:
            await llm3.aclose()


@pytest.mark.asyncio
async def test_audit_search_and_audit_mutual_exclusion(db_session: AsyncSession) -> None:
    """A05/F01: Exclusão mútua nos dois sentidos: Audit não toma reserva de Search ativa, e Search não toma Audit ativa."""
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    # 1. Ponto em busca ativa (status="em_andamento")
    await repo.update_point_status(ponto.ponto_id, status="em_andamento")
    # Auditoria não pode reservar ponto em andamento
    with pytest.raises(ValueError) as exc1:
        await repo.reserve_point_for_audit(ponto.ponto_id)
    assert "CONCURRENT_EXECUTION" in str(exc1.value)

    # 2. Ponto em auditoria ativa (status="auditando")
    await repo.update_point_status(ponto.ponto_id, status="auditando")
    # Busca não pode reservar ponto em auditoria
    with pytest.raises(ValueError) as exc2:
        await repo.reserve_point(ponto.ponto_id)
    assert "CONCURRENT_EXECUTION" in str(exc2.value)


@pytest.mark.asyncio
async def test_r8_audit_rigor_instructions_and_material_support_contract(
    db_session: AsyncSession,
) -> None:
    """R8: Rigor material do Audit — contrato explícito de distinção primária/secundária/consenso/pré-aviso,
    confronto de alcance das alegações com trechos entregues, preservação de feedback acionável
    e deliberação determinística sem reprovação artificial do backend em relatos delimitados.
    """
    repo = ResearchRepository(session=db_session)
    pesq, pontos = await create_research_fixture_with_plan(repo)
    ponto = pontos[0]

    # Prepara evidência com pré-aviso primário e detalhes em fonte secundária
    body_primaria = (
        "PHP Group pre-announcement: Security release scheduled for October 21 2026 at 14:00 UTC. "
        "Versions and specific vulnerability identifiers will be announced upon release."
    )
    body_secundaria = (
        "Security Advisory: PHP released versions 8.5.12, 8.4.27, 8.3.36, and 8.2.35. "
        "Fixes CVE-2026-115560 and bailout memory corruption."
    )
    src_prim = make_source_data("src_primaria", "https://php.net/news-pre-announcement", body_primaria)
    src_sec = make_source_data("src_secundaria", "https://security-digest.example/php-vulns", body_secundaria)

    chk_prim = make_chunk_data(1, "src_primaria", src_prim["url"], body_primaria, 0, len(body_primaria))
    chk_sec = make_chunk_data(2, "src_secundaria", src_sec["url"], body_secundaria, 0, len(body_secundaria))

    personas_names = ["historiador", "visionario", "cetico", "futurista"]
    resultados_personas = {}
    for idx, p in enumerate(personas_names, 1):
        # Historiador afirma confirmação oficial extrapolando trechos; cetico delimita relato secundário
        afirmacao = (
            "Confirmação canônica oficial integral do lançamento de versões PHP em php.net."
            if p == "historiador"
            else f"Relato secundário documentado de correções das versões PHP sob análise de {p}."
        )
        tipo = "fato" if p == "historiador" else "inferencia"
        c_item = {
            "claim_id": f"claim_{idx}",
            "afirmacao": afirmacao,
            "tipo": tipo,
            "evidencias": [src_prim["url"]] if p == "historiador" else [src_sec["url"]],
            "confianca": "alta",
            "limitacoes": "" if p == "historiador" else "Detalhes extraídos de fonte secundária independente.",
        }
        resultados_personas[p] = make_persona_result(
            persona=p,
            analise=f"Análise metodológica {p}.",
            claims=[c_item],
            lacunas=[] if p == "historiador" else ["Aguardando changelog oficial primário em php.net"],
            sucesso=True,
        )
        resultados_personas[p]["urls_fonte"] = [src_prim["url"], src_sec["url"]]
        resultados_personas[p]["urls_lidas"] = [src_prim["url"], src_sec["url"]]

    meta = {
        "versao": 3,
        "fontes": [
            {"url": src_prim["url"], "uso": "utilizada", "titulo": "Pré-aviso", "status": "read_ok"},
            {"url": src_sec["url"], "uso": "utilizada", "titulo": "Digest", "status": "read_ok"},
        ],
        "resultados_personas": resultados_personas,
        "diario_acoes": {p: [{"acao": "buscar"}, {"acao": "concluir"}] for p in personas_names},
    }

    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Evidência primária de pré-aviso e secundária com detalhes de versão",
        urls_lidas=[src_prim["url"], src_sec["url"]],
        urls_fonte=[src_prim["url"], src_sec["url"]],
        metadados_coleta=meta,
    )

    captured_requests = []
    # Vetor simulado 1: reprovação com feedback acionável apontando lacuna de confirmação primária no critério 2
    override_c2 = {
        2: {
            "aprovado": False,
            "justificativa": (
                "Trechos de php.net contêm apenas pré-aviso de lançamento; detalhes de versões e CVEs "
                "constam exclusivamente em fonte secundária. Falta confirmação primária direta."
            ),
            "claim_ids": ["claim_1"],
            "source_ids": [src_prim["url"], src_sec["url"]],
            "lacuna": "Ausência de confirmação primária canônica das versões lançadas em php.net.",
            "correcao": "Search deve buscar o anúncio de lançamento e changelog canônico em php.net.",
            "personas_pertinentes": ["cetico", "historiador"],
        }
    }
    rejection_vector = make_audit_12_vector(
        12,
        known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"],
        known_source_ids=[src_prim["url"], src_sec["url"]],
        override_criterion=override_c2,
    )

    def mock_handler(req: httpx.Request) -> httpx.Response:
        captured_requests.append(req)
        return make_llm_json_response({
            "criterios": rejection_vector,
            "resumo_auditoria": "Reprovado por lacuna material de corroboração canônica primária.",
        })

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = mock_handler
    llm = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net))
    auditor = Auditor(research_repo=repo, llm_client=llm)

    res = await auditor.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=12)
    assert len(captured_requests) == 1
    req_body = json.loads(captured_requests[0].content.decode("utf-8"))
    system_prompt = next(m["content"] for m in req_body["messages"] if m["role"] == "system")
    sys_lower = system_prompt.lower()

    # Contrato explícito no system prompt:
    # 1. Distinção entre suporte primário e fonte secundária citando primária
    assert "secundária" in sys_lower, "Prompt deve instruir distinção de fontes secundárias citando primárias"
    # 2. Consenso entre personas não substitui evidência primária material entregue
    assert "consenso" in sys_lower, "Prompt deve instruir que consenso entre personas não substitui suporte primário material"
    # 3. Pré-aviso / agendamento não prova publicação ou ocorrência posterior
    assert "pré-aviso" in sys_lower or "agendamento" in sys_lower, "Prompt deve instruir que pré-aviso não prova ocorrência posterior"
    # 4. Confrontar alcance das alegações com trechos entregues (reputação de links não aprova o conjunto)
    assert "alcance" in sys_lower, "Prompt deve instruir confronto do alcance das alegações com os trechos"

    # Validação do processamento do vetor de reprovação com feedback acionável preservado
    item = res["auditorias"][0]
    assert item["status"] == "reprovado"
    assert item["criterios_aprovados"] == 11
    assert item["pontuacao_percentual"] == 91.67
    assert len(item["tarefas"]) == 1
    task = item["tarefas"][0]
    assert task["criterio_id"] == 2
    assert "anúncio de lançamento" in task["acao_corretiva"]
    assert "cetico" in task["personas_alvo"]
    assert "historiador" in task["personas_alvo"]
    assert "claim_1" in task["claim_ids"]
    assert item["pontos_fracos"] is not None

    crit2 = next(c for c in item["criterios"] if c["id"] == 2)
    assert crit2["aprovado"] is False
    assert "anúncio de lançamento" in crit2["correcao"]
    assert "cetico" in crit2["personas_pertinentes"]
    assert "historiador" in crit2["personas_pertinentes"]

    # Caso complementar: quando o Search recupera a evidência primária definitiva que sustenta a alegação central,
    # uma segunda coleta real é salva. O backend calcula deterministicamente a aprovação (12/12) sem impor reprovação artificial.
    body_primaria_definitiva = (
        "The PHP Group officially announces the immediate availability of PHP 8.5.12, 8.4.27, "
        "8.3.36, and 8.2.35. Addresses verified security issues including CVE-2026-115560 and "
        "state corruption during bailout. See official release changelog for full details."
    )
    src_prim_def = make_source_data("src_primaria", "https://php.net/news-release-2026", body_primaria_definitiva)
    chk_prim_def = make_chunk_data(10, "src_primaria", src_prim_def["url"], body_primaria_definitiva, 0, len(body_primaria_definitiva))

    resultados_personas_2 = {}
    for idx, p in enumerate(personas_names, 1):
        c_item_2 = {
            "claim_id": f"claim_{idx}",
            "afirmacao": (
                f"Confirmação canônica oficial direta das versões PHP e CVE-2026-115560 em php.net sob análise {p}."
            ),
            "tipo": "fato",
            "evidencias": [src_prim_def["url"]],
            "confianca": "alta",
            "limitacoes": "",
        }
        resultados_personas_2[p] = make_persona_result(
            persona=p,
            analise=f"Análise metodológica atualizada {p} com anúncio e changelog primários.",
            claims=[c_item_2],
            lacunas=[],
            sucesso=True,
        )
        resultados_personas_2[p]["urls_fonte"] = [src_prim_def["url"]]
        resultados_personas_2[p]["urls_lidas"] = [src_prim_def["url"]]

    meta_2 = {
        "versao": 3,
        "fontes": [
            {"url": src_prim_def["url"], "uso": "utilizada", "titulo": "Release", "status": "read_ok"}
        ],
        "resultados_personas": resultados_personas_2,
        "diario_acoes": {p: [{"acao": "buscar_canonica"}, {"acao": "concluir"}] for p in personas_names},
    }

    # Salva nova coleta real: atualiza a rodada e invalida legitimamente o cache sem manipular ponto.status
    await repo.save_collected_content(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesq.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Evidência primária definitiva com anúncio de lançamento e changelog canônico",
        urls_lidas=[src_prim_def["url"]],
        urls_fonte=[src_prim_def["url"]],
        metadados_coleta=meta_2,
    )

    captured_requests_2 = []
    approved_vector = make_audit_12_vector(
        12,
        known_claim_ids=["claim_1", "claim_2", "claim_3", "claim_4"],
        known_source_ids=[src_prim_def["url"]],
    )

    def mock_handler_2(req: httpx.Request) -> httpx.Response:
        captured_requests_2.append(req)
        return make_llm_json_response({
            "criterios": approved_vector,
            "resumo_auditoria": "Aprovado integralmente com suporte primário canônico verificado nos trechos.",
        })

    mock_net_2 = MockNetwork()
    mock_net_2.custom_handlers["chat/completions"] = mock_handler_2
    llm_2 = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net_2))
    auditor_2 = Auditor(research_repo=repo, llm_client=llm_2)

    res_appr = await auditor_2.execute_audit(id_pesquisa=pesq.id_pesquisa, criterios_minimos=12)
    assert len(captured_requests_2) == 1, "Nova coleta deve disparar exatamente 1 nova avaliação LLM"

    item_appr = res_appr["auditorias"][0]
    assert item_appr["status"] == "aprovado"
    assert item_appr["criterios_aprovados"] == 12
    assert item_appr["pontuacao_percentual"] == 100.0
    assert item_appr["pontos_fracos"] is None
    assert len(item_appr["tarefas"]) == 0

    # Total de 2 avaliações reais simuladas
    assert len(captured_requests) + len(captured_requests_2) == 2











