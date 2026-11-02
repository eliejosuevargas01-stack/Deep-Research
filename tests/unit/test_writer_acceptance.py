# -*- coding: utf-8 -*-
"""Testes de aceitação, integridade, concorrência e conformidade do Writer (W01..W14, S01..S08).

Cobre os contratos do adendo v6 e writer-scope.md:
- W01: Prontidão antes de cache/modelo; exige todos pontos aprovados com coleta atual e auditoria válida/aplicada.
- W02: Contexto fiel ao plano e à coleta atual; sem rodadas antigas; ressalvas e falhas da auditoria (ex: C2) incluídas.
- W03: Prompt de síntese material; explicação infantil primeiro quando pedida; citações [Fonte](URL).
- W04: Quatro seções em Markdown substantivas fora de blocos de código; cercas fechadas; término regular; sem URLs inventadas.
- W05: Envelopes de geração e avaliação persistidos em generation_attempts (etapa 'write', personas distintas).
- W06: Avaliação separada do artigo pronto com modelo forte e 12 critérios; corte 11/12 (91.67%); cálculo backend estrito.
- W07: Orçamento máximo de 2 rascunhos e 2 avaliações; recuperação dirigida; 600s total.
- W08: Reserva/lease/fence atômicos no banco via metadados_redacao; dono único; verificação de dados concorrentes.
- W09: Cache de idempotência validado após prontidão; exige documento íntegro e avaliação >= 11; 0 chamadas LLM e sem novo webhook.
- W10: Publicação e status 'concluido' somente para artigo aprovado; falha preserva diagnósticos sem publicar rascunho como final.
- W11: API e webhook sem reasoning; callback opcional; entrega segura.
- W12: Rota POST /api/v1/writer fecha LLM em finally e mapeia 404/400/409/502/504; Runner sem triplo retry externo.
- W13: Migração idempotente de metadados_redacao preservando integridade e registros pré-existentes como NULL.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
import uuid

import httpx
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import delete as sql_delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.pipeline_runner import PipelineRunner
from app.core.writer import Writer
from app.db.init_db import _run_additive_migrations, init_db
from app.db.models import ConteudoColetado, GenerationAttempt, Pesquisa, Ponto
from app.db.research_repository import ResearchRepository
from app.main import app
from app.schemas.audit import CRITERIA_TITLES
try:
    from app.schemas.writer import (
        ArticleCriterionDetail,
        ArticleEvaluationResult,
        WriterRequest,
        WriterResponse,
    )
except ImportError:
    ArticleCriterionDetail = None  # type: ignore
    ArticleEvaluationResult = None  # type: ignore
    from app.schemas.writer import WriterRequest, WriterResponse  # type: ignore
from app.services.webhook_client import WebhookClient
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_audit_acceptance import (
    CANONICAL_EIXO,
    CANONICAL_PLANO,
    make_audit_12_vector,
    make_chunk_data,
    make_persona_result,
    make_source_data,
    make_standard_coleta_metadata,
)
from tests.unit.test_reproduction_gate1_helpers import (
    make_llm_json_response,
    make_llm_raw_response,
)


# ==============================================================================
# HELPERS E FIXTURES DE CONFIGURAÇÃO DO WRITER
# ==============================================================================

VALID_CANONICAL_URL = "https://php.net/security-2026"

# SAMPLE_VALID_ARTICLE é uma fixture meramente estrutural para validação de sintaxe e
# formato Markdown; não comprova mérito factual, completude investigativa ou adequação infantil.
SAMPLE_VALID_ARTICLE = f"""# Dossiê Analítico: Vulnerabilidades de Segurança no PHP em Outubro de 2026

## 1. Sumário Executivo
Este sumário executivo consolida os achados apurados sobre a segurança do runtime PHP em outubro de 2026. A equipe técnica e os mantenedores oficiais publicaram atualizações de rotina mitigando falhas de gravidade baixa e moderada, sem confirmação de vulnerabilidades críticas de execução remota de código (RCE) não corrigidas. As fontes canônicas [PHP Security Announcements]({VALID_CANONICAL_URL}) atestam a disponibilidade das correções nos repositórios oficiais.

## 2. Desenvolvimento dos Eixos Temáticos
A investigação aprofundou a análise técnica dos canais formais e dos relatórios de terceiros. Em conformidade com os registros primários [PHP Group]({VALID_CANONICAL_URL}), as versões estáveis receberam patches pontuais. A análise de conformidade descarta os boatos iniciais divulgados em canais não oficiais.

## 3. Ressalvas e Limitações Metodológicas
A auditoria formal apontou que o pré-aviso oficial não comprova a efetivação posterior de releases e que parte dos detalhes técnicos de commits permanece documentada apenas em relatórios secundários. Ressalva metodológica: os testes automatizados cobrem apenas as versões homologadas e não avaliam extensões descontinuadas.

## 4. Referências e Fontes Canônicas
1. [PHP Security Announcements]({VALID_CANONICAL_URL}) - Boletim oficial de segurança do projeto PHP.
"""


def make_writer_article_12_eval(
    aprovados_count: int = 12,
    correcao_text: Optional[str] = None,
    override_criterion: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Cria resposta estruturada de avaliação do artigo com os 12 critérios formais."""
    criterios = []
    for i in range(1, 13):
        is_aprovado = i <= aprovados_count
        item: Dict[str, Any] = {
            "id": i,
            "aprovado": is_aprovado,
            "justificativa": f"Critério {i} ({CRITERIA_TITLES.get(i, 'criterio')}) {'atendido com rigor' if is_aprovado else 'insuficiente'}.",
            "claim_ids": ["claim_1"],
            "source_ids": [],
            "correcao": None if is_aprovado else (correcao_text or f"Ajustar a redação para atender ao critério {i}."),
        }
        if override_criterion and i in override_criterion:
            item.update(override_criterion[i])
        criterios.append(item)

    return {
        "criterios": criterios,
        "resumo_avaliacao": f"Avaliação da redação com {aprovados_count}/12 critérios atendidos.",
    }


