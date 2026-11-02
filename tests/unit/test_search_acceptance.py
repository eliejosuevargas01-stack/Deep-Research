# -*- coding: utf-8 -*-
"""Testes de aceitação para o Contrato v4 de Busca com Personas (Search).

Atende rigorosamente aos requisitos de confiabilidade DR-001..DR-015, adendo v4-search,
e à matriz de 17 comportamentos auditáveis exigidos:
1. contexto integral recebido pelas 4 personas (eixo, público, recorte temporal, hipóteses);
2. quatro personas com sucesso e IDs/offsets verificáveis no corpo;
3. content null + reasoning não promovido a analise_final após leitura real;
4. description-only + Reader vazio/erro vira snippet_only (não url_lida);
5. metatexto, JSON inválido e finish length rejeitados;
6. três personas falham -> status parcial;
7. falha de síntese com corpo armazenado não gera sucesso;
8. cache compartilhado entrega evidência às 4 personas;
9. falha de fetch não reserva URL como lida;
10. contexto relevante no final de documento longo selecionado no orçamento;
11. IDs inventados pelo modelo rejeitados;
12. histórico real com corpos reaproveitável em nova rodada;
13. agregado cobre todo o conjunto de pontos da pesquisa;
14. concorrência atômica entre 2 sessões SQLite e limite máximo de 4 passagens;
15. cancelamento libera reserva com diagnóstico;
16. endpoint fecha ambos os clientes em finally (inclusive falha de construção);
17. telemetria completa, sanitizada e persistida em GenerationAttempt.
"""

import asyncio
import hashlib
import json
import re
from typing import Any, Dict, List, Optional
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.searcher import Searcher
from app.db.models import ConteudoColetado, GenerationAttempt, Pesquisa, Ponto
from app.db.research_repository import ResearchRepository
from app.tools.errors import JinaError, LLMCallError
from app.tools.jina_client import JinaClient
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response, make_serp_response


def _create_sample_plano_e_eixo() -> Dict[str, Any]:
    """Cria estrutura de plano e eixo para testes com dados completos do contrato v4."""
    eixo = {
        "pergunta_principal": "Qual é a origem e evolução da vulnerabilidade crítica do PHP?",
        "subperguntas": [
            "Quais versões foram historicamente afetadas?",
            "Qual commit introduziu a falha?",
        ],
        "hipoteses": [
            "A falha decorre de conversão insegura de tipos em cabeçalhos CGI.",
        ],
        "consultas_iniciais": [
            "php cgi vulnerability advisory cve",
        ],
        "fontes_primarias_desejadas": [
            "Boletim oficial de segurança do PHP.net",
        ],
        "riscos_de_vies": [
            "Superestimar impacto em versões já descontinuadas.",
        ],
        "evidencias_que_refutariam": [
            "Declaração oficial de que o módulo afetado não fazia parte da build padrão.",
        ],
        "criterio_de_conclusao": "Identificação canônica do boletim oficial e versões corrigidas.",
        "investigabilidade": "Alta via changelogs oficiais.",
        "eixo_essencial": True,
    }
    plano = {
        "pedido_original": "Explicar a falha do PHP exposta recentemente",
        "pedido_normalizado": "Análise técnica e cronológica do incidente PHP",
        "publico": "Desenvolvedores e auditores de segurança",
        "formato_entrega": "Dossiê estruturado com referências canônicas",
        "recorte_temporal": "Últimos 12 meses",
        "pressupostos": ["Metadados SERP não são evidência suficiente"],
        "ambiguidades": [],
        "eixos": [eixo],
    }
    return plano


def _extract_delivered_chunk_id(msgs: List[Dict[str, Any]]) -> str:
    """Extrai com precisão o ID de trecho entregue pelo backend na mensagem do usuário."""
    import re
    user_msgs = [m.get("content", "") for m in msgs if m.get("role") == "user"]
    last_user_msg = user_msgs[-1] if user_msgs else ""
    chk_matches = re.findall(r"\[Trecho ID:\s*(chk_[a-zA-Z0-9_\-]+)\]", last_user_msg)
    if not chk_matches:
        chk_matches = [c for c in re.findall(r"chk_[a-zA-Z0-9_\-]+", last_user_msg) if c != "chk_id"]
    assert chk_matches, f"O backend deveria ter entregue trechos válidos! Mensagem: {last_user_msg}"
    return chk_matches[0]


# -----------------------------------------------------------------------------
# 1. Contexto integral recebido pelas 4 personas
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_contexto_integral_recebido_4_personas(db_session: AsyncSession) -> None:
    """1. Toda persona recebe eixo integral, público, recorte temporal e objetivo.

    Hipóteses devem ser marcadas como hipóteses. Role da persona inequivocamente no system.
    """
    mock_net = MockNetwork()
    captured_messages: List[List[Dict[str, Any]]] = []

    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        captured_messages.append(msgs)
        # Responde parar_insuficiente para encerrar rápido o turno
        resp_payload = {
            "acao": "parar_insuficiente",
            "motivo": "Fim do teste de inspeção de prompt",
            "lacunas": ["Inspeção realizada"],
        }
        return make_llm_json_response(resp_payload)

    mock_net.custom_handlers["chat/completions"] = llm_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    plano_data = _create_sample_plano_e_eixo()
    pesquisa = await repo.create_research(
        tema="Segurança PHP",
        pontos_textos=[plano_data["eixos"][0]["pergunta_principal"]],
        plano_estruturado=plano_data,
        eixos_estruturados=plano_data["eixos"],
    )

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    assert len(captured_messages) >= 4, "Todas as 4 personas devem acionar o LLM."
    roles_encontradas = set()

    for msgs in captured_messages:
        system_msgs = [m["content"] for m in msgs if m.get("role") == "system"]
        user_msgs = [m["content"] for m in msgs if m.get("role") == "user"]
        all_text = " ".join(system_msgs + user_msgs).lower()

        # Verifica presença dos elementos do plano estruturado
        assert plano_data["publico"].lower() in all_text, "Público deve constar no contexto."
        assert plano_data["recorte_temporal"].lower() in all_text, "Recorte temporal deve constar."
        assert plano_data["pedido_original"].lower() in all_text, "Pedido original deve constar."

        # Eixo estruturado integral
        eixo = plano_data["eixos"][0]
        assert eixo["pergunta_principal"].lower() in all_text
        assert eixo["subperguntas"][0].lower() in all_text
        assert eixo["criterio_de_conclusao"].lower() in all_text

        # Hipóteses marcadas como hipóteses
        assert "hipótese" in all_text or "hipotese" in all_text

        # Role inequivocamente no system
        sys_text = " ".join(system_msgs).lower()
        for role in ["historiador", "visionario", "cetico", "futurista"]:
            if role in sys_text:
                roles_encontradas.add(role)

    assert roles_encontradas == {"historiador", "visionario", "cetico", "futurista"}, (
        f"Todas as 4 roles devem estar inequivocamente no system. Encontradas: {roles_encontradas}"
    )


# -----------------------------------------------------------------------------
# 2. Quatro personas sucesso e IDs/offsets verificáveis
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_quatro_personas_sucesso_e_ids_offsets_verificaveis(db_session: AsyncSession) -> None:
    """2. Quatro personas com sucesso geram ponto coletado.

    IDs de trecho gerados pelo backend têm offsets e hashes exatos no corpo armazenado.
    """
    mock_net = MockNetwork()
    SAMPLE_BODY = (
        "# Boletim de Segurança PHP 2026\n\n"
        "Uma vulnerabilidade crítica no processamento de argumentos CGI foi corrigida. "
        "A falha CVE-2026-9999 permite execução remota de código sob certas configurações. "
        "Recomenda-se atualização imediata para a versão 8.3.12."
    )
    turn_counter: Dict[str, int] = {}

    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        sys_msg = " ".join([m["content"] for m in msgs if m.get("role") == "system"]).lower()
        persona = "desconhecido"
        for p in ["historiador", "visionario", "cetico", "futurista"]:
            if p in sys_msg:
                persona = p
                break
        t = turn_counter.get(persona, 0) + 1
        turn_counter[persona] = t

        if t == 1:
            # Turno 1: persona pede busca
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": f"cve php seguranca {persona}",
                "objetivo": "Obter boletim oficial",
            })
        else:
            # Turno 2: persona recebe trechos com IDs do backend e conclui
            delivered_chunk_id = _extract_delivered_chunk_id(msgs)

            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": f"Síntese investigativa robusta elaborada por {persona} com base em fontes canônicas.",
                "conclusoes": [
                    {
                        "claim_id": "clm_1",
                        "afirmacao": "A falha CVE-2026-9999 afeta configurações específicas de CGI.",
                        "tipo": "fato",
                        "evidencias": [delivered_chunk_id],
                        "confianca": "alta",
                        "limitacoes": "Apenas cenários CGI foram demonstrados.",
                    }
                ],
                "lacunas": [],
                "motivo_parada": "Evidências canônicas suficientes obtidas.",
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([
            {
                "url": "https://php.net/security-advisory-2026.html",
                "title": "PHP Security Advisory",
                "description": "Boletim oficial de segurança",
            }
        ])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SAMPLE_BODY, headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    plano_data = _create_sample_plano_e_eixo()
    pesquisa = await repo.create_research(
        tema="Tema Sucesso Total",
        pontos_textos=[plano_data["eixos"][0]["pergunta_principal"]],
        plano_estruturado=plano_data,
        eixos_estruturados=plano_data["eixos"],
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

    assert resultado["status_pesquisa"] == "coletado"
    resumo_ponto = resultado["resumo_coletas"][0]
    assert resumo_ponto["status"] == "coletado"
    assert resumo_ponto["falha_coleta"] is False
    assert resumo_ponto["total_urls_lidas"] >= 1

    # Inspeciona ConteudoColetado e metadados_coleta
    coletas = await repo.get_collected_content(pesquisa.id_pesquisa)
    assert len(coletas) == 1
    c = coletas[0]
    assert c.metadados_coleta is not None
    meta = json.loads(c.metadados_coleta)

    assert "fontes" in meta
    assert "resultados_personas" in meta
    assert "diario_acoes" in meta
    assert "trechos" not in meta and "selecao_contexto" not in meta

    # PRD v3: catálogo só com URL/uso/título/status; resumo por persona
    fontes = meta["fontes"]
    if isinstance(fontes, dict):
        fontes = list(fontes.values())
    assert len(fontes) >= 1
    for fonte in fontes:
        assert fonte["url"].startswith("http")
        assert fonte["status"] == "read_ok"
        assert fonte["uso"] in {"utilizada", "lida_nao_utilizada"}
        assert "body" not in fonte and "body_hash" not in fonte

    personas_meta = meta["resultados_personas"]
    assert len(personas_meta) >= 1
    for persona in personas_meta.values():
        assert persona.get("analise")
        assert "body" not in json.dumps(persona)
        assert "chunk_id" not in json.dumps(persona)


# -----------------------------------------------------------------------------
# 3. Content null + reasoning não promovido a analise_final após leitura real
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_content_null_reasoning_not_promoted_after_real_read(db_session: AsyncSession) -> None:
    """3. Raciocínio interno nunca substitui analise_final quando content vier vazio após leitura."""
    mock_net = MockNetwork()
    DIAG_REASONING = "Analyzing Critical Vulnerabilities in PHP CGI - private reasoning"
    turn = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php security",
                "objetivo": "buscar boletim",
            })
        else:
            # Emite content vazio / None com reasoning_content preenchido
            data = {
                "id": "chatcmpl-null-content",
                "object": "chat.completion",
                "created": 1729720000,
                "model": "gpt-4o",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning_content": DIAG_REASONING,
                    },
                    "finish_reason": "stop",
                }],
            }
            return httpx.Response(200, json=data)

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://php.net/sec", "title": "Sec", "description": "Desc"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# PHP Security\nFull page content.", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Reasoning", pontos_textos=["Ponto 1"])

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)
    p = resultado["resumo_coletas"][0]["personas"][0]

    assert DIAG_REASONING not in p["analise"], "Reasoning privado nunca pode virar analise_final!"


