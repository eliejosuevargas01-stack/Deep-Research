# -*- coding: utf-8 -*-
"""Testes de reprodução e regressão para BUG-20261023-YXTQ (DR-003, DR-011, DR-012).

Alvo: Validação rigorosa de integridade e completude do dossiê do Writer.
Defeito demonstrado:
1. O Writer conclui como 'concluido' um dossiê de 10.641 caracteres contendo apenas
   as seções 1 e 2, com corte abrupto de frase e sem as seções 3 e 4.
2. O cache de idempotência devolve dossiê corrompido/incompleto como 'concluido' de imediato.
3. Cercas de código Markdown abertas e finish_reason='length' não impedem conclusão.
4. Eixos reprovados são aceitos sem distinção, gerando sucesso silencioso.
"""
from datetime import datetime, timezone
import json
import uuid
import pytest
import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConteudoColetado
from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from app.core.writer import Writer
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_audit_acceptance import CANONICAL_PLANO, make_audit_12_vector, make_standard_coleta_metadata
from tests.unit.test_reproduction_gate1_helpers import make_llm_raw_response
from tests.unit.test_writer_acceptance import make_llm_json_response, make_writer_article_12_eval


# Dossiê real truncado do ensaio fornecido (10.641 caracteres, seções 1 e 2 apenas)
DOSSIER_TRUNCATED_10641 = (
    "# Dossiê Analítico: Falha de Segurança no PHP\n\n"
    "## 1. Sumário Executivo\n\n"
    "Este sumário executivo detalha a recente vulnerabilidade crítica descoberta no ecossistema PHP. "
    + ("Análise introdutória sobre mitigação e impacto em infraestruturas legadas. " * 30)
    + "\n\n## 2. Desenvolvimento dos Eixos Temáticos\n\n"
    "Aprofundamento técnico dos vetores de exploração e análise de patching.\n"
    + ("Detalhamento empírico do buffer overflow e condições de contorno observadas no runtime. " * 80)
    + "\n\nÉ obrigatório atualizar o pacote do PHP via gerenciador de pacotes do SO"
    # Note: corta abruptamente sem ponto final, e NÃO contém seção 3 nem seção 4!
)
# Garante tamanho representativo acima de 10.000 caracteres
if len(DOSSIER_TRUNCATED_10641) < 10641:
    padding = " " + ("detalhe adicional de teste " * ((10641 - len(DOSSIER_TRUNCATED_10641)) // 26 + 1))
    DOSSIER_TRUNCATED_10641 = DOSSIER_TRUNCATED_10641[:10641 - len("É obrigatório atualizar o pacote do PHP via gerenciador de pacotes do SO")] + "É obrigatório atualizar o pacote do PHP via gerenciador de pacotes do SO"


VALID_COMPLETE_DOSSIER = (
    "# Dossiê Analítico Completo: Impacto da IA na Educação\n\n"
    "## 1. Sumário Executivo\n"
    "Síntese completa e aprofundada dos resultados investigados.\n\n"
    "## 2. Desenvolvimento dos Eixos Temáticos\n"
    "Análise dos eixos com evidências canônicas [UNESCO](https://unesdoc.unesco.org/ark:/48223/pf0000377897).\n\n"
    "## 3. Ressalvas e Limitações Metodológicas\n"
    "Declaração explícita de incertezas e dados amostrais pendentes.\n\n"
    "## 4. Referências e Fontes Canônicas\n"
    "1. [UNESCO](https://unesdoc.unesco.org/ark:/48223/pf0000377897)\n"
)


async def _setup_research_for_writer(
    repo: ResearchRepository,
    tema: str,
    pontos_status: list[str],
) -> tuple[str, list[str]]:
    """Cria pesquisa com pontos e evidências para execução do Writer."""
    pesquisa = await repo.create_research(
        tema=tema,
        pontos_textos=[f"Ponto {i+1}" for i in range(len(pontos_status))],
        plano_estruturado=dict(CANONICAL_PLANO),
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    ponto_ids = []
    canonical_url = "https://unesdoc.unesco.org/ark:/48223/pf0000377897"
    for p, status in zip(pontos, pontos_status):
        ponto_ids.append(p.ponto_id)
        coleta_id = str(uuid.uuid4())
        coleta_meta = make_standard_coleta_metadata(source_url=canonical_url)
        is_aprovado = (status == "aprovado")
        coleta_meta["auditorias"] = [
            {
                "id_auditoria": str(uuid.uuid4()),
                "coleta_id": coleta_id,
                "rodada": 1,
                "valido": True,
                "aplicado": True,
                "status": status,
                "criterios": make_audit_12_vector(12 if is_aprovado else 8),
                "criterios_aprovados": 12 if is_aprovado else 8,
                "criterios_minimos": 11,
                "pontuacao_percentual": 100.0 if is_aprovado else 66.67,
                "pontos_fracos": None if is_aprovado else "Fragilidades identificadas",
                "tarefas": [],
                "criado_em": datetime.now(timezone.utc).isoformat(),
            }
        ]
        # Salva conteúdo coletado antes de atualizar o status final da auditoria
        await repo.save_collected_content(
            id_pesquisa=pesquisa.id_pesquisa,
            ponto_id=p.ponto_id,
            tema=tema,
            ponto=p.ponto,
            conteudo_coletado="Evidência factual coletada da web",
            urls_lidas=[canonical_url],
            urls_fonte=[canonical_url],
            metadados_coleta=coleta_meta,
        )
        await repo.session.execute(
            update(ConteudoColetado)
            .where(ConteudoColetado.ponto_id == p.ponto_id)
            .values(id=coleta_id)
        )
        await repo.update_point_status(p.ponto_id, status=status)
    return pesquisa.id_pesquisa, ponto_ids


@pytest.mark.asyncio
async def test_writer_truncated_10641_chars_only_sections_1_and_2_fails_concluido(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Dossiê de 10.641 caracteres sem seções 3 e 4 não pode resultar em 'concluido'.
    
    Cenário real DR-003 / Ensaio PHP:
    O modelo gera 10.641 caracteres contendo apenas as seções 1 e 2 e encerra abruptamente
    no meio de uma frase.
    No código atual, como len(texto) >= 100, o Writer aceita o texto como concluído e
    marca a pesquisa como 'concluido'.
    O comportamento esperado é rejeitar como 'incompleto' devido à ausência das seções
    obrigatórias 3 e 4 e ao truncamento evidente.
    """
    mock_net = MockNetwork()
    # Retorna o texto truncado de 10.641 chars com finish_reason="stop" ou "length"
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_raw_response(
        content=DOSSIER_TRUNCATED_10641,
        finish_reason="stop",
    )
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    id_pesquisa, _ = await _setup_research_for_writer(repo, "Tema Vulnerabilidade PHP", ["aprovado"])

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    writer = Writer(research_repo=repo, llm_client=llm_client)

    resultado = await writer.execute_writer(id_pesquisa=id_pesquisa)

    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL):
    # app/core/writer.py:199 só re-tenta se len < 100! Com 10.641 chars, grava e retorna 'concluido'!
    assert resultado["status"] != "concluido", (
        "DEFEITO CONFIRMADO (BUG-20261023-YXTQ): O Writer concluiu com sucesso um dossiê incompleto "
        "de 10.641 caracteres que possuía apenas as seções 1 e 2 e terminava truncado."
    )
    assert resultado["status"] == "incompleto"


@pytest.mark.asyncio
async def test_writer_cached_incomplete_dossier_not_returned_as_concluido(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Dossiê incompleto salvo no banco não pode ser retornado como 'concluido' via cache.
    
    Cenário DR-003 / F-WRITER-SPEC-01:
    A pesquisa já possui no banco um dossier_final gravado anteriormente, mas com
    conteúdo incompleto (10.641 chars, sem seções 3 e 4).
    O código de idempotência (linhas 66-87 de writer.py) retorna imediatamente 'status': 'concluido'
    sem validar a integridade estrutural do artefato em cache.
    """
    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    id_pesquisa, _ = await _setup_research_for_writer(repo, "Tema Cache Incompleto", ["aprovado"])
    # Grava o dossiê truncado diretamente no banco
    await repo.update_research_dossier(
        id_pesquisa=id_pesquisa,
        dossier_final=DOSSIER_TRUNCATED_10641,
    )

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    writer = Writer(research_repo=repo, llm_client=llm_client)

    resultado = await writer.execute_writer(id_pesquisa=id_pesquisa)

    # CONTRATO (BUG-20261023-YXTQ): o dossiê truncado persistido nunca pode voltar
    # como 'concluido'. A validação real do cache/input-hash/íntegra (W09, writer.py
    # _validar_cache_redacao) recusa o artefato truncado; o Writer então executa o
    # fluxo completo de geração. Antes, essa recusa só era observada indiretamente
    # porque o despacho errado do mock (JSON do planejador) sempre derrubava a
    # avaliação; com o roteamento por system role do avaliador corrigido (r5),
    # a regeneração fresca é honesta e 'concluido' só é aceitável com o dossiê
    # novo ÍNTEGRO publicado — nunca o truncado, e sempre com corte 11/12.
    if resultado["status"] == "concluido":
        dossier_publicado = resultado.get("dossier_final") or ""
        assert dossier_publicado != DOSSIER_TRUNCATED_10641, (
            "O dossiê truncado (sem seções 3 e 4) não pode ser publicado como concluido."
        )
        for secao in ("## 1. Sumário Executivo", "## 2. Desenvolvimento dos Eixos Temáticos",
                      "## 3. Ressalvas e Limitações Metodológicas", "## 4. Referências e Fontes Canônicas"):
            assert secao in dossier_publicado, f"Dossiê gerado pressupõe seção íntegra ausente: {secao}"
        qualidade = resultado.get("qualidade_artigo") or {}
        assert qualidade.get("avaliacao_valida") is True and qualidade.get("criterios_aprovados", 0) >= 11, (
            "Publicação concluida exige vetor 12 com corte >= 11/12."
        )
    else:
        assert resultado["status"] in ("incompleto", "falha"), (
            f"Status não previsto para o cenário de dossiê truncado: {resultado['status']}"
        )


@pytest.mark.asyncio
async def test_writer_open_fences_and_finish_reason_length_not_concluded(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Texto com cercas de código não fechadas e finish_reason='length' não pode concluir."""
    mock_net = MockNetwork()
    truncated_code_fence = (
        "## 1. Sumário Executivo\nSíntese.\n\n"
        "## 2. Desenvolvimento dos Eixos Temáticos\n"
        "Abaixo o código de exemplo:\n"
        "```python\ndef test():\n    x = 10\n"  # Cerca não fechada!
    )
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_raw_response(
        content=truncated_code_fence,
        finish_reason="length",  # Corte por limite de tokens
    )
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    id_pesquisa, _ = await _setup_research_for_writer(repo, "Tema Fences Abertas", ["aprovado"])

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    writer = Writer(research_repo=repo, llm_client=llm_client)

    resultado = await writer.execute_writer(id_pesquisa=id_pesquisa)

    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL):
    assert resultado["status"] != "concluido", (
        "DEFEITO CONFIRMADO (BUG-20261023-YXTQ): Dossiê com cercas de código abertas e finish_reason='length' "
        "foi aceito e marcado como 'concluido'."
    )


@pytest.mark.asyncio
async def test_writer_reproved_axis_does_not_silently_succeed(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Eixo reprovado não pode ser transformado em sucesso pleno silencioso.
    
    Cenário DR-012 / backlog item 6:
    A pesquisa possui um ponto 'aprovado' e um ponto 'reprovado'.
    No código atual (linha 94 de writer.py), pontos reprovados são considerados estados
    terminais aceitáveis e a redação prossegue emitindo 'status': 'concluido' sem
    nenhuma ressalva de entrega parcial.
    O comportamento esperado é aplicar política explícita (bloquear ou entregar parcial com ressalva),
    nunca marcar como pesquisa plenamente concluída sem ressalvas.
    """
    mock_net = MockNetwork()
    def _mock_writer_handler(r: httpx.Request) -> httpx.Response:
        body = json.loads(r.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"
        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))
        return make_llm_raw_response(
            content=VALID_COMPLETE_DOSSIER,
            finish_reason="stop",
        )

    mock_net.custom_handlers["chat/completions"] = _mock_writer_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    # Um ponto aprovado e um ponto REPROVADO
    id_pesquisa, _ = await _setup_research_for_writer(repo, "Tema Eixo Reprovado", ["aprovado", "reprovado"])

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    writer = Writer(research_repo=repo, llm_client=llm_client)

    # DR-012 / v2 / W01: Sob a nova política estrita, eixo reprovado bloqueia ANTES do LLM/cache
    with pytest.raises(ValueError, match="reprovado|UNAPPROVED_POINTS|READINESS_FAILED"):
        await writer.execute_writer(id_pesquisa=id_pesquisa)


@pytest.mark.asyncio
async def test_writer_valid_complete_dossier_concludes(
    db_session: AsyncSession,
) -> None:
    """[PROTEÇÃO/REGRESSÃO] Dossiê com todas as 4 seções, cercas fechadas e stop regular é concluído."""
    mock_net = MockNetwork()
    def _mock_writer_handler(r: httpx.Request) -> httpx.Response:
        body = json.loads(r.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"
        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))
        return make_llm_raw_response(
            content=VALID_COMPLETE_DOSSIER,
            finish_reason="stop",
        )

    mock_net.custom_handlers["chat/completions"] = _mock_writer_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    id_pesquisa, _ = await _setup_research_for_writer(repo, "Tema Válido", ["aprovado"])

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    writer = Writer(research_repo=repo, llm_client=llm_client)

    resultado = await writer.execute_writer(id_pesquisa=id_pesquisa)
    assert resultado["status"] == "concluido"
    assert resultado["total_caracteres_dossier"] > 100