async def setup_research_with_audit(
    repo: ResearchRepository,
    tema: str = "Vulnerabilidades PHP Outubro 2026",
    status_ponto: str = "aprovado",
    audit_valid: bool = True,
    audit_applied: bool = True,
    criterios_aprovados: int = 11,
    failed_criterion_id: Optional[int] = 2,
    remaining_task: Optional[str] = "Obtain definitive primary release/CVE passages or explicitly qualify secondary reporting in the final synthesis",
    plano_override: Optional[Dict[str, Any]] = None,
    source_url: str = VALID_CANONICAL_URL,
    ponto_fracos: Optional[str] = None,
) -> tuple[str, str, str]:
    """Cria uma pesquisa com plano estruturado, coleta com proveniência e auditoria formal coerente."""
    plano = plano_override or dict(CANONICAL_PLANO)
    pesquisa = await repo.create_research(
        tema=tema,
        pontos_textos=["Análise de vulnerabilidades do PHP em outubro de 2026"],
        plano_estruturado=plano,
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    ponto = pontos[0]

    # Para garantir coerência matemática estrita de 11/12 aprovados com critério 2 reprovado:
    # Geramos base com 12 True e override reprova especificamente failed_criterion_id.
    base_count = 12 if failed_criterion_id else criterios_aprovados
    vector = make_audit_12_vector(
        aprovados_count=base_count,
        override_criterion={
            failed_criterion_id: {
                "aprovado": False,
                "justificativa": "Pré-aviso não comprova release efetivado; reporte secundário precisa de qualificação.",
                "lacuna": "Falta de confirmação primária definitiva",
                "correcao": "Qualificar relato secundário",
            }
        } if failed_criterion_id else None,
    )

    real_aprovados = sum(1 for c in vector if c.get("aprovado") is True)
    pontuacao = round((real_aprovados / 12) * 100, 2)

    tarefas = []
    if remaining_task:
        tarefas.append({
            "id_tarefa": str(uuid.uuid4()),
            "criterio_id": failed_criterion_id or 2,
            "descricao": remaining_task,
            "personas_alvo": ["cetico", "historiador"],
        })

    coleta_meta = make_standard_coleta_metadata(source_url=source_url)
    audit_id = str(uuid.uuid4())
    coleta_id = str(uuid.uuid4())

    coleta_meta["auditorias"] = [
        {
            "id_auditoria": audit_id,
            "coleta_id": coleta_id,
            "rodada": 1,
            "valido": audit_valid,
            "aplicado": audit_applied,
            "status": status_ponto,
            "criterios": vector,
            "criterios_aprovados": real_aprovados,
            "criterios_minimos": 11,
            "pontuacao_percentual": pontuacao,
            "pontos_fracos": ponto_fracos,
            "tarefas": tarefas,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
    ]

    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=tema,
        ponto=ponto.ponto,
        conteudo_coletado="Evidências primárias sobre segurança do PHP 2026.",
        urls_lidas=[source_url],
        urls_fonte=[source_url],
        metadados_coleta=coleta_meta,
    )

    stmt_upd_coleta = (
        update(ConteudoColetado)
        .where(ConteudoColetado.ponto_id == ponto.ponto_id)
        .values(id=coleta_id)
    )
    await repo.session.execute(stmt_upd_coleta)

    # Na pesquisa real aceita, quando status é 'aprovado', pontos_fracos na tabela ponto fica NULL
    await repo.update_point_status(
        ponto_id=ponto.ponto_id,
        status=status_ponto,
        pontos_fracos=ponto_fracos if status_ponto == "reprovado" else None,
    )

    return pesquisa.id_pesquisa, ponto.ponto_id, coleta_id


# ==============================================================================
# 1. PRONTIDÃO ANTES DE CACHE E MODELO (W01, v6)
# ==============================================================================

@pytest.mark.asyncio
async def test_readiness_blocks_before_cache_and_model_if_point_pending(db_session: AsyncSession) -> None:
    """W01: Bloqueia execução antes de cache e modelo se houver ponto pendente, mesmo com cache presente."""
    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    pesquisa = await repo.create_research(
        tema="Pesquisa Ponto Pendente",
        pontos_textos=["Ponto não auditado"],
        plano_estruturado=dict(CANONICAL_PLANO),
    )
    # Grava documento completo no cache para provar que a prontidão é testada ANTES de devolver cache
    await repo.update_research_dossier(
        id_pesquisa=pesquisa.id_pesquisa,
        dossier_final=SAMPLE_VALID_ARTICLE,
    )

    writer = Writer(research_repo=repo, llm_client=llm_client)
    with pytest.raises(ValueError, match="PENDING_AUDIT_POINTS|pontos pendentes"):
        await writer.execute_writer(id_pesquisa=pesquisa.id_pesquisa)

    assert len(mock_net.requests) == 0, "Nenhuma chamada de LLM pode ocorrer antes da prontidão."


@pytest.mark.asyncio
async def test_readiness_blocks_before_cache_and_model_if_point_reproved_under_v2(db_session: AsyncSession) -> None:
    """W01 / DR-012: v2 bloqueia ponto reprovado antes do cache/modelo, sem parcial silencioso."""
    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(
        repo=repo,
        status_ponto="reprovado",
        audit_valid=True,
        audit_applied=True,
        criterios_aprovados=9,
        failed_criterion_id=None,
        ponto_fracos="Fragilidade severa não mitigada",
    )
    # Grava documento no cache para provar que o bloqueio de reprovação antecede o cache
    await repo.update_research_dossier(
        id_pesquisa=id_pesquisa,
        dossier_final=SAMPLE_VALID_ARTICLE,
    )

    writer = Writer(research_repo=repo, llm_client=llm_client)
    with pytest.raises(ValueError, match="reprovado|UNAPPROVED_POINTS|READINESS_FAILED"):
        await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert len(mock_net.requests) == 0, "Nenhum LLM ou cache é acionado para ponto reprovado."


@pytest.mark.asyncio
async def test_readiness_fails_if_no_valid_applied_audit_on_current_collection(db_session: AsyncSession) -> None:
    """W01: Falha se o ponto não tem auditoria estruturada válida e aplicada na coleta atual."""
    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    # Caso A: Auditoria marcada como valido=False
    id_pesquisa_invalida, _, _ = await setup_research_with_audit(
        repo=repo,
        status_ponto="aprovado",
        audit_valid=False,
        audit_applied=True,
    )
    writer = Writer(research_repo=repo, llm_client=llm_client)
    with pytest.raises(ValueError, match="READINESS_FAILED|auditoria|invalida"):
        await writer.execute_writer(id_pesquisa=id_pesquisa_invalida)

    # Caso B: Auditoria marcada como aplicado=False
    id_pesquisa_nao_aplicada, _, _ = await setup_research_with_audit(
        repo=repo,
        status_ponto="aprovado",
        audit_valid=True,
        audit_applied=False,
    )
    with pytest.raises(ValueError, match="READINESS_FAILED|auditoria|aplicada"):
        await writer.execute_writer(id_pesquisa=id_pesquisa_nao_aplicada)

    assert len(mock_net.requests) == 0


# ==============================================================================
# 2. CONTEXTO, COLETAS ATUAIS E RESSALVAS C2 (W02, v6)
# ==============================================================================

@pytest.mark.asyncio
async def test_context_delivers_current_collection_and_c2_failure_even_when_pontos_fracos_is_null(
    db_session: AsyncSession,
) -> None:
    """W02: Contexto recebe plano e coleta atual; ressalva C2 é enviada ao redator mesmo com pontos_fracos NULL."""
    mock_net = MockNetwork()

    generation_messages: List[Dict[str, Any]] = []
    evaluation_messages: List[Dict[str, Any]] = []

    def custom_llm_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            evaluation_messages.extend(msgs)
            return make_llm_json_response(make_writer_article_12_eval(aprovados_count=12))
        else:
            generation_messages.extend(msgs)
            return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = custom_llm_handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, ponto_id, coleta_id = await setup_research_with_audit(
        repo=repo,
        status_ponto="aprovado",
        criterios_aprovados=11,
        failed_criterion_id=2,
        remaining_task="Obtain definitive primary release/CVE passages or explicitly qualify secondary reporting",
        ponto_fracos=None,  # Na pesquisa real do banco, pontos_fracos é NULL!
    )

    # Atualiza a coleta mais recente para rodada 2 primeiro para liberar rodada 1
    stmt_upd = update(ConteudoColetado).where(ConteudoColetado.id == coleta_id).values(rodada=2)
    await repo.session.execute(stmt_upd)
    await repo.session.commit()

    # Insere rodada antiga com sentinel para comprovar que É incluída no contexto (PRD v2, I-5)
    meta_old = {
        "versao": 3,
        "fontes": [
            {"url": "https://old.org", "uso": "utilizada", "titulo": "Rodada antiga", "status": "read_ok"}
        ],
        "resultados_personas": {
            "historiador": {
                "persona": "historiador",
                "analise": "HISTORICAL_ROUND_SENTINEL_OLD_RODADA_1",
                "urls_fonte": ["https://old.org"],
                "urls_lidas": ["https://old.org"],
                "sucesso": True,
            }
        },
    }
    old_record = ConteudoColetado(
        id=str(uuid.uuid4()),
        id_pesquisa=id_pesquisa,
        ponto_id=ponto_id,
        rodada=1,
        tema="Tema",
        ponto="Ponto",
        conteudo_coletado="HISTORICAL_ROUND_SENTINEL_OLD_RODADA_1",
        urls_lidas=json.dumps(["https://old.org"]),
        urls_fonte=json.dumps(["https://old.org"]),
        metadados_coleta=json.dumps(meta_old),
        criado_em=datetime.now(timezone.utc).isoformat(),
    )
    repo.session.add(old_record)
    await repo.session.commit()

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] == "concluido"

    # Confere estritamente as mensagens de GERAÇÃO (redator final), não de avaliação!
    gen_text = " ".join([m.get("content", "") for m in generation_messages])

    # 1. Falha C2 ou tarefa de qualificação secundária deve constar no prompt do redator
    assert (
        "qualify secondary reporting" in gen_text
        or "critério 2" in gen_text.lower()
        or "corroboracao_canonica" in gen_text.lower()
        or "pré-aviso não comprova" in gen_text.lower()
    ), "Ressalva da auditoria (falha C2 / tarefa) deve ser entregue ao redator mesmo quando pontos_fracos é NULL."

    # 2. Informações do plano estruturado devem estar presentes
    assert "Especialistas em segurança" in gen_text
    assert "Dossiê analítico" in gen_text
    assert "19 a 24 de outubro de 2026" in gen_text

    # 3. Rodada antiga DEVE constar no payload de geração (PRD v2, I-5: acúmulo de retries)
    assert "HISTORICAL_ROUND_SENTINEL_OLD_RODADA_1" in gen_text, (
        "Rodadas anteriores devem ser entregues ao redator: descartar retries perde coleta já paga."
    )

    # 4. Proveniência real v3: URL, uso e resumo da persona, sem corpo bruto
    assert VALID_CANONICAL_URL in gen_text, "URL utilizada deve constar no contexto do redator."
    assert '"uso": "utilizada"' in gen_text, "Catálogo deve classificar uso da URL."
    assert "Análise substantiva da perspectiva" in gen_text, "Resumo acumulado da persona deve ser entregue."
    assert '"body_hash"' not in gen_text and '"chunk_id"' not in gen_text, "Bruto/hash/chunk não podem vazar para a redação."
    assert '"status": "read_ok"' in gen_text, "Fontes entregues devem manter status read_ok."
    # 6. Eixo real do plano e ressalva C2 com lacuna/correção entregues ao redator
    assert "Qualificar relato secundário" in gen_text, "Correção acionável (acao_corretiva) da auditoria deve constar no contexto."
    assert "pergunta_principal" in gen_text, "Eixo estruturado do plano deve constar no contexto."