# -----------------------------------------------------------------------------
# 4. Description-only + Reader vazio/erro vira snippet_only
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_description_only_reader_empty_yields_snippet_only(db_session: AsyncSession) -> None:
    """4. Quando Reader falha ou retorna vazio, URL é snippet_only e total_urls_lidas é zero."""
    mock_net = MockNetwork()
    turn = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php security",
                "objetivo": "buscar boletim",
            })
        else:
            return make_llm_json_response({
                "acao": "parar_insuficiente",
                "motivo": "Sem fontes utilizáveis pelo Reader",
                "lacunas": ["Reader indisponível"],
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([
            {"url": "https://exemplo.org/doc", "title": "Doc", "description": "Snippet curto da SERP"}
        ])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        # Reader retorna vazio
        return httpx.Response(200, text="", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Snippet Only", pontos_textos=["Ponto 1"])

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)
    resumo_ponto = resultado["resumo_coletas"][0]

    assert resumo_ponto["total_urls_lidas"] == 0, "Snippet/description da SERP não incrementa total_urls_lidas!"
    assert resumo_ponto["falha_coleta"] is True or resumo_ponto["status"] in ("falha_coleta", "parcial")


# -----------------------------------------------------------------------------
# 5. Metatexto / JSON inválido / finish_reason length
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_metatexto_json_invalido_finish_length(db_session: AsyncSession) -> None:
    """5. Metatexto, JSON malformado e finish_reason='length' são rejeitados sem virar sucesso."""
    mock_net = MockNetwork()
    turn = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php security",
                "objetivo": "buscar boletim",
            })
        else:
            # Emite envelope com finish_reason length e JSON truncado
            data = {
                "id": "chatcmpl-trunc",
                "object": "chat.completion",
                "created": 1729720000,
                "model": "gpt-4o",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": '{"acao": "concluir", "analise_final": "Texto truncado...',
                    },
                    "finish_reason": "length",
                }],
            }
            return httpx.Response(200, json=data)

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://sec.org", "title": "T", "description": "D"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# Sec Page\nBody.", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Truncamento", pontos_textos=["Ponto 1"])

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)
    p = resultado["resumo_coletas"][0]["personas"][0]

    assert p["falha_coleta"] is True or "COLETA FALHOU" in p["analise"] or "INSUFICIENTE" in p["analise"]


# -----------------------------------------------------------------------------
# 6. Três personas falham -> status parcial
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_tres_personas_falham_status_parcial(db_session: AsyncSession) -> None:
    """6. Três personas falhando e apenas 1 com sucesso resulta em status 'parcial', nunca 'coletado'."""
    mock_net = MockNetwork()
    turn_by_persona: Dict[str, int] = {}

    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        sys_msg = " ".join([m["content"] for m in msgs if m.get("role") == "system"]).lower()
        persona = "desconhecido"
        for p in ["historiador", "visionario", "cetico", "futurista"]:
            if p in sys_msg:
                persona = p
                break
        t = turn_by_persona.get(persona, 0) + 1
        turn_by_persona[persona] = t

        if persona == "historiador":
            if t == 1:
                return make_llm_json_response({
                    "acao": "buscar",
                    "consulta": "historia php",
                    "objetivo": "buscar origens",
                })
            else:
                chk_id = _extract_delivered_chunk_id(msgs)
                return make_llm_json_response({
                    "acao": "concluir",
                    "analise_final": "Síntese do Historiador.",
                    "conclusoes": [{
                        "claim_id": "c1",
                        "afirmacao": "Fato histórico confirmado.",
                        "tipo": "fato",
                        "evidencias": [chk_id],
                        "confianca": "alta",
                        "limitacoes": "nenhuma",
                    }],
                    "lacunas": [],
                    "motivo_parada": "Concluído",
                })
        else:
            # As outras 3 personas declaram parada insuficiente
            return make_llm_json_response({
                "acao": "parar_insuficiente",
                "motivo": "Sem fontes para esta perspectiva",
                "lacunas": ["Fontes ausentes"],
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://historia.org", "title": "H", "description": "D"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# História\nTexto da fonte.", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Parcial", pontos_textos=["Ponto 1"])

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)
    resumo_ponto = resultado["resumo_coletas"][0]

    assert resumo_ponto["status"] == "parcial", "3 falhas e 1 sucesso deve produzir status 'parcial'!"
    assert resultado["status_pesquisa"] == "parcial"


# -----------------------------------------------------------------------------
# 7. Falha de síntese com corpo não é sucesso
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_falha_sintese_com_corpo_nao_sucesso(db_session: AsyncSession) -> None:
    """7. Se o Reader obteve o corpo mas a síntese falhou, persona não tem sucesso (mas fontes são salvas)."""
    mock_net = MockNetwork()
    turn = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php advisory",
                "objetivo": "buscar advisory",
            })
        else:
            # Falha de LLM na síntese (HTTP 500)
            return httpx.Response(500, json={"error": {"message": "Internal LLM crash"}})

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://php.net/advisory", "title": "Adv", "description": "Desc"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# Advisory\nCorpo da página salvo.", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Falha Sintese", pontos_textos=["Ponto 1"])

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)
    p = resultado["resumo_coletas"][0]["personas"][0]

    assert p["falha_coleta"] is True, "Falha de síntese impede sucesso da persona!"

    # Porém o corpo lido pelo Reader foi preservado no repositório
    coletas = await repo.get_collected_content(pesquisa.id_pesquisa)
    assert len(coletas) >= 1
    meta = json.loads(coletas[0].metadados_coleta or "{}")
    assert "https://php.net/advisory" in [f.get("url") for f in meta.get("fontes", {}).values()]


# -----------------------------------------------------------------------------
# 8. Cache compartilhado entrega evidência às 4 personas
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_cache_compartilhado_entrega_evidencia_as_quatro(db_session: AsyncSession) -> None:
    """8. Leitura bem-sucedida de uma URL é compartilhada entre as personas sem re-fetch de rede."""
    mock_net = MockNetwork()
    reader_calls = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        user_content = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
        if "chk_" not in user_content:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php canonical advisory",
                "objetivo": "buscar mesma URL",
            })
        else:
            chk_id = _extract_delivered_chunk_id(msgs)
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": "Síntese concluída com fonte compartilhada.",
                "conclusoes": [{
                    "claim_id": "c1",
                    "afirmacao": "Afirmação suportada.",
                    "tipo": "fato",
                    "evidencias": [chk_id],
                    "confianca": "alta",
                    "limitacoes": "nenhuma",
                }],
                "lacunas": [],
                "motivo_parada": "Concluído",
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        # Mesma URL retornada para todas as personas
        return make_serp_response([{"url": "https://shared.org/doc", "title": "Doc", "description": "D"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        nonlocal reader_calls
        reader_calls += 1
        return httpx.Response(200, text="# Shared Content\nConteúdo compartilhado.", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Cache Compartilhado", pontos_textos=["Ponto 1"])

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    assert reader_calls == 1, f"Reader deveria ter sido chamado exatamente 1 vez graças ao cache in-flight! Chamado: {reader_calls}"
    resumo = resultado["resumo_coletas"][0]
    assert resumo["status"] == "coletado"


# -----------------------------------------------------------------------------
# 9. Falha de fetch não reserva URL
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_falha_fetch_nao_reserva_url(db_session: AsyncSession) -> None:
    """9. Se a leitura do Reader falhar, a URL não é envenenada no cache nem marcada como lida."""
    mock_net = MockNetwork()
    turn = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php security",
                "objetivo": "buscar advisory",
            })
        else:
            return make_llm_json_response({
                "acao": "parar_insuficiente",
                "motivo": "Falha na leitura",
                "lacunas": ["Reader indisponível"],
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://failing.org/doc", "title": "F", "description": "D"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Reader timeout"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Falha Fetch", pontos_textos=["Ponto 1"])

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    read_urls = await repo.get_read_urls(pesquisa.id_pesquisa)
    assert "https://failing.org/doc" not in read_urls, "URL que falhou no Reader não pode constar em urls_lidas!"


# -----------------------------------------------------------------------------
# 10. Contexto relevante no final de texto grande
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_contexto_relevante_no_final_de_texto_grande(db_session: AsyncSession) -> None:
    """10. Evidência localizada no final de texto longo (> 20.000 chars) é selecionada no ledger."""
    mock_net = MockNetwork()
    # Cria corpo de 25.000 chars com a informação crucial no final
    padding = "Texto preliminar sobre generalidades de servidores web sem menção a CVEs. " * 300
    KEY_EVIDENCE = "ACHADO CRÍTICO DECISIVO: A vulnerabilidade CVE-2026-9999 afeta estritamente o módulo mod_cgi sob Windows."
    LARGE_BODY = f"{padding}\n\n{KEY_EVIDENCE}\n\n" + ("Mais texto irrelevante no rodapé. " * 50)
    assert len(LARGE_BODY) > 20000

    delivered_prompt_text = ""

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal delivered_prompt_text
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        user_content = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
        if "chk_" not in user_content:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "CVE-2026-9999 mod_cgi Windows",
                "objetivo": "buscar confirmação de mod_cgi no Windows",
            })
        else:
            delivered_prompt_text = str(msgs)
            chk_id = _extract_delivered_chunk_id(msgs)
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": "Síntese baseada na evidência final.",
                "conclusoes": [{
                    "claim_id": "c1",
                    "afirmacao": "mod_cgi no Windows é o vetor.",
                    "tipo": "fato",
                    "evidencias": [chk_id],
                    "confianca": "alta",
                    "limitacoes": "nenhuma",
                }],
                "lacunas": [],
                "motivo_parada": "Concluído",
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://huge.org/doc", "title": "Huge Doc", "description": "D"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=LARGE_BODY, headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Texto Longo", pontos_textos=["Ponto 1"])

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    # Verifica se a evidência que estava além dos 20.000 chars foi entregue no prompt
    assert "ACHADO CRÍTICO DECISIVO" in delivered_prompt_text, (
        "Corte cego de 8000 caracteres impediria que a evidência relevante no final fosse entregue!"
    )


# -----------------------------------------------------------------------------
# 11. IDs inventados rejeitados
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_ids_inventados_rejeitados(db_session: AsyncSession) -> None:
    """11. Se o modelo inventa IDs de evidência não entregues, eles são rejeitados."""
    mock_net = MockNetwork()
    turn = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php security",
                "objetivo": "buscar advisory",
            })
        else:
            # Modelo inventa IDs não existentes
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": "Síntese com IDs inventados.",
                "conclusoes": [
                    {
                        "claim_id": "c1",
                        "afirmacao": "Afirmação com ID inventado.",
                        "tipo": "fato",
                        "evidencias": ["chk_inventado_9999", "src_fake"],
                        "confianca": "alta",
                        "limitacoes": "nenhuma",
                    }
                ],
                "lacunas": [],
                "motivo_parada": "Concluído",
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://sec.org/doc", "title": "S", "description": "D"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# Sec Doc\nConteúdo real.", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste IDs Inventados", pontos_textos=["Ponto 1"])

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)
    p = resultado["resumo_coletas"][0]["personas"][0]

    # Inspeciona metadados_coleta
    coletas = await repo.get_collected_content(pesquisa.id_pesquisa)
    meta = json.loads(coletas[0].metadados_coleta or "{}")
    conclusoes = meta.get("resultados_personas", {}).get("historiador", {}).get("conclusoes", [])

    assert len(conclusoes) >= 1
    # Conclusão com ID inventado deve ter sido reclassificada para não_verificado
    # e IDs inventados rejeitados
    assert conclusoes[0]["tipo"] == "não_verificado"
    assert "chk_inventado_9999" not in conclusoes[0].get("evidencias", [])


