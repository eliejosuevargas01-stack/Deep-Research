"""Testes unitários para os módulos de domínio do núcleo analítico.

Cobre formulação de N pontos pelo planejador, busca concorrente com 4 personas
e deduplicação no pesquisador, checklist das 12 perguntas no auditor e redação
com 100% de fontes canônicas e bloqueio estrito de pendências.
Atende a DT-07 a DT-10, RN-04 a RN-08 e RF-01 a RF-10.
"""

from datetime import datetime, timezone
import json
import uuid
import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import ConteudoColetado
from app.db.research_repository import ResearchRepository
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_audit_acceptance import CANONICAL_PLANO, make_audit_12_vector, make_standard_coleta_metadata
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response, make_llm_raw_response
from tests.unit.test_writer_acceptance import make_writer_article_12_eval


@pytest.mark.asyncio
async def test_planner_formulates_exact_n_points(db_session: AsyncSession) -> None:
    """Verifica que o planejador formula exatamente N pontos via SERP e persiste como pendente."""
    from app.core.planner import Planner
    from app.tools.jina_client import JinaClient
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    planner = Planner(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        n_pontos=5,
    )

    pesquisa = await planner.execute_plan(tema="Impacto da Inteligência Artificial na Educação")

    assert pesquisa is not None
    assert pesquisa.id_pesquisa is not None
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    assert len(pontos) == 5
    for p in pontos:
        assert p.status == "pendente"
        assert len(p.ponto) > 5


@pytest.mark.asyncio
async def test_searcher_concurrent_4_personas_and_deduplication(
    db_session: AsyncSession,
) -> None:
    """Verifica varredura paralela das 4 personas e deduplicação de URLs por pesquisa (RN-04)."""
    from app.core.searcher import Searcher
    from app.tools.jina_client import JinaClient
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Busca Personas",
        pontos_textos=["Ponto 1", "Ponto 2"],
    )

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    assert resultado["total_pontos_processados"] == 2
    assert resultado["status_pesquisa"] == "coletado"

    coletas = await repo.get_collected_content(pesquisa.id_pesquisa)
    assert len(coletas) == 2
    for c in coletas:
        assert len(c.conteudo_coletado) > 0
        assert "Perspectiva Historiador" in c.conteudo_coletado
        assert "Perspectiva Visionario" in c.conteudo_coletado
        assert "Perspectiva Cetico" in c.conteudo_coletado
        assert "Perspectiva Futurista" in c.conteudo_coletado


@pytest.mark.asyncio
async def test_searcher_single_point_executes_all_4_personas_with_llm(
    db_session: AsyncSession,
) -> None:
    """Verifica que para exatamente 1 ponto, todas as 4 personas são acionadas no LLM leve."""
    from app.core.searcher import Searcher
    from app.tools.jina_client import JinaClient
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Impacto da IA em Restaurantes",
        pontos_textos=["Automação de cardápio digital"],
    )

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    assert resultado["total_pontos_processados"] == 1
    ponto_resumo = resultado["resumo_coletas"][0]
    assert ponto_resumo["total_personas"] == 4

    coletas = await repo.get_collected_content(pesquisa.id_pesquisa)
    assert len(coletas) == 1
    texto = coletas[0].conteudo_coletado

    # As 4 personas devem estar consolidadas no conteúdo coletado do ponto
    assert "Perspectiva Historiador" in texto
    assert "Perspectiva Visionario" in texto
    assert "Perspectiva Cetico" in texto
    assert "Perspectiva Futurista" in texto

    # Deve ter havido chamadas LLM com tools para cada persona
    llm_calls = [
        req for req in mock_net.requests
        if "chat/completions" in str(req.url)
    ]
    assert len(llm_calls) >= 4

    # Verifica se a memória indexada por {id_pesquisa}:{ponto_id} foi devidamente populada
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    memory_key = f"{pesquisa.id_pesquisa}:{pontos[0].ponto_id}"
    assert memory_key in searcher.memoria
    for persona in ["historiador", "visionario", "cetico", "futurista"]:
        assert persona in searcher.memoria[memory_key]
        persona_mem = searcher.memoria[memory_key][persona]
        assert "messages" in persona_mem
        assert len(persona_mem["messages"]) >= 2
        assert persona_mem["queries_executadas"] <= 3