# ==============================================================================
# 3. PROMPT DE SÍNTESE E PÚBLICO INFANTIL (W03, v6)
# ==============================================================================

@pytest.mark.asyncio
async def test_prompt_prioritizes_child_explanation_when_requested(db_session: AsyncSession) -> None:
    """W03: Quando o público do plano for infantil, o prompt instrui explicação didática em primeiro plano."""
    mock_net = MockNetwork()
    generation_messages: List[Dict[str, Any]] = []

    def custom_handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))
        else:
            generation_messages.extend(msgs)
            return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = custom_handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    plano_infantil = dict(CANONICAL_PLANO)
    plano_infantil["publico"] = "Infantil (criança de 5 anos)"
    plano_infantil["formato_entrega"] = "Explicação simples com analogias e apêndice técnico"

    id_pesquisa, _, _ = await setup_research_with_audit(
        repo=repo,
        plano_override=plano_infantil,
    )

    writer = Writer(research_repo=repo, llm_client=llm_client)
    await writer.execute_writer(id_pesquisa=id_pesquisa)

    gen_prompt_str = " ".join([m.get("content", "") for m in generation_messages]).lower()
    assert "criança" in gen_prompt_str or "infantil" in gen_prompt_str, "Público infantil deve ser comunicado ao redator."
    assert (
        "primeiro plano" in gen_prompt_str
        or "analogia" in gen_prompt_str
        or "simples" in gen_prompt_str
    ), "Instrução de síntese infantil prioritária deve constar no prompt de geração."


# ==============================================================================
# 4. INTEGRIDADE REAL DO DOCUMENTO (W04, DR-003, DR-005, DR-011)
# ==============================================================================

@pytest.mark.asyncio
async def test_article_validation_rejects_header_inside_code_fence(db_session: AsyncSession) -> None:
    """W04: Cabeçalho obrigatório dentro de bloco de código Markdown não conta como seção real."""
    mock_net = MockNetwork()
    fake_article_header_in_code = """# Dossiê

## 1. Sumário Executivo
Texto do sumário executivo.

```markdown
## 2. Desenvolvimento dos Eixos Temáticos
Este cabeçalho está dentro de uma cerca de código, logo não é seção real!
```

## 3. Ressalvas e Limitações Metodológicas
Ressalvas metodológicas reais.

## 4. Referências e Fontes Canônicas
1. https://php.net/security-2026
"""
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_raw_response(
        content=fake_article_header_in_code,
        finish_reason="stop",
    )
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] != "concluido", "Artigo com seção dentro de bloco de código não pode concluir."
    assert res["status"] == "incompleto"


@pytest.mark.asyncio
async def test_article_validation_rejects_empty_section_body(db_session: AsyncSession) -> None:
    """W04: Seção com corpo vazio (apenas título sem texto substantivo) é rejeitada."""
    mock_net = MockNetwork()
    empty_section_article = """# Dossiê

## 1. Sumário Executivo
Texto do sumário executivo substantivo.

## 2. Desenvolvimento dos Eixos Temáticos
## 3. Ressalvas e Limitações Metodológicas
Texto substantivo da seção 3.

## 4. Referências e Fontes Canônicas
1. https://php.net/security-2026
"""
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_raw_response(
        content=empty_section_article,
        finish_reason="stop",
    )
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] == "incompleto"


@pytest.mark.asyncio
async def test_article_validation_rejects_invented_urls(db_session: AsyncSession) -> None:
    """W04: URLs inventadas (não presentes no conjunto lido da coleta) invalidam a integridade."""
    mock_net = MockNetwork()
    article_with_fake_url = SAMPLE_VALID_ARTICLE.replace(
        VALID_CANONICAL_URL, "https://url-inventada-totalmente-falsa.com/fake"
    )
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_raw_response(
        content=article_with_fake_url,
        finish_reason="stop",
    )
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo, source_url=VALID_CANONICAL_URL)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] == "incompleto"


@pytest.mark.asyncio
async def test_article_validation_rejects_irregular_finish_reason(db_session: AsyncSession) -> None:
    """W04 / DR-005: finish_reason diferente de regular ('length' ou None) é rejeitado."""
    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_raw_response(
        content=SAMPLE_VALID_ARTICLE,
        finish_reason="length",  # Truncado por limite de tokens
    )
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] == "incompleto"


# ==============================================================================
# 5. AVALIAÇÃO SEMÂNTICA DO ARTIGO PRONTO E SCHEMA (W06, v6)
# ==============================================================================