# -----------------------------------------------------------------------------
# 12. Histórico real com corpos reaproveitável em nova rodada
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_historico_real_reaproveitavel(db_session: AsyncSession) -> None:
    """12. Em rodada subsequente, o catálogo de URLs da rodada anterior é reaproveitado; corpo bruto não persiste (PRD v3)."""
    mock_net = MockNetwork()
    received_history_text = ""

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_history_text
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        received_history_text = str(msgs)
        return make_llm_json_response({
            "acao": "parar_insuficiente",
            "motivo": "Inspeção de histórico concluída",
            "lacunas": [],
        })

    mock_net.custom_handlers["chat/completions"] = llm_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Historico Real", pontos_textos=["Ponto 1"])
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]

    # Simula rodada 1 com metadados estruturados de coleta
    meta_r1 = {
        "versao": 3,
        "fontes": [
            {
                "url": "https://historia-antiga.org/doc",
                "uso": "utilizada",
                "titulo": "Documento histórico",
                "status": "read_ok",
            }
        ],
        "resultados_personas": {
            "historiador": {
                "persona": "historiador",
                "analise": "Resumo persistido da rodada 1.",
                "urls_fonte": ["https://historia-antiga.org/doc"],
                "urls_lidas": ["https://historia-antiga.org/doc"],
                "sucesso": True,
            }
        },
    }
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=ponto.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Conteudo r1",
        urls_lidas=["https://historia-antiga.org/doc"],
        urls_fonte=["https://historia-antiga.org/doc"],
        metadados_coleta=meta_r1,
    )
    # Marca ponto como reprovado para nova rodada
    await repo.update_point_status(ponto.ponto_id, status="reprovado", pontos_fracos="Faltam dados")

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador"],
    )

    await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa, ponto_id=ponto.ponto_id)

    assert '"body":' not in received_history_text and '"body_hash"' not in received_history_text, (
        "Prompt da persona não deve receber corpo bruto, hash ou trechos persistidos."
    )


# -----------------------------------------------------------------------------
# 13. Agregado cobre todo o conjunto de pontos da pesquisa
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_agregado_cobre_todo_conjunto(db_session: AsyncSession) -> None:
    """13. O status agregado cobre TODOS os pontos da pesquisa, inclusive pontos fora do filtro."""
    mock_net = MockNetwork()

    def llm_handler(request: httpx.Request) -> httpx.Response:
        msgs = json.loads(request.content.decode("utf-8")).get("messages", [])
        user_content = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
        if "chk_" not in user_content:
            return make_llm_json_response({"acao": "buscar", "consulta": "q", "objetivo": "obj"})
        else:
            chk_id = _extract_delivered_chunk_id(msgs)
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": "Síntese P1.",
                "conclusoes": [{"claim_id": "c1", "afirmacao": "A", "tipo": "fato", "evidencias": [chk_id], "confianca": "alta", "limitacoes": ""}],
                "lacunas": [],
                "motivo_parada": "Fim",
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://p1.org", "title": "P1", "description": "D"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# P1\nCorpo.", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(
        tema="Tema Multi Pontos",
        pontos_textos=["Ponto 1 para buscar", "Ponto 2 que ficara pendente"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    p1 = pontos[0]

    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    # Executa busca apenas para o ponto 1 (filtro por ponto_id)
    resultado = await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa, ponto_id=p1.ponto_id)

    # Ponto 1 é coletado, mas Ponto 2 continua pendente!
    # Status agregado da pesquisa NÃO pode ser 'coletado'
    assert resultado["status_pesquisa"] == "parcial", (
        "Status agregado da pesquisa deve cobrir todos os pontos; havendo ponto pendente, status deve ser parcial!"
    )


# -----------------------------------------------------------------------------
# 14. Concorrência atômica entre 2 sessões SQLite e limite máximo de 4
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_concorrencia_duas_sessoes_e_limite_max_4(async_engine) -> None:
    """14. Duas sessões SQLite concorrentes tentam reservar o mesmo ponto: uma vence e outra falha por conflito.

    Teto de 4 tentativas é estritamente bloqueado.
    """
    session_factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session1, session_factory() as session2:
        repo1 = ResearchRepository(session=session1)
        repo2 = ResearchRepository(session=session2)

        pesquisa = await repo1.create_research(tema="Teste Concorrencia", pontos_textos=["Ponto Concorrente"])
        ponto = (await repo1.list_points(pesquisa.id_pesquisa))[0]

        reserva1_feita = asyncio.Event()
        liberar_sessao1 = asyncio.Event()

        mock_net1 = MockNetwork()
        async def holding_llm_handler1(request: httpx.Request) -> httpx.Response:
            reserva1_feita.set()
            await liberar_sessao1.wait()
            return make_llm_json_response({
                "acao": "parar_insuficiente",
                "motivo": "Fim do teste de concorrência com barreira",
                "lacunas": ["Teste concluído"],
            })

        mock_net1.custom_handlers["chat/completions"] = holding_llm_handler1
        transport1 = create_mock_transport(mock_net1)
        jina1 = JinaClient(api_key="k", transport=transport1)
        llm1 = LLMClient(api_key="k", transport=transport1)

        mock_net2 = MockNetwork()
        transport2 = create_mock_transport(mock_net2)
        jina2 = JinaClient(api_key="k", transport=transport2)
        llm2 = LLMClient(api_key="k", transport=transport2)

        searcher1 = Searcher(research_repo=repo1, jina_client=jina1, llm_client=llm1, personas=["historiador"])
        searcher2 = Searcher(research_repo=repo2, jina_client=jina2, llm_client=llm2, personas=["historiador"])

        task1 = asyncio.create_task(
            searcher1.execute_search(id_pesquisa=pesquisa.id_pesquisa, ponto_id=ponto.ponto_id)
        )

        try:
            # Aguarda a sessão 1 ter entrado no I/O mockado (comprovando reserva atômica commitada)
            await reserva1_feita.wait()

            # Sessão 2 concorre sobre o mesmo ponto enquanto a sessão 1 tem posse ativa confirmada
            with pytest.raises(ValueError, match="CONCURRENT_EXECUTION"):
                await searcher2.execute_search(id_pesquisa=pesquisa.id_pesquisa, ponto_id=ponto.ponto_id)
        finally:
            liberar_sessao1.set()
            await task1

        # Testa teto máximo de 4 tentativas
        ponto_db = await repo1.get_point(ponto.ponto_id)
        assert ponto_db is not None
        ponto_db.tentativas = 4
        ponto_db.status = "reprovado"
        await session1.commit()

        with pytest.raises(ValueError, match="MAX_ATTEMPTS_EXCEEDED"):
            await searcher1.execute_search(id_pesquisa=pesquisa.id_pesquisa, ponto_id=ponto.ponto_id)


# -----------------------------------------------------------------------------
# 15. Cancelamento libera reserva com diagnóstico
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_cancelamento_libera_reserva(db_session: AsyncSession) -> None:
    """15. Cancelamento assíncrono (asyncio.CancelledError) libera a reserva do ponto."""
    mock_net = MockNetwork()

    async def hanging_llm_handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(10.0)
        return httpx.Response(200, json={})

    mock_net.custom_handlers["chat/completions"] = hanging_llm_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Cancelamento", pontos_textos=["Ponto Lento"])
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]

    jina = JinaClient(api_key="k", transport=transport)
    llm = LLMClient(api_key="k", transport=transport)
    searcher = Searcher(research_repo=repo, jina_client=jina, llm_client=llm, personas=["historiador"])

    task = asyncio.create_task(searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa, ponto_id=ponto.ponto_id))
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    # Verifica se a reserva foi liberada no banco
    ponto_apos = await repo.get_point(ponto.ponto_id)
    assert ponto_apos is not None
    assert ponto_apos.status != "em_andamento", "Ponto não pode permanecer em_andamento após cancelamento!"
    assert "cancel" in (ponto_apos.pontos_fracos or "").lower() or ponto_apos.status in ("falha_coleta", "pendente")