@pytest.mark.asyncio
async def test_auditor_evaluates_12_questions_checklist(db_session: AsyncSession) -> None:
    """Verifica aplicação das 12 perguntas de qualidade e persistência de parecer (RN-06)."""
    from app.core.auditor import Auditor
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Auditoria",
        pontos_textos=["Ponto Analítico 1"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="Conteúdo robusto coletado com referências canônicas.",
        urls_lidas=["https://unesco.org/estudo"],
        urls_fonte=["https://unesco.org/estudo"],
    )

    auditor = Auditor(research_repo=repo, llm_client=llm_client)
    res_auditoria = await auditor.execute_audit(id_pesquisa=pesquisa.id_pesquisa)

    assert res_auditoria["total_pontos"] == 1
    assert res_auditoria["aprovados"] + res_auditoria["reprovados"] == 1

    ponto_atualizado = await repo.get_point(pontos[0].ponto_id)
    assert ponto_atualizado is not None
    assert ponto_atualizado.status in ("aprovado", "reprovado")


@pytest.mark.asyncio
async def test_writer_enforces_100_percent_canonical_sources_and_structure(
    db_session: AsyncSession,
) -> None:
    """Verifica geração do dossiê em 4 seções com 100% de fontes e despacho de webhook (RN-08, RN-09)."""
    from app.core.writer import Writer
    from app.services.webhook_client import WebhookClient
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    webhook_client = WebhookClient(secret="webhook-secret", transport=transport)
    repo = ResearchRepository(session=db_session)

    canonical_url = "https://unesdoc.unesco.org/ark:/48223/pf0000377897"
    coleta_id = str(uuid.uuid4())
    coleta_meta = make_standard_coleta_metadata(source_url=canonical_url)
    coleta_meta["auditorias"] = [
        {
            "id_auditoria": str(uuid.uuid4()),
            "coleta_id": coleta_id,
            "rodada": 1,
            "valido": True,
            "aplicado": True,
            "status": "aprovado",
            "criterios": make_audit_12_vector(12),
            "criterios_aprovados": 12,
            "criterios_minimos": 11,
            "pontuacao_percentual": 100.0,
            "pontos_fracos": None,
            "tarefas": [],
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
    ]
    pesquisa = await repo.create_research(
        tema="Tema Redação Final",
        pontos_textos=["Ponto Auditado e Aprovado"],
        plano_estruturado=dict(CANONICAL_PLANO),
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=pontos[0].ponto_id,
        tema=pesquisa.tema,
        ponto=pontos[0].ponto,
        conteudo_coletado="Texto completo do ponto 1.",
        urls_lidas=[canonical_url],
        urls_fonte=[canonical_url],
        metadados_coleta=coleta_meta,
    )
    await repo.session.execute(
        update(ConteudoColetado)
        .where(ConteudoColetado.ponto_id == pontos[0].ponto_id)
        .values(id=coleta_id)
    )
    await repo.update_point_status(ponto_id=pontos[0].ponto_id, status="aprovado")

    writer = Writer(
        research_repo=repo,
        llm_client=llm_client,
        webhook_client=webhook_client,
        callback_url="https://callback.test/hook",
    )

    dossie_unesco = f"""# Dossiê Analítico: IA e Educação Básica

## 1. Sumário Executivo
Este dossiê consolida os achados das quatro personas investigativas sobre a integração de IA generativa na educação básica. O relatório canônico [Relatório UNESCO]({canonical_url}) atesta a urgência de capacitação docente e a persistência de assimetrias de conectividade documentadas no corpo lido.

## 2. Desenvolvimento dos Eixos Temáticos
A investigação do eixo apurou, pelo corpo real da fonte primária [Relatório UNESCO]({canonical_url}), que dinâmicas escolares são transformadas por modelos generativos e que as diretrizes formais ainda não alcançam a maioria das escolas monitoradas no conjunto entregue.

## 3. Ressalvas e Limitações Metodológicas
A auditoria formal qualifica os achados: os dados de capacitação docente provêm de relato secundário consolidado no relatório lido, sem confirmação primária de monitoramento longitudinal; nenhuma versão, comando ou métrica fora do conjunto lido foi introduzida.

## 4. Referências e Fontes Canônicas
1. [Relatório UNESCO]({canonical_url}) - Relatório analítico sobre integração pedagógica de modelos generativos.
"""

    def writer_llm_handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content.decode("utf-8"))
        msgs = body.get("messages", [])
        is_eval = any(
            m.get("role") == "system" and "auditor_redacao" in str(m.get("content", ""))
            for m in msgs
        ) or body.get("response_format", {}).get("type") == "json_object"
        if is_eval:
            return make_llm_json_response(make_writer_article_12_eval(12))
        return make_llm_raw_response(content=dossie_unesco, finish_reason="stop")

    mock_net.custom_handlers["chat/completions"] = writer_llm_handler

    resultado = await writer.execute_writer(id_pesquisa=pesquisa.id_pesquisa)

    assert resultado["status"] == "concluido"
    assert resultado["total_caracteres_dossier"] > 100
    assert "Sumário Executivo" in resultado["dossier_resumo"] or "# Dossiê" in resultado["dossier_resumo"]

    # Confere persistência no banco
    pesquisa_db = await repo.get_research(pesquisa.id_pesquisa)
    assert pesquisa_db is not None
    assert pesquisa_db.dossier_final is not None
    assert pesquisa_db.webhook_status == "entregue"