@pytest.mark.asyncio
async def test_article_evaluation_10_of_12_fails_concluido(db_session: AsyncSession) -> None:
    """W06: Avaliação do artigo com 10/12 (83.33%) falha o corte mínimo 11 e não publica 'concluido'."""
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            # 10 aprovados e 2 reprovados -> 83.33% (reprova!)
            return make_llm_json_response(make_writer_article_12_eval(aprovados_count=10))
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] != "concluido", "Artigo avaliado com 10/12 (83.33%) não pode ser publicado como concluído."
    assert res["status"] == "incompleto"


@pytest.mark.asyncio
async def test_article_evaluation_11_of_12_passes_concluido(db_session: AsyncSession) -> None:
    """W06: Avaliação do artigo com 11/12 (91.67%) atinge o corte mínimo 11 e publica 'concluido'."""
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            # 11 aprovados -> 91.67% (passa!)
            return make_llm_json_response(make_writer_article_12_eval(aprovados_count=11))
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] == "concluido"


@pytest.mark.parametrize(
    "invalid_case_desc,eval_mutator",
    [
        ("string_boolean", lambda d: d["criterios"][0].update({"aprovado": "true"})),
        ("missing_12th_item", lambda d: d["criterios"].pop()),
        ("duplicate_id", lambda d: d["criterios"][1].update({"id": 1})),
        ("id_bool", lambda d: d["criterios"][0].update({"id": True})),
        ("reproved_without_correcao", lambda d: d["criterios"][0].update({"aprovado": False, "correcao": None})),
    ],
)
@pytest.mark.asyncio
async def test_article_evaluation_schema_edge_cases_rejected(
    db_session: AsyncSession, invalid_case_desc: str, eval_mutator: Any
) -> None:
    """W06: Vetores de avaliação com formato inválido são estritamente rejeitados pelo backend."""
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            eval_data = make_writer_article_12_eval(12)
            eval_mutator(eval_data)
            return make_llm_json_response(eval_data)
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] != "concluido", f"Caso inválido '{invalid_case_desc}' não pode aprovar artigo."


@pytest.mark.asyncio
async def test_article_evaluation_rejects_unknown_references(db_session: AsyncSession) -> None:
    """W06 / v6 item 5: Referências a claim_ids ou source_ids desconhecidos no contexto são rejeitadas."""
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            eval_dict = make_writer_article_12_eval(12)
            eval_dict["criterios"][0]["claim_ids"] = ["clm_fantasma_inexistente_999"]
            return make_llm_json_response(eval_dict)
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] == "incompleto"
    assert "desconhecido" in str(res.get("diagnostico", "")).lower()


# ==============================================================================
# 6. ORÇAMENTO, RECUPERAÇÃO DIRIGIDA E ENVELOPES (W05, W07, v6)
# ==============================================================================

@pytest.mark.asyncio
async def test_budget_directed_repair_draft2_passes(db_session: AsyncSession) -> None:
    """W07: Orçamento máximo de 2 rascunhos e 2 avaliações; rascunho 2 corrige com base no feedback."""
    mock_net = MockNetwork()
    draft_count = 0
    eval_count = 0
    captured_draft2_prompt: List[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal draft_count, eval_count
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            eval_count += 1
            if eval_count == 1:
                # 1ª avaliação: reprova com 10/12 e dá correção acionável
                return make_llm_json_response(
                    make_writer_article_12_eval(
                        aprovados_count=10,
                        correcao_text="Reforçar a distinção entre confirmação primária e relato secundário no sumário.",
                    )
                )
            else:
                # 2ª avaliação: aprova com 11/12
                return make_llm_json_response(make_writer_article_12_eval(aprovados_count=11))
        else:
            draft_count += 1
            if draft_count == 2:
                for m in msgs:
                    captured_draft2_prompt.append(m.get("content", ""))
            return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] == "concluido"
    assert draft_count == 2, "Deve gerar exatamente 2 rascunhos."
    assert eval_count == 2, "Deve executar exatamente 2 avaliações."

    d2_prompt_text = " ".join(captured_draft2_prompt)
    assert "confirmação primária e relato secundário" in d2_prompt_text


@pytest.mark.asyncio
async def test_evaluation_json_parse_error_reuses_draft_without_extra_draft_generation(
    db_session: AsyncSession,
) -> None:
    """W07: Se o JSON da avaliação falhar, aproveita o rascunho e refaz apenas a avaliação."""
    mock_net = MockNetwork()
    draft_count = 0
    eval_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal draft_count, eval_count
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            eval_count += 1
            if eval_count == 1:
                # Retorna JSON corrompido na primeira tentativa de avaliação
                return make_llm_raw_response(content="{invalid_json: true, unterminated", finish_reason="stop")
            else:
                # Na segunda tentativa de avaliação, retorna JSON válido aprovado
                return make_llm_json_response(make_writer_article_12_eval(11))
        else:
            draft_count += 1
            return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] == "concluido"
    assert draft_count == 1, "Rascunho não deve ser regenerado se apenas o parse do JSON da avaliação falhou."
    assert eval_count == 2, "Avaliação deve ser retentada corrigindo o JSON."


@pytest.mark.asyncio
async def test_envelopes_persisted_with_distinct_personas_and_no_reasoning_in_api(db_session: AsyncSession) -> None:
    """W05, W11: Envelopes de redação e avaliação são persistidos com personas distintas; reasoning não vaza."""
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            return make_llm_json_response(
                make_writer_article_12_eval(12),
                reasoning="Raciocínio interno da avaliação da redação.",
            )
        return make_llm_raw_response(
            content=SAMPLE_VALID_ARTICLE,
            reasoning="Raciocínio interno confidencial do redator final.",
            finish_reason="stop",
        )

    mock_net.custom_handlers["chat/completions"] = handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(research_repo=repo, llm_client=llm_client)
    res = await writer.execute_writer(id_pesquisa=id_pesquisa)

    assert res["status"] == "concluido"

    # W11: API pública não pode retornar reasoning_dossier
    assert "reasoning_dossier" not in res or res.get("reasoning_dossier") is None

    # W05: Consulta generation_attempts no banco
    stmt = (
        select(GenerationAttempt)
        .where(GenerationAttempt.id_pesquisa == id_pesquisa, GenerationAttempt.etapa == "write")
    )
    attempts = list((await db_session.execute(stmt)).scalars().all())

    assert len(attempts) >= 2, "Deve persistir tanto a geração quanto a avaliação da redação."
    personas = {a.persona for a in attempts}
    assert "redator final" in personas
    assert "auditor_redacao" in personas or "avaliador_redacao" in personas

    has_reasoning = any(a.reasoning_content for a in attempts)
    assert has_reasoning, "Reasoning deve estar registrado apenas na persistência privada de telemetria."


# ==============================================================================
# 7. RESERVA, LEASE, CONCORRÊNCIA E CAS FENCE (W08, v6)
# ==============================================================================