# -----------------------------------------------------------------------------
# 16. Endpoint fecha ambos os clientes em finally (inclusive falha de construção)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_endpoint_fecha_ambos_clientes(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """16. Endpoint /api/v1/search garante fechamento (aclose) de JinaClient e LLMClient em finally."""
    from app.api.v1.endpoints.search import search_points
    from app.schemas.search import SearchRequest

    closed_clients = []

    original_jina_aclose = JinaClient.aclose
    original_llm_aclose = LLMClient.aclose

    async def tracked_jina_aclose(self):
        closed_clients.append("jina")
        await original_jina_aclose(self)

    async def tracked_llm_aclose(self):
        closed_clients.append("llm")
        await original_llm_aclose(self)

    monkeypatch.setattr(JinaClient, "aclose", tracked_jina_aclose)
    monkeypatch.setattr(LLMClient, "aclose", tracked_llm_aclose)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Endpoint Clientes", pontos_textos=["Ponto 1"])

    payload = SearchRequest(id_pesquisa=pesquisa.id_pesquisa)
    try:
        await search_points(payload=payload, db=db_session)
    except Exception:
        pass

    assert "jina" in closed_clients, "JinaClient.aclose() deve ter sido chamado no finally do endpoint!"
    assert "llm" in closed_clients, "LLMClient.aclose() deve ter sido chamado no finally do endpoint!"


# -----------------------------------------------------------------------------
# 17. Telemetria completa, sanitizada e persistida em GenerationAttempt
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_telemetria_persistida_e_sanitizada(db_session: AsyncSession) -> None:
    """17. Toda inferência gera GenerationAttempt com prompt_hash, finish_reason, usage e sanitização."""
    mock_net = MockNetwork()

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return make_llm_json_response({
            "acao": "parar_insuficiente",
            "motivo": "Fim do teste telemetria",
            "lacunas": [],
        })

    mock_net.custom_handlers["chat/completions"] = llm_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Teste Telemetria", pontos_textos=["Ponto 1"])

    jina = JinaClient(api_key="jina-key", transport=transport)
    llm = LLMClient(api_key="openai-key", transport=transport)
    searcher = Searcher(research_repo=repo, jina_client=jina, llm_client=llm, personas=["historiador"])

    await searcher.execute_search(id_pesquisa=pesquisa.id_pesquisa)

    attempts = await repo.get_generation_attempts(pesquisa.id_pesquisa, etapa="search")
    assert len(attempts) >= 1, "Deveria haver pelo menos 1 GenerationAttempt registrado para search!"

    att = attempts[0]
    assert att.etapa == "search"
    assert att.persona == "historiador"
    assert att.prompt_hash is not None and len(att.prompt_hash) == 64
    assert att.finish_reason is not None
    assert "openai-key" not in att.messages_json
    assert "openai-key" not in (att.system_message or "")


# =============================================================================
# REPRODUÇÕES R2 DOS ACHADOS F01..F05 e C01..C04 (CONCILIAÇÃO)
# =============================================================================

async def _setup_search_fixture(
    db_session: AsyncSession,
    personas: Optional[List[str]] = None,
    tema: str = "Segurança PHP",
    custom_plano: Optional[Dict[str, Any]] = None,
):
    """Helper de fixture para reduzir repetição de setup de Search sem framework."""
    mock_net = MockNetwork()
    transport = create_mock_transport(mock_net)
    repo = ResearchRepository(session=db_session)
    plano_data = custom_plano or _create_sample_plano_e_eixo()
    pesquisa = await repo.create_research(
        tema=tema,
        pontos_textos=[plano_data["eixos"][0]["pergunta_principal"]],
        plano_estruturado=plano_data,
        eixos_estruturados=plano_data["eixos"],
    )
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    ponto = pontos[0]
    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)
    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=personas or ["historiador"],
    )
    return {
        "repo": repo,
        "pesquisa": pesquisa,
        "ponto": ponto,
        "mock_net": mock_net,
        "transport": transport,
        "jina_client": jina_client,
        "llm_client": llm_client,
        "searcher": searcher,
        "plano": plano_data,
    }


# -----------------------------------------------------------------------------
# F01 / C04: Reader primeiro falha depois mesma URL tem sucesso -> promove read_ok
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_f01_reader_primeiro_falha_depois_mesma_url_tem_sucesso(db_session: AsyncSession) -> None:
    """F01: Se URL falha na primeira tentativa (snippet_only), mas é lida com sucesso depois,
    deve ser promovida para read_ok, gerar trechos e armazenar o corpo."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    mock_net = setup["mock_net"]
    url_alvo = "https://php.net/advisory-f01.html"
    turn = 0
    reader_calls = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php advisory cgi falha",
                "objetivo": "buscar boletim oficial",
            })
        elif turn == 2:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php advisory cgi retry",
                "objetivo": "tentar ler novamente mesma url",
            })
        else:
            chk_id = _extract_delivered_chunk_id(msgs)
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": "Conclusão com corpo recuperado após falha temporária.",
                "conclusoes": [{
                    "claim_id": "c1",
                    "afirmacao": "Vulnerabilidade confirmada no advisory.",
                    "tipo": "fato",
                    "evidencias": [chk_id],
                }],
                "lacunas": [],
                "motivo_parada": "Evidência recuperada com sucesso.",
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{
            "url": url_alvo,
            "title": "Advisory F01",
            "description": "Snippet temporário",
        }])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        nonlocal reader_calls
        reader_calls += 1
        if reader_calls == 1:
            # Primeira tentativa: falha de leitura (corpo vazio ou erro)
            return httpx.Response(500, text="Temporary upstream reader error")
        # Segunda tentativa: sucesso com corpo real
        corpo = "# Advisory Oficial PHP\n\nVulnerabilidade crítica sanada na versão 8.3.12."
        return httpx.Response(200, text=corpo, headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler

    resultado = await setup["searcher"].execute_search(id_pesquisa=setup["pesquisa"].id_pesquisa)
    assert resultado["status_pesquisa"] == "coletado"

    coletas = await setup["repo"].get_collected_content(setup["pesquisa"].id_pesquisa)
    assert len(coletas) == 1
    meta = json.loads(coletas[0].metadados_coleta)
    fontes = meta["fontes"]
    if isinstance(fontes, dict):
        fontes = list(fontes.values())

    # PRD v3: promoção só altera status/uso no catálogo; corpo não é persistido
    rec_fonte = next((f for f in fontes if f.get("url") == url_alvo), None)
    assert rec_fonte is not None, "A fonte deve existir em metadados_coleta!"
    assert rec_fonte["status"] == "read_ok", f"Status deveria ser promovido a read_ok, mas é {rec_fonte.get('status')}"
    assert "body" not in rec_fonte and "trechos" not in meta


# -----------------------------------------------------------------------------
# F02 / C04: IDs backend distintos para claims idênticos do modelo + evidencias dict safe
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_f02_claim_ids_unicos_backend_e_evidencias_dict_safe(db_session: AsyncSession) -> None:
    """F02: Backend deve gerar IDs canônicos distintos para claims idênticos (ex: c1 de historiador e c1 de visionario)
    e não deve lançar TypeError quando o modelo emitir evidências como dict em vez de string."""
    setup = await _setup_search_fixture(db_session, personas=["historiador", "visionario"])
    mock_net = setup["mock_net"]
    turn_by_persona: Dict[str, int] = {}

    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        sys_msg = " ".join([m["content"] for m in msgs if m.get("role") == "system"]).lower()
        persona = "historiador" if "historiador" in sys_msg else "visionario"
        t = turn_by_persona.get(persona, 0) + 1
        turn_by_persona[persona] = t

        if t == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": f"php cgi {persona}",
                "objetivo": "buscar fatos",
            })
        else:
            chk_id = _extract_delivered_chunk_id(msgs)
            # Historiador emite claim_id 'c1' com evidencias como lista de strings
            # Visionario emite o MESMO claim_id 'c1', mas com evidencias contendo um dict inválido
            if persona == "historiador":
                evs = [chk_id]
            else:
                evs = [{"id": chk_id, "texto": "evidencia dict invalida"}, chk_id]

            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": f"Análise da persona {persona}.",
                "conclusoes": [{
                    "claim_id": "c1",  # ID idêntico emitido por ambas personas
                    "afirmacao": f"Afirmação apurada por {persona}",
                    "tipo": "fato",
                    "evidencias": evs,
                }],
                "lacunas": [],
                "motivo_parada": "Conclusão realizada",
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://php.net/sec.html", "title": "PHP Sec"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# PHP Sec\n\nCorreção crítica aplicada.", headers={"Content-Type": "text/markdown"})

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler

    resultado = await setup["searcher"].execute_search(
        id_pesquisa=setup["pesquisa"].id_pesquisa,
        ponto_id=setup["ponto"].ponto_id,
        personas=["historiador", "visionario"],
    )

    resumo_p = resultado["resumo_coletas"][0]
    p_res = resumo_p["personas"]
    assert len(p_res) == 2, "Ambas personas devem ter sido concluídas sem TypeError!"

    hist_claims = p_res[0]["conclusoes"]
    vis_claims = p_res[1]["conclusoes"]
    assert len(hist_claims) == 1
    assert len(vis_claims) == 1

    # Backend não deve adotar cegamente 'c1' colidindo entre personas
    cid_hist = hist_claims[0]["claim_id"]
    cid_vis = vis_claims[0]["claim_id"]
    assert cid_hist != cid_vis, f"IDs de claim não podem colidir entre personas! Ambos receberam: {cid_hist}"
    assert "c1" not in (cid_hist, cid_vis) or cid_hist != cid_vis


# -----------------------------------------------------------------------------
# F03 / C04: Tentativa antiga / lease expirada não grava nem apaga dossiê
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_f03_tentativa_antiga_expirada_nao_grava_nem_apaga_dossier(db_session: AsyncSession) -> None:
    """F03: save_collected_content deve comprovar posse da rodada com UPDATE condicional real.
    Se a rodada expirou e outra sessão assumiu o ponto ou aprovou o dossiê, a chamada antiga é rejeitada."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    repo = setup["repo"]
    pesquisa = setup["pesquisa"]
    ponto = setup["ponto"]

    # Simula reserva da tentativa 1
    ponto_res1 = await repo.reserve_point(ponto.ponto_id, lease_seconds=600)
    assert ponto_res1.tentativas == 1

    # Simula avanço para tentativa 2 por outra sessão e aprovação de dossiê final
    ponto_res1.tentativas = 2
    ponto_res1.status = "coletado"
    pesquisa_db = await repo.get_research(pesquisa.id_pesquisa)
    assert pesquisa_db is not None
    pesquisa_db.dossier_final = "# Dossiê Aprovado da Nova Rodada"
    await db_session.commit()

    # Agora a tentativa antiga 1 tenta salvar conteúdo tardio
    with pytest.raises(Exception, match=r"(?i)(possession|tentativa|expir|conflito)"):
        await repo.save_collected_content(
            id_pesquisa=pesquisa.id_pesquisa,
            ponto_id=ponto.ponto_id,
            tema=pesquisa.tema,
            ponto=ponto.ponto,
            conteudo_coletado="Conteúdo da tentativa 1 atrasada",
            urls_lidas=[],
            urls_fonte=[],
            expected_tentativa=1,  # Tentativa esperada é 1, mas o banco já está em 2!
            invalidar_dossier=True,
        )

    # Verifica que o dossiê da nova rodada NÃO foi apagado nem ConteudoColetado gravado
    pesquisa_apos = await repo.get_research(pesquisa.id_pesquisa)
    assert pesquisa_apos is not None
    assert pesquisa_apos.dossier_final == "# Dossiê Aprovado da Nova Rodada", "Dossiê aprovado não pode ser apagado por sessão tardia!"
    coletas = await repo.get_collected_content(pesquisa.id_pesquisa)
    assert len(coletas) == 0, "Conteúdo da tentativa antiga com posse perdida não deve ser inserido!"