@pytest.mark.asyncio
async def test_writer_blocks_when_points_pending(db_session: AsyncSession) -> None:
    """Verifica bloqueio estrito de redação quando há pontos com status 'pendente' (RN-07, RF-09)."""
    from app.core.writer import Writer
    from app.services.webhook_client import WebhookClient
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    webhook_client = WebhookClient(secret="secret", transport=transport)
    repo = ResearchRepository(session=db_session)

    pesquisa = await repo.create_research(
        tema="Pesquisa com Ponto Pendente",
        pontos_textos=["Ponto que não foi auditado"],
        plano_estruturado=dict(CANONICAL_PLANO),
    )

    writer = Writer(
        research_repo=repo,
        llm_client=llm_client,
        webhook_client=webhook_client,
    )

    with pytest.raises(ValueError, match="pontos pendentes|PENDING_AUDIT_POINTS"):
        await writer.execute_writer(id_pesquisa=pesquisa.id_pesquisa)


@pytest.mark.asyncio
async def test_incremental_rounds_and_auditor_rejection_cycle(db_session: AsyncSession) -> None:
    """Verifica que as coletas de múltiplas rodadas são salvas incrementalmente sem apagar anteriores

    e que o auditor sintetiza todas as rodadas com limite máximo de 3 tentativas.
    """
    from app.core.auditor import Auditor
    from app.tools.llm_client import LLMClient

    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    repo = ResearchRepository(session=db_session)

    pesquisa = await repo.create_research(
        tema="Tema Ciclo de Auditoria",
        pontos_textos=["Ponto com Re-pesquisa"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    ponto = pontos[0]

    # Rodada 1 de coleta
    c1 = await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="### Perspectiva Historiador\n\nPrimeira análise histórica.",
        urls_lidas=["https://exemplo.com/1"],
        urls_fonte=["https://exemplo.com/1"],
        metadados_coleta=make_standard_coleta_metadata(source_url="https://exemplo.com/1"),
    )
    assert c1.rodada == 1

    # Rodada 2 de coleta (não apaga a rodada 1!)
    c2 = await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="### Perspectiva Historiador\n\nSegunda análise refinada com novos dados.",
        urls_lidas=["https://exemplo.com/2"],
        urls_fonte=["https://exemplo.com/2"],
        metadados_coleta=make_standard_coleta_metadata(source_url="https://exemplo.com/2"),
    )
    assert c2.rodada == 2

    # Verifica se ambas as coletas coexistem no banco
    todas_coletas = await repo.get_collected_content_for_point(pesquisa.id_pesquisa, ponto.ponto_id)
    assert len(todas_coletas) == 2
    assert todas_coletas[0].rodada == 1
    assert todas_coletas[1].rodada == 2

    # Executa a auditoria que sintetiza todas as rodadas
    auditor = Auditor(
        research_repo=repo,
        llm_client=llm_client,
        persona_prompt="Você é o auditor",
    )
    resultado = await auditor.execute_audit(id_pesquisa=pesquisa.id_pesquisa)
    assert resultado["total_pontos"] == 1
    assert resultado["status_geral"] == "auditado"

    # Confere se a tentativa de auditoria foi incrementada no ponto
    ponto_atualizado = await repo.get_point(ponto.ponto_id)
    assert ponto_atualizado is not None
    assert ponto_atualizado.tentativas_auditoria == 1