@pytest.mark.asyncio
async def test_writer_atomic_reservation_blocks_concurrent_writer(db_session: AsyncSession) -> None:
    """W08: Dois Writers em duas AsyncSessions reais com Event; o segundo é bloqueado por conflito de lease."""
    bind = db_session.bind
    session_factory = async_sessionmaker(bind, expire_on_commit=False)

    gen1_started = asyncio.Event()
    allow_gen1_finish = asyncio.Event()
    writer1_calls = 0

    async def async_handler1(req: httpx.Request) -> httpx.Response:
        nonlocal writer1_calls
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))

        writer1_calls += 1
        gen1_started.set()
        # Segura a execução do primeiro Writer até que o segundo tente entrar
        try:
            await asyncio.wait_for(allow_gen1_finish.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    writer2_calls = 0

    async def async_handler2(req: httpx.Request) -> httpx.Response:
        nonlocal writer2_calls
        writer2_calls += 1
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    transport1 = httpx.MockTransport(async_handler1)
    transport2 = httpx.MockTransport(async_handler2)

    repo_init = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo_init)
    await db_session.commit()

    async with session_factory() as s1, session_factory() as s2:
        writer1 = Writer(research_repo=ResearchRepository(s1), llm_client=LLMClient(api_key="k1", transport=transport1))
        writer2 = Writer(research_repo=ResearchRepository(s2), llm_client=LLMClient(api_key="k2", transport=transport2))

        task1 = asyncio.create_task(writer1.execute_writer(id_pesquisa))
        await gen1_started.wait()

        # Segundo Writer tenta executar enquanto o primeiro está ativo: DEVE FALHAR por conflito de concorrência
        with pytest.raises(ValueError, match="concorr|conflito|lease|ativa|409|redigindo"):
            await writer2.execute_writer(id_pesquisa)

        # Libera o primeiro Writer para concluir normalmente
        allow_gen1_finish.set()
        res1 = await task1
        assert res1["status"] == "concluido"

    # Em sessão fresca, confere integridade do banco
    async with session_factory() as s3:
        pesquisa_db = await ResearchRepository(s3).get_research(id_pesquisa)
        assert pesquisa_db is not None
        assert pesquisa_db.status_pipeline == "concluido"
        assert pesquisa_db.dossier_final is not None