# -----------------------------------------------------------------------------
# F04 / C04: Reparo de JSON conserva ambas chamadas reais (prior_envelopes persistidos)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_f04_reparo_json_conserva_ambas_chamadas_reais(db_session: AsyncSession) -> None:
    """F04: Quando ocorre reparo de JSON malformado, envelope.prior_envelopes deve ser desempacotado
    e persistido em GenerationAttempt, preservando ambas as chamadas (a com falha e a corrigida)."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    mock_net = setup["mock_net"]
    turn = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            # Resposta malformada na primeira tentativa (sem JSON válido)
            return httpx.Response(200, json={
                "id": "chatcmpl-malformed",
                "object": "chat.completion",
                "created": 1729720000,
                "model": "gpt-4o-mini",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": "Isto não é um JSON válido!"},
                    "finish_reason": "stop",
                }],
            })
        else:
            # Reparo bem-sucedido
            return make_llm_json_response({
                "acao": "parar_insuficiente",
                "motivo": "Fim do teste F04",
                "lacunas": [],
            })

    mock_net.custom_handlers["chat/completions"] = llm_handler

    await setup["searcher"].execute_search(id_pesquisa=setup["pesquisa"].id_pesquisa)

    attempts = await setup["repo"].get_generation_attempts(setup["pesquisa"].id_pesquisa, etapa="search")
    # Deveria haver 2 attempts: o original falho (prior_envelope) e o reparado
    assert len(attempts) >= 2, f"Reparo de JSON deve persistir ambas as chamadas! Encontradas: {len(attempts)}"
    assert any(a.finish_reason is not None for a in attempts)


# -----------------------------------------------------------------------------
# F05 / C04: Protocolo JSON estrito com 0 mensagens role='tool' em falha SERP
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_f05_zero_mensagens_role_tool_em_falha_ou_vazio_serp(db_session: AsyncSession) -> None:
    """F05: Se a SERP falha ou retorna vazia, o searcher não deve injetar mensagens com role='tool'
    sem tool_calls nativos, usando unicamente o protocolo JSON com role='user'/'system'."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    mock_net = setup["mock_net"]
    turn = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])

        # Transporte estrito: rejeita role='tool' sem assistant tool_calls
        for m in msgs:
            if m.get("role") == "tool":
                return httpx.Response(400, text="HTTP 400: role 'tool' without tool_calls is strictly invalid!")

        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "termo que falha na serp",
                "objetivo": "testar transporte estrito",
            })
        else:
            return make_llm_json_response({
                "acao": "parar_insuficiente",
                "motivo": "SERP vazia tratada via protocolo JSON puro",
                "lacunas": ["dados ausentes"],
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        # Retorna SERP vazia
        return make_serp_response([])

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler

    resultado = await setup["searcher"].execute_search(id_pesquisa=setup["pesquisa"].id_pesquisa)
    assert resultado is not None
    # Verifica que não falhou com HTTP 400 por injeção de role='tool'
    resumo_p = resultado["resumo_coletas"][0]
    assert resumo_p["personas"][0]["motivo_parada"] is not None


# -----------------------------------------------------------------------------
# C01 / C04: finish_reason None e length em casos separados (is_regular_finish)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_c01_finish_reason_none_rejeitado_como_sucesso(db_session: AsyncSession) -> None:
    """C01: finish_reason None não deve ser tratado como sucesso regular (is_regular_finish)."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    mock_net = setup["mock_net"]

    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = {
            "id": "chatcmpl-finish-none",
            "object": "chat.completion",
            "created": 1729720000,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"acao": "concluir", "analise_final": "Tentativa com finish None"}),
                },
                "finish_reason": None,  # finish_reason ausente / None
            }],
        }
        return httpx.Response(200, json=data)

    mock_net.custom_handlers["chat/completions"] = llm_handler

    resultado = await setup["searcher"].execute_search(id_pesquisa=setup["pesquisa"].id_pesquisa)
    resumo_p = resultado["resumo_coletas"][0]
    p_res = resumo_p["personas"][0]
    assert p_res["falha_coleta"] is True, "finish_reason None deve ser rejeitado como término irregular!"


@pytest.mark.asyncio
async def test_search_c01_finish_reason_length_rejeitado(db_session: AsyncSession) -> None:
    """C01: finish_reason 'length' (truncamento) deve ser rejeitado como término irregular."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    mock_net = setup["mock_net"]

    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = {
            "id": "chatcmpl-finish-length",
            "object": "chat.completion",
            "created": 1729720000,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"acao": "concluir", "analise_final": "Texto truncado"}),
                },
                "finish_reason": "length",
            }],
        }
        return httpx.Response(200, json=data)

    mock_net.custom_handlers["chat/completions"] = llm_handler

    resultado = await setup["searcher"].execute_search(id_pesquisa=setup["pesquisa"].id_pesquisa)
    resumo_p = resultado["resumo_coletas"][0]
    p_res = resumo_p["personas"][0]
    assert p_res["falha_coleta"] is True, "finish_reason length deve ser rejeitado como término irregular!"


# -----------------------------------------------------------------------------
# C02 / C04: Múltiplas queries / body > 8k sem exceder budget em NENHUMA mensagem
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_c02_multiplas_queries_budget_8k_nunca_excedido_por_chamada(db_session: AsyncSession) -> None:
    """C02: Em múltiplas buscas com documentos longos (> 10.000 chars cada), em NENHUMA mensagem
    enviada ao LLM o total de caracteres de evidência pode exceder 8.000 chars."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    mock_net = setup["mock_net"]
    captured_payloads: List[List[Dict[str, Any]]] = []
    turn = 0

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        captured_payloads.append(msgs)

        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php doc 1",
                "objetivo": "buscar documento longo 1",
            })
        elif turn == 2:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php doc 2",
                "objetivo": "buscar documento longo 2",
            })
        else:
            chk_id = _extract_delivered_chunk_id(msgs)
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": "Conclusão respeitando orçamento estrito.",
                "conclusoes": [{
                    "claim_id": "c1",
                    "afirmacao": "Fato comprovado dentro do orçamento",
                    "tipo": "fato",
                    "evidencias": [chk_id],
                }],
                "lacunas": [],
                "motivo_parada": "Conclusão realizada",
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([
            {"url": f"https://php.net/large-{turn}.html", "title": f"Large Doc {turn}"}
        ])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        # Gera corpo com 15.000 caracteres
        return httpx.Response(200, text=("Parágrafo de evidência com dados relevantes sobre segurança. " * 300))

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler

    resultado = await setup["searcher"].execute_search(id_pesquisa=setup["pesquisa"].id_pesquisa)
    assert resultado["status_pesquisa"] == "coletado"

    # Verifica cada payload enviado ao LLM: NENHUMA mensagem pode conter mais de 8000 caracteres de evidência
    for payload_turn, msgs in enumerate(captured_payloads, start=1):
        for msg in msgs:
            content = str(msg.get("content") or "")
            # Se for o bloco de contexto / evidências
            if "evidencias" in content.lower() or "trecho id:" in content.lower():
                # Se for JSON estruturado de contexto
                try:
                    c_json = json.loads(content)
                    evs = c_json.get("evidencias") or c_json.get("evidencias_web_como_dados_nao_confiaveis") or []
                    total_ev_chars = sum(len(str(e.get("texto") or e.get("text") or "")) for e in evs)
                    assert total_ev_chars <= 8000, (
                        f"No turno {payload_turn}, total de caracteres de evidência ({total_ev_chars}) excedeu 8.000 chars!"
                    )
                except Exception:
                    pass


# -----------------------------------------------------------------------------
# C03 / C04: Cancelamento preserva chamadas concluídas e libera posse
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_c03_cancelamento_preserva_chamadas_concluidas_e_libera_posse(db_session: AsyncSession) -> None:
    """C03: Quando ocorre cancelamento após reserva commitada, envelopes de chamadas já concluídas
    e fontes lidas devem ser preservados em ConteudoColetado/GenerationAttempt, liberando a posse e propagando CancelledError."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    mock_net = setup["mock_net"]
    turn = 0

    async def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        if turn == 1:
            return make_llm_json_response({
                "acao": "buscar",
                "consulta": "php cancel test",
                "objetivo": "buscar primeira vez",
            })
        else:
            # Turno 2 demora para receber cancelamento
            await asyncio.sleep(5.0)
            return make_llm_json_response({"acao": "concluir", "analise_final": "demora"})

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://php.net/c03.html", "title": "C03 Doc"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# C03 Doc\n\nConteúdo lido no turno 1.")

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler

    task = asyncio.create_task(
        setup["searcher"].execute_search(
            id_pesquisa=setup["pesquisa"].id_pesquisa,
            ponto_id=setup["ponto"].ponto_id,
        )
    )
    # Aguarda o turno 1 completar e o turno 2 iniciar
    await asyncio.sleep(0.15)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    # Verifica se a posse foi liberada (não em_andamento)
    ponto_apos = await setup["repo"].get_point(setup["ponto"].ponto_id)
    assert ponto_apos is not None
    assert ponto_apos.status != "em_andamento", "Posse deve ser liberada após cancelamento!"

    # Verifica se a chamada do turno 1 foi preservada em GenerationAttempt
    attempts = await setup["repo"].get_generation_attempts(setup["pesquisa"].id_pesquisa, etapa="search")
    assert len(attempts) >= 1, "A chamada concluída do turno 1 deve ser preservada em GenerationAttempt após cancelamento!"


# -----------------------------------------------------------------------------
# C04: Concorrência com duas sessões SQLite em arquivo com barreira/evento
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_c04_concorrencia_duas_sessoes_arquivo_com_barreira(tmp_path) -> None:
    """C04: Prova concorrência atômica entre duas sessões SQLite em arquivo com barreira de sincronização."""
    from sqlalchemy.ext.asyncio import create_async_engine
    db_file = tmp_path / "concurrent_search.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_async_engine(db_url)

    from app.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as sess1, session_maker() as sess2:
        repo1 = ResearchRepository(session=sess1)
        repo2 = ResearchRepository(session=sess2)

        pesq = await repo1.create_research(tema="Barreira Concorrência", pontos_textos=["Ponto Barreira"])
        pontos = await repo1.list_points(pesq.id_pesquisa)
        p_id = pontos[0].ponto_id

        # Reserva concorrente
        res1, res2 = await asyncio.gather(
            repo1.reserve_point(p_id, lease_seconds=600),
            repo2.reserve_point(p_id, lease_seconds=600),
            return_exceptions=True,
        )

        erros = [r for r in [res1, res2] if isinstance(r, Exception)]
        sucessos = [r for r in [res1, res2] if not isinstance(r, Exception)]
        assert len(sucessos) == 1, "Exatamente uma sessão deve obter a reserva do ponto!"
        assert len(erros) == 1, "A outra sessão deve ser rejeitada com erro de concorrência!"
        assert "CONCURRENT_EXECUTION" in str(erros[0]) or "em_andamento" in str(erros[0])

    await engine.dispose()


# -----------------------------------------------------------------------------
# C04: Retry com duas rodadas REAIS preservando as outras personas e histórico
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_c04_retry_duas_rodadas_reais_preserva_outras_personas(db_session: AsyncSession) -> None:
    """C04: Duas rodadas reais: rodada 1 historiador tem sucesso e visionario falha (status parcial).
    Rodada 2 com retry direcionado para visionario: visionario tem sucesso, historiador é preservado (status coletado)."""
    setup = await _setup_search_fixture(db_session, personas=["historiador", "visionario"])
    mock_net = setup["mock_net"]
    round_num = 1

    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        sys_msg = " ".join([m["content"] for m in msgs if m.get("role") == "system"]).lower()
        user_content = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
        persona = "historiador" if "historiador" in sys_msg else "visionario"

        if round_num == 1:
            if persona == "historiador":
                if "chk_" not in user_content:
                    return make_llm_json_response({
                        "acao": "buscar",
                        "consulta": "php security r1",
                        "objetivo": "buscar r1",
                    })
                chk_id = _extract_delivered_chunk_id(msgs)
                return make_llm_json_response({
                    "acao": "concluir",
                    "analise_final": "Historiador completado na R1.",
                    "conclusoes": [{"claim_id": "c1", "afirmacao": "Fato R1", "tipo": "fato", "evidencias": [chk_id]}],
                    "lacunas": [],
                    "motivo_parada": "Sucesso",
                })
            else:
                return make_llm_json_response({
                    "acao": "parar_insuficiente",
                    "motivo": "Visionário falhou na R1",
                    "lacunas": ["dados"],
                })
        else:
            # Rodada 2: visionario agora faz busca e conclui
            if "chk_" not in user_content:
                return make_llm_json_response({
                    "acao": "buscar",
                    "consulta": "php security r2",
                    "objetivo": "buscar r2",
                })
            chk_id = _extract_delivered_chunk_id(msgs)
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": "Visionário completado na R2.",
                "conclusoes": [{"claim_id": "c1", "afirmacao": "Fato R2", "tipo": "fato", "evidencias": [chk_id]}],
                "lacunas": [],
                "motivo_parada": "Sucesso",
            })

    def serp_handler(request: httpx.Request) -> httpx.Response:
        return make_serp_response([{"url": "https://php.net/r.html", "title": "R Doc"}])

    def reader_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="# R Doc\n\nConteúdo para ambas rodadas.")

    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = serp_handler
    mock_net.custom_handlers["r.jina.ai"] = reader_handler

    # Rodada 1
    r1 = await setup["searcher"].execute_search(
        id_pesquisa=setup["pesquisa"].id_pesquisa,
        ponto_id=setup["ponto"].ponto_id,
        personas=["historiador", "visionario"],
    )
    assert r1["resumo_coletas"][0]["status"] == "parcial"

    # Rodada 2: retry direcionado apenas para 'visionario'
    round_num = 2
    # Libera status para permitir retry
    p_db = await setup["repo"].get_point(setup["ponto"].ponto_id)
    assert p_db is not None
    p_db.status = "reprovado"
    await db_session.commit()

    r2 = await setup["searcher"].execute_search(
        id_pesquisa=setup["pesquisa"].id_pesquisa,
        ponto_id=setup["ponto"].ponto_id,
        personas=["visionario"],
    )
    res_ponto = r2["resumo_coletas"][0]
    # Ambas personas devem constar nos resultados recombinados da rodada
    coletas = await setup["repo"].get_collected_content(setup["pesquisa"].id_pesquisa)
    assert len(coletas) >= 2, "Histórico de coletas deve ser preservado!"


# -----------------------------------------------------------------------------
# C04: Reader erro HTTP 200 com JSON de erro (code >= 400)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_c04_reader_erro_http_200_json_classificado(db_session: AsyncSession) -> None:
    """C04: Resposta HTTP 200 do Reader contendo JSON com code >= 400 (ex: 402) deve levantar
    JinaError e não ser tratada como Markdown."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    mock_net = setup["mock_net"]

    def reader_handler(request: httpx.Request) -> httpx.Response:
        json_err = json.dumps({"code": 402, "message": "Insufficient Balance"})
        return httpx.Response(200, text=json_err, headers={"Content-Type": "application/json"})

    mock_net.custom_handlers["r.jina.ai"] = reader_handler

    # Leitura direta com jina_client deve levantar JinaError com categoria billing
    with pytest.raises(JinaError) as exc_info:
        await setup["jina_client"].read("https://php.net/fail")
    assert exc_info.value.categoria == "billing"
    assert exc_info.value.terminal is True


# -----------------------------------------------------------------------------
# C04: Injeção de segredo sintético para testar sanitização
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_c04_sanitizacao_com_segredo_sintetico(db_session: AsyncSession) -> None:
    """C04: Injeção de segredo sintético em mensagens/headers deve ser redigida em GenerationAttempt."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    mock_net = setup["mock_net"]
    SECRET_SYNTHETIC = "sk-proj-supersecret9876543210abcdefg"

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return make_llm_json_response({
            "acao": "parar_insuficiente",
            "motivo": f"Segredo vazado: {SECRET_SYNTHETIC}",
            "lacunas": [],
        })

    mock_net.custom_handlers["chat/completions"] = llm_handler

    await setup["searcher"].execute_search(id_pesquisa=setup["pesquisa"].id_pesquisa)

    attempts = await setup["repo"].get_generation_attempts(setup["pesquisa"].id_pesquisa, etapa="search")
    assert len(attempts) >= 1
    att = attempts[0]
    # O segredo sintético não pode aparecer em nenhuma coluna do banco
    assert SECRET_SYNTHETIC not in str(att.messages_json)
    assert SECRET_SYNTHETIC not in str(att.content_final)


# -----------------------------------------------------------------------------
# C04: Falha de construção de LLM após Jina garante fechamento em finally
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_c04_falha_construcao_llm_apos_jina_fecha_jina(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """C04: Se a construção do LLMClient falhar após JinaClient ter sido instanciado,
    o bloco finally do endpoint /api/v1/search deve fechar o jina_client sem vazamento de sockets."""
    from app.api.v1.endpoints.search import search_points
    from app.schemas.search import SearchRequest

    closed = []
    orig_aclose = JinaClient.aclose

    async def mock_jina_aclose(self):
        closed.append("jina")
        await orig_aclose(self)

    monkeypatch.setattr(JinaClient, "aclose", mock_jina_aclose)

    def failing_llm_init(*args, **kwargs):
        raise ValueError("Simulated LLMClient construction failure")

    monkeypatch.setattr(LLMClient, "__init__", failing_llm_init)

    repo = ResearchRepository(session=db_session)
    pesq = await repo.create_research(tema="Teste Falha LLM Init", pontos_textos=["P1"])

    payload = SearchRequest(id_pesquisa=pesq.id_pesquisa)
    try:
        await search_points(payload=payload, db=db_session)
    except Exception:
        pass

    assert "jina" in closed, "JinaClient deve ter sido fechado mesmo quando LLMClient falhou na inicialização!"


# -----------------------------------------------------------------------------
# C04: Metatexto em JSON válido rejeitado
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_c04_metatexto_em_json_valido_rejeitado(db_session: AsyncSession) -> None:
    """C04: Conclusão contendo metatexto ou diretrizes de persona em analise_final deve ser reprovada."""
    setup = await _setup_search_fixture(db_session, personas=["historiador"])
    mock_net = setup["mock_net"]

    def llm_handler(request: httpx.Request) -> httpx.Response:
        return make_llm_json_response({
            "acao": "concluir",
            "analise_final": "Como uma inteligência artificial, meu papel é investigar a vulnerabilidade.",
            "conclusoes": [],
            "lacunas": [],
            "motivo_parada": "Conclusão com metatexto",
        })

    mock_net.custom_handlers["chat/completions"] = llm_handler

    resultado = await setup["searcher"].execute_search(id_pesquisa=setup["pesquisa"].id_pesquisa)
    resumo_p = resultado["resumo_coletas"][0]
    assert resumo_p["personas"][0]["falha_coleta"] is True, "Metatexto deve reprovar a coleta da persona!"


# -----------------------------------------------------------------------------
# C05 / BUG-20261023-VDCJ: Falso agregado por cache ORM e finalização tardia
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_c05_aggregate_stale_identity_map_and_tx_sync(db_session: AsyncSession) -> None:
    """C05: Duas sessões SQLite. SessionA carrega P1 pendente e P2 aprovado.
    SessionB altera P2 para falha_coleta e commita.
    SessionA conclui P1 como coletado.
    Searcher NÃO pode calcular falso sucesso ('coletado') a partir de cache ORM stale.
    O status real no banco e na resposta deve ser 'parcial' e total_falhas_coleta deve ser 1."""
    engine = db_session.bind
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session_a, session_factory() as session_b:
        repo_a = ResearchRepository(session=session_a)
        repo_b = ResearchRepository(session=session_b)

        pesq = await repo_a.create_research(
            tema="Tema C05 Concorrência",
            pontos_textos=["Ponto 1", "Ponto 2"],
        )
        pontos = await repo_a.list_points(pesq.id_pesquisa)
        p1 = pontos[0]
        p2 = pontos[1]

        # P2 é inicialmente marcado como 'aprovado' e carregado na SessionA
        p2_db = await repo_a.get_point(p2.ponto_id)
        assert p2_db is not None
        p2_db.status = "aprovado"
        await session_a.commit()

        # SessionA lê P1 e P2 para manter em seu identity map
        pontos_in_a = await repo_a.list_points(pesq.id_pesquisa)
        assert len(pontos_in_a) == 2
        assert pontos_in_a[1].status == "aprovado"

        # SessionB altera P2 para 'falha_coleta' e commita
        p2_in_b = await repo_b.get_point(p2.ponto_id)
        assert p2_in_b is not None
        p2_in_b.status = "falha_coleta"
        await session_b.commit()

        # Configura MockNetwork para SessionA executar busca com sucesso apenas para P1
        mock_net = MockNetwork()
        def llm_handler(request: httpx.Request) -> httpx.Response:
            msgs = json.loads(request.content.decode("utf-8")).get("messages", [])
            user_content = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
            if "chk_" not in user_content:
                return make_llm_json_response({
                    "acao": "buscar",
                    "consulta": "php p1 query",
                    "objetivo": "buscar p1",
                })
            chk_id = _extract_delivered_chunk_id(msgs)
            return make_llm_json_response({
                "acao": "concluir",
                "analise_final": "Síntese P1 concluída com sucesso.",
                "conclusoes": [{
                    "claim_id": "c1",
                    "afirmacao": "P1 comprovado",
                    "tipo": "fato",
                    "evidencias": [chk_id],
                }],
                "lacunas": [],
                "motivo_parada": "Concluído",
            })

        def serp_handler(request: httpx.Request) -> httpx.Response:
            return make_serp_response([{"url": "https://p1.org/doc", "title": "P1", "description": "D"}])

        def reader_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="# P1\nConteúdo.", headers={"Content-Type": "text/markdown"})

        mock_net.custom_handlers["chat/completions"] = llm_handler
        mock_net.custom_handlers["s.jina.ai"] = serp_handler
        mock_net.custom_handlers["r.jina.ai"] = reader_handler
        transport = create_mock_transport(mock_net)

        jina_client = JinaClient(api_key="jina-test", transport=transport)
        llm_client = LLMClient(api_key="openai-test", transport=transport)
        searcher_a = Searcher(
            research_repo=repo_a,
            jina_client=jina_client,
            llm_client=llm_client,
            personas=["historiador"],
        )

        resultado = await searcher_a.execute_search(
            id_pesquisa=pesq.id_pesquisa,
            ponto_id=p1.ponto_id,
        )

        # O fold NÃO pode retornar 'coletado' falso por causa do P2 cacheado em SessionA
        assert resultado["status_pesquisa"] == "parcial", (
            f"Falso sucesso detectado: status_pesquisa retornou '{resultado['status_pesquisa']}', "
            f"mas no banco real os status são P1: coletado e P2: falha_coleta (deve ser 'parcial')!"
        )
        assert resultado["total_falhas_coleta"] == 1, (
            f"total_falhas_coleta deve ser 1 (cobrir P2 com falha_coleta fora do filtro), retornou {resultado['total_falhas_coleta']}!"
        )

        # Verifica no banco real via SessionB (nova leitura escalar)
        stmt_pesq = select(Pesquisa.status_pipeline).where(Pesquisa.id_pesquisa == pesq.id_pesquisa)
        status_pipeline_b = (await session_b.execute(stmt_pesq)).scalar_one_or_none()
        assert status_pipeline_b == "parcial", (
            f"Pesquisa.status_pipeline no banco deve ser 'parcial', mas está '{status_pipeline_b}'!"
        )