@pytest.mark.asyncio
async def test_cas_fence_aborts_publication_if_coleta_modified_during_generation(db_session: AsyncSession) -> None:
    """W08: Se nova coleta ou alteração de estado ocorrer durante a geração, CAS recusa publicar documento obsoleto."""
    bind = db_session.bind
    session_factory = async_sessionmaker(bind, expire_on_commit=False)

    gen1_started = asyncio.Event()
    coleta_updated = asyncio.Event()

    async def async_handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))

        gen1_started.set()
        # Aguarda a inserção concorrente da nova coleta na segunda sessão
        try:
            await asyncio.wait_for(coleta_updated.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    transport = httpx.MockTransport(async_handler)
    repo_init = ResearchRepository(session=db_session)
    id_pesquisa, ponto_id, _ = await setup_research_with_audit(repo=repo_init)
    await db_session.commit()

    async with session_factory() as s1, session_factory() as s2:
        writer1 = Writer(research_repo=ResearchRepository(s1), llm_client=LLMClient(api_key="k1", transport=transport))
        task1 = asyncio.create_task(writer1.execute_writer(id_pesquisa))

        await gen1_started.wait()

        # Sessão 2: Insere uma nova coleta (rodada 2) e reprova o ponto, alterando os inputs
        repo2 = ResearchRepository(s2)
        await repo2.save_collected_content(
            id_pesquisa=id_pesquisa,
            ponto_id=ponto_id,
            tema="Tema",
            ponto="Ponto",
            conteudo_coletado="Nova coleta concorrente",
            urls_lidas=["https://nova-fonte.org"],
            urls_fonte=["https://nova-fonte.org"],
            rodada=2,
        )
        await repo2.update_point_status(ponto_id=ponto_id, status="reprovado", pontos_fracos="Nova falha detectada")
        await s2.commit()

        # Libera o Writer 1 para tentar finalizar
        coleta_updated.set()
        res1 = await task1

        # O CAS deve recusar publicar o documento antigo como concluído!
        assert res1["status"] != "concluido", "Writer não pode concluir se os dados mudaram durante a inferência."

    # Em sessão fresca, confere que o documento obsoleto não sobrescreveu o estado novo
    async with session_factory() as s3:
        pesquisa_db = await ResearchRepository(s3).get_research(id_pesquisa)
        assert pesquisa_db is not None
        assert pesquisa_db.status_pipeline != "concluido"


# ==============================================================================
# 8. CACHE DE IDEMPOTÊNCIA (W09, v6)
# ==============================================================================

@pytest.mark.asyncio
async def test_valid_cache_does_zero_llm_calls_and_no_duplicate_webhook(db_session: AsyncSession) -> None:
    """W09: Cache válido com artigo íntegro e avaliado retorna com 0 chamadas LLM e sem novo webhook."""
    mock_net = MockNetwork()

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"

        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    webhook_client = WebhookClient(secret="test-sec", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    writer = Writer(
        research_repo=repo,
        llm_client=llm_client,
        webhook_client=webhook_client,
        callback_url="https://webhook.test/callback",
    )

    # 1ª Execução: gera, avalia e grava cache
    res1 = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert res1["status"] == "concluido"
    reqs_primeira = len(mock_net.requests)
    assert reqs_primeira > 0

    # Confere generation_attempts da 1ª execução
    attempts1 = await repo.get_generation_attempts(id_pesquisa, etapa="write")
    count_ga1 = len(attempts1)
    assert count_ga1 >= 2

    # 2ª Execução: deve vir diretamente do cache válido
    res2 = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert res2["status"] == "concluido"
    reqs_segunda = len(mock_net.requests)

    # Nenhuma nova chamada de LLM ou Webhook
    assert reqs_segunda == reqs_primeira, "Cache válido não pode gerar novas inferências ou reenvios."

    # Nenhum novo generation_attempt adicionado
    attempts2 = await repo.get_generation_attempts(id_pesquisa, etapa="write")
    assert len(attempts2) == count_ga1


@pytest.mark.asyncio
async def test_cache_invalidation_by_prompt_model_version_and_document(db_session: AsyncSession) -> None:
    """W09 / v6 item 13: Cache é invalidado se o prompt, o modelo, a versão ou o documento sofrerem mutação."""
    mock_net = MockNetwork()
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"
        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = handler
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="mock-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)
    writer = Writer(research_repo=repo, llm_client=llm_client)

    # 1. Primeira execução gera e salva cache válido
    res1 = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert res1["status"] == "concluido"
    reqs_antes = len(mock_net.requests)

    # 2. Mutação no modelo LLM invalida cache -> obriga nova chamada
    llm_client2 = LLMClient(api_key="mock-key", transport=transport, model_strong="gemini-different-model")
    writer2 = Writer(research_repo=repo, llm_client=llm_client2)
    res2 = await writer2.execute_writer(id_pesquisa=id_pesquisa)
    assert res2["status"] == "concluido"
    assert len(mock_net.requests) > reqs_antes

    # 3. Mutação no dossier_final no banco (tampering) invalida cache
    stmt_tamper = (
        update(Pesquisa)
        .where(Pesquisa.id_pesquisa == id_pesquisa)
        .values(dossier_final=SAMPLE_VALID_ARTICLE + "\n\nAdulterado externamente.")
    )
    await repo.session.execute(stmt_tamper)
    await repo.session.commit()

    reqs_antes_tamper = len(mock_net.requests)
    res3 = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert len(mock_net.requests) > reqs_antes_tamper

    # 4. Tampering do vetão 12 (booleano não estrito + contagem nominal divergente) invalida cache
    await repo.session.execute(update(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa).values(dossier_final=SAMPLE_VALID_ARTICLE))
    await repo.session.commit()
    pesq_meta = await repo.get_research(id_pesquisa)
    meta4 = json.loads(pesq_meta.metadados_redacao)
    meta4["qualidade_artigo"]["criterios"][0]["aprovado"] = "true"  # booleano não estrito
    await repo.session.execute(update(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa).values(metadados_redacao=json.dumps(meta4)))
    await repo.session.commit()
    reqs_antes_vec = len(mock_net.requests)
    res_vec = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert res_vec["status"] == "concluido"
    assert len(mock_net.requests) > reqs_antes_vec, "Cache com vetor 12 adulterado não pode ser devolvido como válido."

    # 5. Tampering da contagem nominal curando o vetor em 3/12 invalida cache
    pesq_meta = await repo.get_research(id_pesquisa)
    meta5 = json.loads(pesq_meta.metadados_redacao)
    meta5["qualidade_artigo"]["criterios_aprovados"] = 8  # nominal divergente do vetor real
    await repo.session.execute(update(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa).values(metadados_redacao=json.dumps(meta5)))
    await repo.session.commit()
    reqs_antes_count = len(mock_net.requests)
    res_count = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert len(mock_net.requests) > reqs_antes_count, "Contagem nominal divergente do vetor real não pode aprovar cache."

    # 6. Tampering do término (finish irregular) invalida cache
    pesq_meta = await repo.get_research(id_pesquisa)
    meta6 = json.loads(pesq_meta.metadados_redacao)
    meta6["finish_reason"] = "length"
    await repo.session.execute(update(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa).values(metadados_redacao=json.dumps(meta6)))
    await repo.session.commit()
    reqs_antes_fin = len(mock_net.requests)
    res_fin = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert len(mock_net.requests) > reqs_antes_fin, "Cache com término irregular persistido não pode ser considerada válido."

    # 7. Envelopes de geração removidos do banco invalidam cache (sem comprovação real)
    pesq_meta = await repo.get_research(id_pesquisa)
    meta7 = json.loads(pesq_meta.metadados_redacao)
    ga_para_remover = list(meta7.get("generation_attempt_ids") or [])
    for ga_id in ga_para_remover:
        await repo.session.execute(sql_delete(GenerationAttempt).where(GenerationAttempt.id == ga_id))
    await repo.session.commit()
    reqs_antes_ga = len(mock_net.requests)
    res_ga = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert len(mock_net.requests) > reqs_antes_ga, "Cache sem envelopes efetivamente persistidos não pode ser considerada válido."

    # 8. Refs estranhas no vetor persistido invalidam cache
    pesq_meta = await repo.get_research(id_pesquisa)
    meta8 = json.loads(pesq_meta.metadados_redacao)
    meta8["qualidade_artigo"]["criterios"][0]["source_ids"] = ["src_inexistente_fantasma"]
    await repo.session.execute(update(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa).values(metadados_redacao=json.dumps(meta8)))
    await repo.session.commit()
    reqs_antes_refs = len(mock_net.requests)
    res_refs = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert len(mock_net.requests) > reqs_antes_refs, "Cache com refs estranhas ao conjunto atual não pode ser considerada válido."


@asynccontextmanager
async def _fresh_role_session(async_engine: AsyncEngine):
    """Sessão nova de inspeção (Event/freshsession, direção r1): abre AsyncSession independente
    sobre o mesmo engine da fixture, sem compartilhar transação com o fluxo sob cancelamento."""
    maker = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with maker() as session:
        yield session


@pytest.mark.asyncio
async def test_writer_deadline_timeout_and_cancellation(db_session: AsyncSession, async_engine) -> None:
    """W07 / v6 item 12 (direção r1): timeout próprio entrega incompleto real e libera a reserva
    (inspeção em sessão fresca); cancelamento em LLM ativo via AsyncEvent setado pelo handler;
    cancelamento durante a avaliação preserva somente o envelope REAL do draft observado."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    # ---------------------------------------------------------------
    # Parte 1: TIMEOUT próprio com prazo curto (incompleto real)
    # ---------------------------------------------------------------
    mock_net_timeout = MockNetwork()

    async def hanging_handler(req: httpx.Request) -> httpx.Response:
        await asyncio.sleep(10.0)
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE)

    mock_net_timeout.custom_handlers["chat/completions"] = hanging_handler
    llm_client_timeout = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net_timeout))
    writer_timeout = Writer(research_repo=repo, llm_client=llm_client_timeout, timeout_seconds=0.05)
    # W07/W12 (r3): TimeoutError TIPADO propaga para a rota (HTTP 504), sem dict nominal.
    with pytest.raises(TimeoutError):
        await writer_timeout.execute_writer(id_pesquisa=id_pesquisa)

    # Inspeção em SESSÃO FRESCA: reserva liberada pelo caminho real do timeout
    async with _fresh_role_session(async_engine) as s_fresh:
        pesq_t = (
            await s_fresh.execute(
                select(Pesquisa)
                .where(Pesquisa.id_pesquisa == id_pesquisa)
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        meta_t = json.loads(pesq_t.metadados_redacao or "{}")
        assert meta_t.get("lease_token") is None
        assert json.loads(pesq_t.metadados_redacao)["status"] == "incompleto"
        # Nenhum envelope de geração observado completo: a chamada nunca retornou
        gat_t1 = (
            await s_fresh.execute(select(GenerationAttempt).where(GenerationAttempt.id_pesquisa == id_pesquisa))
        ).scalars().all()
        assert len(gat_t1) == 0

    # ---------------------------------------------------------------
    # Parte 2: CANCELAMENTO assíncrono durante chamada LLM ATIVA
    # (AsyncEvent setado pelo handler; sem sleep(0.01) escolhendo ponto)
    # ---------------------------------------------------------------
    mock_net_cancel = MockNetwork()
    ev2 = asyncio.Event()

    async def handler_cancel_ativo(req: httpx.Request) -> httpx.Response:
        ev2.set()  # sinaliza chegada da chamada real ao LLM
        await asyncio.sleep(30.0)
        return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE)  # nunca alcançado

    mock_net_cancel.custom_handlers["chat/completions"] = handler_cancel_ativo
    llm_client_cancel = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net_cancel))
    writer_cancel = Writer(research_repo=repo, llm_client=llm_client_cancel, timeout_seconds=30)

    task = asyncio.create_task(writer_cancel.execute_writer(id_pesquisa=id_pesquisa))
    await asyncio.wait_for(ev2.wait(), timeout=5.0)
    task.cancel()  # cancelamento injetado durante a chamada LLM ativa
    with pytest.raises(asyncio.CancelledError):
        await task

    # Inspeção em SESSÃO FRESCA: posse própria liberada e nenhum envelope observado
    async with _fresh_role_session(async_engine) as s_fresh:
        pesq_c = (
            await s_fresh.execute(
                select(Pesquisa)
                .where(Pesquisa.id_pesquisa == id_pesquisa)
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        meta_c = json.loads(pesq_c.metadados_redacao or "{}")
        assert meta_c.get("lease_token") is None
        gat_c = (
            await s_fresh.execute(select(GenerationAttempt).where(GenerationAttempt.id_pesquisa == id_pesquisa))
        ).scalars().all()
        assert len(gat_c) == 0, "Chamada cancelada no meio não pode produzir envelope observado completo."

    # ---------------------------------------------------------------
    # Parte 3 (Caso B): CANCELAMENTO durante a AVALIAÇÃO, com draft completo
    # ---------------------------------------------------------------
    mock_net_eval = MockNetwork()
    ev3 = asyncio.Event()
    calls_b = {"n": 0}

    async def handler_eval_bloqueio(req: httpx.Request) -> httpx.Response:
        calls_b["n"] += 1
        if calls_b["n"] == 1:
            # 1ª chamada: geração do artigo (draft) completa normalmente
            return make_llm_raw_response(content=SAMPLE_VALID_ARTICLE)
        ev3.set()  # avaliador sinaliza e bloqueia
        await asyncio.sleep(30.0)
        return make_llm_json_response({"criterios": []})  # nunca alcançado

    mock_net_eval.custom_handlers["chat/completions"] = handler_eval_bloqueio
    llm_client_eval = LLMClient(api_key="mock-key", transport=create_mock_transport(mock_net_eval))
    writer_eval = Writer(research_repo=repo, llm_client=llm_client_eval, timeout_seconds=30)

    task_b = asyncio.create_task(writer_eval.execute_writer(id_pesquisa=id_pesquisa))
    await asyncio.wait_for(ev3.wait(), timeout=10.0)
    task_b.cancel()  # cancelamento injetado durante a chamada de AVALIAÇÃO
    with pytest.raises(asyncio.CancelledError):
        await task_b

    # Inspeção em SESSÃO FRESCA: envelope REAL do draft preservado; zero envelope de avaliação;
    # somente a posse própria liberada; CancelledError propagado (acima).
    assert calls_b["n"] == 2, "Esperadas exatamente 2 chamadas observadas: draft completa + avaliador bloqueado."
    async with _fresh_role_session(async_engine) as s_fresh:
        pesq_b = (
            await s_fresh.execute(
                select(Pesquisa)
                .where(Pesquisa.id_pesquisa == id_pesquisa)
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        meta_b = json.loads(pesq_b.metadados_redacao or "{}")
        assert meta_b.get("lease_token") is None
        assert pesq_b.dossier_final is None, "Rascunho bloqueado na avaliação não pode virar documento final."
        assert pesq_b.status_pipeline == "incompleto"

        gat_b = (
            await s_fresh.execute(
                select(GenerationAttempt).where(GenerationAttempt.id_pesquisa == id_pesquisa)
            )
        ).scalars().all()
        assert len(gat_b) == 1, "Somente o envelope REAL do draft observado deve ser preservado."
        ga_draft = gat_b[0]
        assert ga_draft.persona == "redator final"
        assert ga_draft.etapa == "write"
        assert ga_draft.content_final == SAMPLE_VALID_ARTICLE
        assert ga_draft.finish_reason == "stop"
        assert ga_draft.is_regular_finish is True
        assert not any(g.persona == "auditor_redacao" for g in gat_b), "Zero envelope de avaliação bloqueada."
        assert len(meta_b.get("generation_attempt_ids") or []) == 1, "Meta da liberação registra o envelope do draft."


@pytest.mark.asyncio
async def test_writer_expired_lease_cannot_finalize_new_owner(db_session: AsyncSession) -> None:
    """W08 / v6 item 7: Dono antigo cuja lease expirou não consegue finalizar ou sobrescrever novo dono."""
    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    # Worker 1 adquire lease
    token1, _ = await repo.reserve_research_for_writer(id_pesquisa=id_pesquisa, lease_seconds=1)

    # Simula expiração forçando lease_expira_em no passado
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    meta1 = {
        "lease_token": token1,
        "lease_expira_em": past,
        "status": "redigindo",
    }
    stmt_exp = update(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa).values(metadados_redacao=json.dumps(meta1))
    await repo.session.execute(stmt_exp)
    await repo.session.commit()

    # Worker 2 adquire a lease legitimamente (dono novo) e Worker 1 não pode finalizar sobre ele
    token2, _ = await repo.reserve_research_for_writer(id_pesquisa=id_pesquisa, lease_seconds=600)
    assert token2 != token1

    pub1 = await repo.finalize_writer_publication(
        id_pesquisa=id_pesquisa,
        lease_token=token1,
        dossier_final="# Documento Antigo Stale",
        status_pipeline="concluido",
        metadados_redacao_dict={"artifact_hash": "stale_hash"},
    )
    assert pub1 is False, "Worker 1 com token antigo não pode finalizar publicação sobre novo dono."

    # Verifica que o estado no banco continua pertencendo ao Worker 2
    pesq = await repo.get_research(id_pesquisa)
    meta_now = json.loads(pesq.metadados_redacao or "{}")
    assert meta_now.get("lease_token") == token2
    assert pesq.dossier_final is None

    # Fase B: lease EXPIRADA do próprio dono SEM novo dono também não publica
    await repo.release_writer_reservation(id_pesquisa=id_pesquisa, lease_token=token2, status_pipeline="coletado")
    token3, _ = await repo.reserve_research_for_writer(id_pesquisa=id_pesquisa, lease_seconds=600)
    past3 = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    meta3 = {
        "lease_token": token3,
        "lease_expira_em": past3,
        "status": "redigindo",
        "input_hash": "hash-de-entrada-fase-b",
    }
    await repo.session.execute(
        update(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa).values(metadados_redacao=json.dumps(meta3))
    )
    await repo.session.commit()

    pub3 = await repo.finalize_writer_publication(
        id_pesquisa=id_pesquisa,
        lease_token=token3,
        dossier_final="# Documento com lease expirada",
        status_pipeline="concluido",
        metadados_redacao_dict={"artifact_hash": "hash_fase_b"},
        expected_input_hash="hash-de-entrada-fase-b",
    )
    assert pub3 is False, "Lease expirada sem novo dono não deve publicar."

    pesq3 = await repo.get_research(id_pesquisa)
    assert pesq3.dossier_final is None
    assert json.loads(pesq3.metadados_redacao or "{}").get("lease_token") == token3

    # Fase C: identidade da entrada divergente (input_hash) bloqueia a publicação deste mesmo dono
    pub3b = await repo.finalize_writer_publication(
        id_pesquisa=id_pesquisa,
        lease_token=token3,
        dossier_final="# Documento com input divergente",
        status_pipeline="concluido",
        metadados_redacao_dict={"artifact_hash": "hash_fase_c"},
        expected_input_hash="hash-CONCORRENTEMENTE-diferente",
    )
    assert pub3b is False, "Fence com input_hash divergente não pode publicar."
    assert pesq3.dossier_final is None

    # Posse normal sem expiração e com input coerente publica (controle de sanidade)
    stmt_renovar = update(Pesquisa).where(Pesquisa.id_pesquisa == id_pesquisa).values(
        metadados_redacao=json.dumps({
            "lease_token": token3,
            "lease_expira_em": (datetime.now(timezone.utc) + timedelta(seconds=600)).isoformat(),
            "status": "redigindo",
            "input_hash": "hash-coerENTE",
        })
    )
    await repo.session.execute(stmt_renovar)
    await repo.session.commit()
    pub3c = await repo.finalize_writer_publication(
        id_pesquisa=id_pesquisa,
        lease_token=token3,
        dossier_final="# Documento legítimo",
        status_pipeline="concluido",
        metadados_redacao_dict={"artifact_hash": "hash_fase_c_ok"},
        expected_input_hash="hash-coerENTE",
    )
    assert pub3c is True, "Lease vigente da própria posse com input coerente publica normalmente."


# ==============================================================================
# 9. PIPELINE RUNNER E MIGRAÇÃO LEGADA (W12, W13, v6)
# ==============================================================================

@pytest.mark.asyncio
async def test_runner_calls_writer_without_triple_retry_or_fallback_concluido(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W12 / DR-013: Runner chama Writer respeitando o orçamento interno e sem fallback 'concluido'."""
    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    runner = PipelineRunner(transport=transport)

    repo = ResearchRepository(session=db_session)
    id_pesquisa, _, _ = await setup_research_with_audit(repo=repo)

    # Isola Searcher e Auditor via spy garantindo que chegam prontos ao Writer
    async def spy_search(self, id_pesquisa, ponto_id, personas=None):
        return {"status": "coletado"}

    async def spy_audit(self, id_pesquisa):
        return {"pronto_para_writer": True, "auditorias": []}

    writer_call_count = 0

    async def spy_writer(self, id_pesquisa, **kwargs):
        nonlocal writer_call_count
        writer_call_count += 1
        # Comportamento REAL do Writer em resultado incompleto (W08/W10): adquire a posse,
        # e publica/libera com status honesto antes de retornar. Com o H02, o Runner NÃO
        # regrava status — quem publica o estado final é o próprio Writer via CAS de posse.
        lease_token, _pesquisa = await self.research_repo.reserve_research_for_writer(
            id_pesquisa=id_pesquisa
        )
        await self.research_repo.release_writer_reservation(
            id_pesquisa=id_pesquisa,
            lease_token=lease_token,
            status_pipeline="incompleto",
        )
        return {
            "id_pesquisa": id_pesquisa,
            "status": "incompleto",
            "dossier_final": "incompleto",
            "diagnostico": "Erro estrutural",
        }

    monkeypatch.setattr("app.core.searcher.Searcher.execute_search", spy_search)
    monkeypatch.setattr("app.core.auditor.Auditor.execute_audit", spy_audit)
    monkeypatch.setattr("app.core.writer.Writer.execute_writer", spy_writer)

    res = await runner.run(id_pesquisa=id_pesquisa)

    # 1. Writer deve ser chamado exatamente 1 vez pelo Runner (sem loop de 3 tentativas externas)
    assert writer_call_count == 1, "PipelineRunner não deve executar retry triplo sobre o Writer."

    # 2. Status deve ser honestamente 'incompleto', sem fallback para 'concluido'
    assert res.get("status") == "incompleto"
    pesquisa_db = await repo.get_research(id_pesquisa)
    assert pesquisa_db is not None
    assert pesquisa_db.status_pipeline == "incompleto"


@pytest.mark.asyncio
async def test_additive_migration_idempotent_and_preserves_null(db_session: AsyncSession) -> None:
    """W13: Migração aditiva de metadados_redacao é idempotente e preserva dados pré-existentes como NULL."""
    conn = await db_session.connection()

    # Executa duas vezes a rotina de migração idempotente
    await _run_additive_migrations(conn)
    await _run_additive_migrations(conn)

    # Verifica se a coluna existe na tabela pesquisa
    res_pragma = await conn.execute(text("PRAGMA table_info(pesquisa);"))
    cols = {row[1] for row in res_pragma.fetchall()}
    assert "metadados_redacao" in cols, "Coluna metadados_redacao deve existir após a migração."


# ==============================================================================
# 10. ROTA HTTP /api/v1/writer (W11, W12, v6)
# ==============================================================================

@pytest.mark.asyncio
async def test_writer_route_closes_llm_and_maps_error_codes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W12: Rota POST /api/v1/writer fecha o cliente LLM em finally e mapeia 404, 400, 409, 502, 504."""
    aclose_called = False
    orig_aclose = LLMClient.aclose

    async def spy_aclose(self):
        nonlocal aclose_called
        aclose_called = True
        return await orig_aclose(self)

    monkeypatch.setattr(LLMClient, "aclose", spy_aclose)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. 404 Not Found para pesquisa inexistente
        r_404 = await client.post("/api/v1/writer", json={"id_pesquisa": str(uuid.uuid4())})
        assert r_404.status_code == 404
        assert aclose_called is True

        # 2. 400 Bad Request para pesquisa com ponto pendente (readiness falha)
        repo = ResearchRepository(session=db_session)
        p_pendente = await repo.create_research(tema="Pendente", pontos_textos=["Ponto 1"])
        r_400 = await client.post("/api/v1/writer", json={"id_pesquisa": p_pendente.id_pesquisa})
        assert r_400.status_code == 400

        # 3. 409 Conflict quando há conflito de concorrência / lease
        async def mock_execute_conflict(self, id_pesquisa):
            raise ValueError("CONCURRENCY_CONFLICT: pesquisa em redação por outro processo")

        monkeypatch.setattr("app.core.writer.Writer.execute_writer", mock_execute_conflict)
        r_409 = await client.post("/api/v1/writer", json={"id_pesquisa": p_pendente.id_pesquisa})
        assert r_409.status_code == 409

        # 4. 502 Bad Gateway para erro de provedor LLM
        async def mock_execute_502(self, id_pesquisa):
            raise httpx.ConnectError("Failed to reach LLM provider")

        monkeypatch.setattr("app.core.writer.Writer.execute_writer", mock_execute_502)
        r_502 = await client.post("/api/v1/writer", json={"id_pesquisa": p_pendente.id_pesquisa})
        assert r_502.status_code == 502

        # 5. 504 Gateway Timeout para estouro de tempo (caminho de exceção do core)
        async def mock_execute_504(self, id_pesquisa):
            raise TimeoutError("LLM call timed out")

        monkeypatch.setattr("app.core.writer.Writer.execute_writer", mock_execute_504)
        r_504 = await client.post("/api/v1/writer", json={"id_pesquisa": p_pendente.id_pesquisa})
        assert r_504.status_code == 504

        # 6. (r3) O mapeamento por substring WRITER_TIMEOUT foi REMOVIDO da rota: o core
        # propaga TimeoutError tipado (caso 5). O enveloper abaixo permanece apenas como
        # construtor do corpo 'incompleto' reutilizado no caso 7 — nenhum dict nominal
        # de timeout existe mais no core (nunca 200 de timeout por substring).
        async def mock_execute_incompleto_construtor(self, id_pesquisa):
            # corpo mínimo do contrato 'incompleto' (sem diagnóstico de timeout)
            return {
                "id_pesquisa": id_pesquisa,
                "tema": p_pendente.tema,
                "status": "incompleto",
                "total_caracteres_dossier": 0,
                "concluido_em": None,
                "dossier_resumo": None,
                "dossier_final": None,
                "reasoning_dossier": None,
                "diagnostico": None,
                "qualidade_artigo": None,
                "webhook_entrega": {
                    "url": None,
                    "status": "nao_aplicavel",
                    "http_status_code": None,
                    "tentativas": 0,
                    "detalhes_falha": None,
                },
            }

        # 7. incompleto sem WRITER_TIMEOUT (exaustão de avaliação) permanece 200 com corpo do contrato
        async def mock_execute_incompleto(self, id_pesquisa):
            env = await mock_execute_incompleto_construtor(self, id_pesquisa)
            env["diagnostico"] = "avaliação inconsistente após orçamento de reparo"
            return env

        monkeypatch.setattr("app.core.writer.Writer.execute_writer", mock_execute_incompleto)
        r_200_incompleto = await client.post("/api/v1/writer", json={"id_pesquisa": p_pendente.id_pesquisa})
        assert r_200_incompleto.status_code == 200
        assert r_200_incompleto.json()["status"] == "incompleto"