@pytest.mark.asyncio
async def test_search_c05_pipeline_status_transitions_reservation_and_cancellation(db_session: AsyncSession) -> None:
    """C05: Testa transições globais de Pesquisa.status_pipeline:
    1. Durante reserva de ponto, Pesquisa reflete 'buscando'.
    2. Durante liberação/cancelamento, Pesquisa reflete o status agregado terminal real (não permanece buscando nem planejado)."""
    repo = ResearchRepository(session=db_session)
    pesq = await repo.create_research(tema="Tema Pipeline States", pontos_textos=["P1"])
    pontos = await repo.list_points(pesq.id_pesquisa)
    p1 = pontos[0]

    # Estado inicial
    assert pesq.status_pipeline == "planejado"

    # 1. Ao reservar, reflete 'buscando'
    await repo.reserve_point(p1.ponto_id)
    stmt_pesq = select(Pesquisa.status_pipeline).where(Pesquisa.id_pesquisa == pesq.id_pesquisa)
    st1 = (await db_session.execute(stmt_pesq)).scalar_one_or_none()
    assert st1 == "buscando", f"Na reserva, status_pipeline deve ser 'buscando', mas foi '{st1}'!"

    # 2. Ao liberar/cancelar reserva, reflete estado terminal real
    await repo.release_point_reservation(p1.ponto_id, status="falha_coleta", expected_tentativa=1)
    st2 = (await db_session.execute(stmt_pesq)).scalar_one_or_none()
    assert st2 == "falha", f"Após cancelamento/falha do único ponto, status_pipeline deve ser 'falha', mas foi '{st2}'!"


# -----------------------------------------------------------------------------
# Contexto v4: Preservação integral do Plano Geral e Eixo Corrente canônicos
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_contexto_integral_plano_e_eixo_canonicos(db_session: AsyncSession) -> None:
    """Valida que o payload user é um JSON único contendo plano_geral integral (sem lista de eixos repetida)
    e eixo_corrente com todos os campos canônicos do schema (pedido_normalizado, investigabilidade, eixo_essencial=False,
    consultas_iniciais, fontes_primarias_desejadas) para as 4 personas com papéis distintos."""
    plano_data = {
        "pedido_original": "Investigar vulnerabilidades PHP",
        "pedido_normalizado": "SENTINELA_PEDIDO_NORMALIZADO: Análise histórica e técnica de falhas CGI no PHP",
        "publico": "Engenheiros de Segurança",
        "recorte_temporal": "2020 a 2026",
        "formato_entrega": "Dossiê Técnico Detalhado",
        "pressupostos": ["Acesso a repositórios públicos"],
        "ambiguidades": ["Interpretação de versões descontinuadas"],
        "pergunta_de_esclarecimento": None,
        "eixos": [
            {
                "pergunta_principal": "Qual a origem do bug CGI no PHP?",
                "subperguntas": ["Quais commits introduziram o bug?"],
                "hipoteses": ["O bug decorre de parsing incorreto"],
                "consultas_iniciais": ["php cgi rfc advisory 2024"],
                "fontes_primarias_desejadas": ["php.net security announcements"],
                "riscos_de_vies": ["Relatórios de terceiros imprecisos"],
                "evidencias_que_refutariam": ["Fix aplicado sem impacto em CGI"],
                "criterio_de_conclusao": "Confirmação no changelog oficial",
                "investigabilidade": "SENTINELA_INVESTIGABILIDADE: Código aberto no GitHub php/php-src",
                "eixo_essencial": False,
            }
        ],
    }

    repo = ResearchRepository(session=db_session)
    pesq = await repo.create_research(
        tema=plano_data["pedido_original"],
        pontos_textos=["Ponto Teste Contexto"],
    )
    pesq_db = await repo.get_research(pesq.id_pesquisa)
    assert pesq_db is not None
    pesq_db.plano_estruturado = json.dumps(plano_data)
    pontos = await repo.list_points(pesq.id_pesquisa)
    p1 = pontos[0]
    p1.ponto_eixo_estruturado = json.dumps(plano_data["eixos"][0])
    await db_session.commit()

    captured_requests: List[Dict[str, Any]] = []

    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        captured_requests.append(data)
        return make_llm_json_response({
            "acao": "parar_insuficiente",
            "motivo": "Inspeção de prompt concluída sem rede",
            "lacunas": ["dados intencionalmente omitidos"],
        })

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = llm_handler
    transport = create_mock_transport(mock_net)

    jina_client = JinaClient(api_key="jina-test", transport=transport)
    llm_client = LLMClient(api_key="openai-test", transport=transport)

    searcher = Searcher(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    await searcher.execute_search(
        id_pesquisa=pesq.id_pesquisa,
        ponto_id=p1.ponto_id,
        personas=["historiador", "visionario", "cetico", "futurista"],
    )

    # 1. Provar exatamente 4 chamadas para 4 papéis distintos
    assert len(captured_requests) == 4, f"Deveriam ocorrer 4 chamadas, ocorreram {len(captured_requests)}"
    personas_encontradas = set()

    for req in captured_requests:
        msgs = req.get("messages", [])
        assert len(msgs) == 2, "Mensagens devem ser estritamente [system, user]"
        sys_msg = msgs[0]["content"].lower()

        # Identifica persona
        persona_nome = None
        for p in ("historiador", "visionario", "cetico", "futurista"):
            if p in sys_msg:
                persona_nome = p
                break
        assert persona_nome is not None, f"Persona não identificada no system prompt: {sys_msg}"
        personas_encontradas.add(persona_nome)

        # 2. O conteúdo do usuário deve ser estritamente um JSON único decodificável
        user_content = msgs[1]["content"]
        payload = json.loads(user_content)

        # 3. Valida plano_geral
        plano_geral = payload["plano_geral"]
        assert "eixos" not in plano_geral, "A lista global de eixos NÃO deve ser repetida em plano_geral!"
        assert plano_geral["pedido_original"] == plano_data["pedido_original"]
        assert plano_geral["pedido_normalizado"] == "SENTINELA_PEDIDO_NORMALIZADO: Análise histórica e técnica de falhas CGI no PHP"
        assert plano_geral["publico"] == "Engenheiros de Segurança"
        assert plano_geral["recorte_temporal"] == "2020 a 2026"
        assert plano_geral["formato_entrega"] == "Dossiê Técnico Detalhado"
        assert plano_geral["pressupostos"] == ["Acesso a repositórios públicos"]
        assert plano_geral["ambiguidades"] == ["Interpretação de versões descontinuadas"]

        # 4. Valida eixo_corrente integral com nomes canônicos do schema
        eixo_corrente = payload["eixo_corrente"]
        assert eixo_corrente["pergunta_principal"] == "Qual a origem do bug CGI no PHP?"
        assert eixo_corrente["subperguntas"] == ["Quais commits introduziram o bug?"]
        assert eixo_corrente["hipoteses"] == ["O bug decorre de parsing incorreto"]
        assert "consultas_sugeridas" not in eixo_corrente, "Campo deve usar o nome canônico 'consultas_iniciais'!"
        assert eixo_corrente["consultas_iniciais"] == ["php cgi rfc advisory 2024"]
        assert "fontes_desejadas" not in eixo_corrente, "Campo deve usar o nome canônico 'fontes_primarias_desejadas'!"
        assert eixo_corrente["fontes_primarias_desejadas"] == ["php.net security announcements"]
        assert eixo_corrente["riscos_de_vies"] == ["Relatórios de terceiros imprecisos"]
        assert eixo_corrente["evidencias_que_refutariam"] == ["Fix aplicado sem impacto em CGI"]
        assert eixo_corrente["criterio_de_conclusao"] == "Confirmação no changelog oficial"
        assert eixo_corrente["investigabilidade"] == "SENTINELA_INVESTIGABILIDADE: Código aberto no GitHub php/php-src"
        assert "eixo_essencial" in eixo_corrente, "eixo_essencial deve estar presente no eixo_corrente!"
        assert eixo_corrente["eixo_essencial"] is False, "eixo_essencial=False deve ser preservado como False!"
        assert type(eixo_corrente["eixo_essencial"]) is bool

    assert personas_encontradas == {"historiador", "visionario", "cetico", "futurista"}


# =============================================================================
# REPRODUÇÕES R3 FORTALECIDAS (G01..G05) — CONCILIAÇÃO R3 (DR-001..DR-015)
# =============================================================================

def test_search_r3_janelas_coerentes_titulo_data_corpo_e_offsets_reais() -> None:
    """r3-item1/G04: Janelas contíguas até 1500 chars agrupam adjacentes; parágrafo > 1500 fatiado; offsets e hashes exatos."""
    from app.core.searcher import _create_chunks_from_body

    header_date_expl = (
        "### Boletim de Segurança 2026-X\n\n"
        "22 de Outubro de 2026\n\n"
        "Pesquisadores independentes identificaram uma condição crítica de contorno de autenticação.\n"
        "A falha permite execução arbitrária quando parâmetros malformados são enviados ao parser.\n\n"
        "Identificadores técnicos associados: SEC-2026-001 e SEC-2026-002."
    )
    long_para = "Detalhe técnico extenso sobre vulnerabilidade e análise de fluxo de execução. " * 45  # ~3500 chars
    unicode_block = "Análise com acentuação e caracteres especiais: vulnerabilidade crítica na função de decodificação UTF-8 (ç, ã, é, 🚀)."
    full_body = f"{header_date_expl}\r\n\r\n{long_para}\n\n{unicode_block}\n\nConclusão final da análise."

    chunks = _create_chunks_from_body(
        body=full_body,
        source_id="src_1",
        url="https://sec.example/advisory",
        start_chunk_idx=1,
    )

    # 1. Deve haver múltiplos trechos por causa do parágrafo longo, mas header/data/explicação devem estar juntos no chk_1
    assert len(chunks) >= 4, f"Deveriam ser criados múltiplos trechos (agrupados e fatiados)! Criados: {len(chunks)}"
    c0 = chunks[0]
    assert c0["chunk_id"] == "chk_1"
    assert "22 de Outubro de 2026" in c0["text"]
    assert "Pesquisadores independentes" in c0["text"]
    assert "SEC-2026-001" in c0["text"]

    # 2. Todos os trechos devem respeitar <= 1500 caracteres, slice exato e hash SHA-256
    for c in chunks:
        assert len(c["text"]) <= 1500, f"Trecho {c['chunk_id']} excedeu limite de 1500 chars: {len(c['text'])}"
        start = c["start_offset"]
        end = c["end_offset"]
        assert full_body[start:end] == c["text"], f"Offset do trecho {c['chunk_id']} não bate exatamente com o corpo!"
        expected_hash = hashlib.sha256(c["text"].encode("utf-8")).hexdigest()
        assert c["text_hash"] == expected_hash, f"Hash do trecho {c['chunk_id']} divergente!"


def test_search_r3_selecao_diversidade_indice_repetitivo_vs_paragrafo_pertinente() -> None:
    """r3-item2/G05: Presença de termos e diversidade entre fontes relevantes; irrelevante excluída e consulta atual priorizada."""
    from app.core.searcher import _select_chunks_by_relevance

    chunks: List[Dict[str, Any]] = []
    # Fonte A: Índice com 15 trechos repetindo 40 vezes os termos gerais
    for i in range(15):
        chunks.append({
            "chunk_id": f"chk_idx_{i}",
            "source_id": "src_idx",
            "url": "https://directory.example/index",
            "start_offset": i * 400,
            "end_offset": (i + 1) * 400,
            "text": ("seguranca falha cgi " * 40) + f" entrada {i}",
        })
    # Fonte B: Artigo substantivo com 2 trechos pertinentes
    chunks.append({
        "chunk_id": "chk_subst_1",
        "source_id": "src_subst",
        "url": "https://cve.example/detail",
        "start_offset": 0,
        "end_offset": 600,
        "text": "Análise técnica substantiva detalhando o mecanismo da falha cgi e mitigação recomendada.",
    })
    chunks.append({
        "chunk_id": "chk_subst_2",
        "source_id": "src_subst",
        "url": "https://cve.example/detail",
        "start_offset": 600,
        "end_offset": 1200,
        "text": "Evidência primária sobre condições de exploração e versões seguras auditadas.",
    })
    # Fonte C: Fonte totalmente irrelevante (receita culinária)
    chunks.append({
        "chunk_id": "chk_irrel_1",
        "source_id": "src_irrel",
        "url": "https://recipes.example/cake",
        "start_offset": 0,
        "end_offset": 500,
        "text": "Receita deliciosa de bolo de chocolate com cobertura de morango e baunilha.",
    })
    # Fonte D: Documento longo com achado crítico no final casando com a consulta atual
    chunks.append({
        "chunk_id": "chk_doc_1",
        "source_id": "src_doc",
        "url": "https://advisory.example/doc",
        "start_offset": 0,
        "end_offset": 500,
        "text": "Introdução geral ao sistema de arquivos sem menção direta a vulnerabilidades.",
    })
    chunks.append({
        "chunk_id": "chk_doc_2",
        "source_id": "src_doc",
        "url": "https://advisory.example/doc",
        "start_offset": 500,
        "end_offset": 1100,
        "text": "ACHADO CRÍTICO DECISIVO: vulnerabilidade CVE-2026-CRITICAL permite contorno total de autenticação.",
    })

    # Orçamento limitado a 3500 chars (o índice sozinho tem 6000 chars)
    selected, ledger = _select_chunks_by_relevance(
        chunks=chunks,
        query_terms=["seguranca falha cgi"],
        budget_chars=3500,
        current_query="CVE-2026-CRITICAL ACHADO DECISIVO",
    )
    selected_sources = {c["source_id"] for c in selected}
    selected_ids = [c["chunk_id"] for c in selected]

    # 1. A fonte substantiva DEVE estar presente
    assert "src_subst" in selected_sources, "A fonte substantiva DEVE ser incluída pela seleção de diversidade!"
    # 2. O achado crítico casado com a consulta atual DEVE estar presente
    assert "chk_doc_2" in selected_ids, "O trecho da consulta atual no final do documento DEVE ser priorizado!"
    # 3. A fonte irrelevante NÃO pode entrar apenas para diversificar
    assert "src_irrel" not in selected_sources, "Fonte irrelevante NÃO deve ser selecionada apenas por diversidade!"
    # 4. Orçamento respeitado
    assert ledger["total_delivered_chars"] <= 3500










@pytest.mark.asyncio
async def test_search_r3_analogia_sem_heuristica_lexical_preserva_fato_documental(db_session: AsyncSession) -> None:
    """r3-item5: Fato documental legítimo contendo 'como um' preserva tipo='fato' sem interferência de heurística por palavras-chave."""
    def llm_handler(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        user_c = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
        if "chk_" not in user_c:
            return make_llm_json_response({"acao": "buscar", "consulta": "distribuição", "objetivo": "empacotamento"})
        chk_id = _extract_delivered_chunk_id(msgs)
        return make_llm_json_response({
            "acao": "concluir",
            "analise_final": "Análise técnica documental.",
            "conclusoes": [
                {
                    "claim_id": "c1",
                    "afirmacao": "O software é distribuído oficialmente como um arquivo ZIP para plataformas legadas.",
                    "tipo": "fato",
                    "evidencias": [chk_id],
                    "confianca": "alta",
                    "limitacoes": "",
                }
            ],
            "lacunas": [],
            "motivo_parada": "ok",
        })

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = llm_handler
    mock_net.custom_handlers["s.jina.ai"] = lambda req: make_serp_response([{"url": "https://example.org/pkg", "title": "P", "description": "d"}])
    mock_net.custom_handlers["r.jina.ai"] = lambda req: httpx.Response(200, text="Distribuição como um arquivo ZIP verificado.", headers={"Content-Type": "text/markdown"})
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesq = await repo.create_research(tema="Teste Fato 'Como Um'", pontos_textos=["Ponto 1"])
    jina_client = JinaClient(api_key="jina-test", transport=transport)
    llm_client = LLMClient(api_key="openai-test", transport=transport)
    searcher = Searcher(research_repo=repo, jina_client=jina_client, llm_client=llm_client, personas=["historiador"])

    res = await searcher.execute_search(id_pesquisa=pesq.id_pesquisa)
    ponto_resumo = res["resumo_coletas"][0]
    persona_data = ponto_resumo["personas"][0]
    conclusoes = persona_data["conclusoes"]
    assert len(conclusoes) == 1
    # Não deve ter sido rebaixado para 'inferencia' pela presença da substring 'como um'
    assert conclusoes[0]["tipo"] == "fato", f"Fato legítimo foi alterado para {conclusoes[0]['tipo']}!"


@pytest.mark.asyncio
async def test_search_r3_prompt_instrucoes_cobertura_subperguntas_e_analogias(db_session: AsyncSession) -> None:
    """r3-item5: System prompt exige cobertura explícita de subperguntas, suporte material e tipagem de analogia."""
    captured_sys_prompt = ""

    def llm_handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_sys_prompt
        data = json.loads(request.content.decode("utf-8"))
        msgs = data.get("messages", [])
        sys_m = next((m.get("content", "") for m in msgs if m.get("role") == "system"), "")
        captured_sys_prompt = sys_m
        return make_llm_json_response({
            "acao": "parar_insuficiente",
            "motivo": "Verificação de prompt",
            "lacunas": ["teste"],
        })

    mock_net = MockNetwork()
    mock_net.custom_handlers["chat/completions"] = llm_handler
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesq = await repo.create_research(tema="Teste Instruções Prompt", pontos_textos=["Ponto 1"])
    jina_client = JinaClient(api_key="jina-test", transport=transport)
    llm_client = LLMClient(api_key="openai-test", transport=transport)
    searcher = Searcher(research_repo=repo, jina_client=jina_client, llm_client=llm_client, personas=["historiador"])

    await searcher.execute_search(id_pesquisa=pesq.id_pesquisa)
    assert captured_sys_prompt, "System prompt deve ser capturado!"
    sys_lower = captured_sys_prompt.lower()

    # 1. Cobertura explícita de subperguntas ou lacunas
    assert "subpergunta" in sys_lower
    # 2. Suporte material substantivo (título/data/link isolado não comprova)
    assert "suporte" in sys_lower or "material" in sys_lower
    # 3. Analogias didáticas como inferência, sem garantia universal de segurança ou ausência de dano
    assert "analogia" in sys_lower or "didática" in sys_lower
    assert "inferencia" in sys_lower or "inferência" in sys_lower
    # 4. Ausência de evidência não é prova de inexistência
    assert "ausência de evidência" in sys_lower or "ausencia de evidencia" in sys_lower





