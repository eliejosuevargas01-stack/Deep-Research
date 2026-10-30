# -*- coding: utf-8 -*-
"""Testes de reprodução e regressão para BUG-20261023-ZUI3 (DR-006).

Alvo: Validador de contrato estruturado no Planejador (Plan).
Defeito demonstrado:
Quando o modelo retorna um JSON que é um array ('["p1", "p2"]') ou null ('null')
em vez de um objeto JSON ('{"pontos": [...]}'), a chamada execute_plan
acessa parsed.get(...) diretamente, gerando um erro não tratado
AttributeError ('list' object has no attribute 'get' ou 'NoneType' object has no attribute 'get')
em vez de emitir um erro explícito de contrato e garantir ausência de persistência inválida.
"""
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from app.tools.jina_client import JinaClient
from app.core.planner import Planner
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response, make_serp_response


@pytest.mark.asyncio
async def test_planner_json_array_raises_contract_error_without_attribute_error(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Resposta JSON array deve gerar erro explícito de contrato, sem AttributeError.
    
    Cenário DR-006 / F-PLAN-ERR-02:
    O modelo retorna JSON válido, mas como lista: '["p1", "p2", "p3", "p4", "p5"]'.
    No código atual, app/core/planner.py:112 executa parsed.get("pontos", []),
    lançando AttributeError: 'list' object has no attribute 'get'.
    O comportamento esperado é falhar com erro semântico de contrato (ex: ValueError
    com mensagem explícita exigindo objeto JSON) e NÃO persistir pesquisa órfã.
    """
    mock_net = MockNetwork()
    # Retorna JSON array em vez de dict/objeto
    array_payload = ["ponto 1", "ponto 2", "ponto 3", "ponto 4", "ponto 5"]
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response(array_payload)
    mock_net.custom_handlers["s.jina.ai"] = lambda r: make_serp_response([
        {"title": "Doc", "url": "https://fontes.org", "description": "Desc"}
    ])
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    planner = Planner(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        n_pontos=5,
    )

    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL):
    # O código atual lança AttributeError. O teste exige erro explícito de contrato
    # e proíbe AttributeError genérico!
    try:
        await planner.execute_plan(tema="Tema Teste Array JSON")
        pytest.fail("Deveria ter lançado erro de contrato para JSON array.")
    except AttributeError as ae:
        pytest.fail(
            f"DEFEITO CONFIRMADO (BUG-20261023-ZUI3): execute_plan lançou AttributeError genérico "
            f"ao receber JSON array ({ae}), sem diagnóstico de contrato."
        )
    except ValueError as ve:
        # Esperado: erro amigável de contrato
        assert "objeto" in str(ve).lower() or "formato" in str(ve).lower() or "pontos" in str(ve).lower()


@pytest.mark.asyncio
async def test_planner_json_null_raises_contract_error_without_attribute_error(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Resposta JSON null deve gerar erro explícito de contrato, sem AttributeError."""
    mock_net = MockNetwork()
    # Retorna JSON null
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response("null")
    mock_net.custom_handlers["s.jina.ai"] = lambda r: make_serp_response([
        {"title": "Doc", "url": "https://fontes.org", "description": "Desc"}
    ])
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    planner = Planner(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        n_pontos=5,
    )

    try:
        await planner.execute_plan(tema="Tema Teste Null JSON")
        pytest.fail("Deveria ter lançado erro de contrato para JSON null.")
    except AttributeError as ae:
        pytest.fail(
            f"DEFEITO CONFIRMADO (BUG-20261023-ZUI3): execute_plan lançou AttributeError genérico "
            f"ao receber JSON null ({ae}), sem diagnóstico de contrato."
        )
    except ValueError as ve:
        assert "objeto" in str(ve).lower() or "formato" in str(ve).lower() or "pontos" in str(ve).lower()


@pytest.mark.asyncio
async def test_planner_valid_json_persists_research(
    db_session: AsyncSession,
) -> None:
    """[PROTEÇÃO/REGRESSÃO] Resposta JSON com esquema rico completo e 5 eixos persiste com sucesso."""
    mock_net = MockNetwork()
    valid_payload = {
        "pedido_original": "Tema Investigação Válida",
        "pedido_normalizado": "Escopo investigativo estruturado",
        "publico": "Geral e técnico",
        "formato_entrega": "Dossiê com citações e fontes primárias",
        "pressupostos": ["Busca exploratória inicial"],
        "ambiguidades": [],
        "eixos": [
            {
                "pergunta_principal": "Adoção de tutores inteligentes baseados em IA e impactos no letramento",
                "subperguntas": ["Como ferramentas de IA apoiam a alfabetização em turmas heterogêneas?"],
                "hipoteses": ["Tutores de IA reduzem o tempo de aquisição de leitura básica em 20%."],
                "consultas_iniciais": ["ia generativa letramento unesco relatorio"],
                "fontes_primarias_desejadas": ["Relatórios de avaliação pedagógica e diretrizes UNESCO"],
                "riscos_de_vies": ["Superestimação de benefícios por fornecedores de software"],
                "evidencias_que_refutariam": ["Estudo empírico independente demonstrando estagnação"],
                "criterio_de_conclusao": "Corroboração com pelo menos dois estudos independentes",
                "investigabilidade": "Viável via repositórios acadêmicos e bases abertas da UNESCO",
                "eixo_essencial": True,
            },
            {
                "pergunta_principal": "Desafios de plágio, integridade acadêmica e novas diretrizes de avaliação",
                "subperguntas": ["Quais mecanismos institucionais foram adotados contra fraudes?"],
                "hipoteses": ["Instituições substituem testes remotos por avaliações orais."],
                "consultas_iniciais": ["integridade academica ia diretrizes ocde"],
                "fontes_primarias_desejadas": ["Regulamentos de universidades e diretrizes da OCDE"],
                "riscos_de_vies": ["Foco desproporcional em punição em detrimento de formação"],
                "evidencias_que_refutariam": ["Aumento de casos sem qualquer alteração avaliativa"],
                "criterio_de_conclusao": "Mapeamento de 3 marcos institucionais vigentes",
                "investigabilidade": "Documentação pública disponível em portais acadêmicos",
                "eixo_essencial": True,
            },
            {
                "pergunta_principal": "Desigualdade no acesso digital e assimetrias regionais de infraestrutura",
                "subperguntas": ["Como a disparidade de conectividade afeta escolas rurais?"],
                "hipoteses": ["Escolas sem banda larga ficam excluídas de ferramentas avançadas."],
                "consultas_iniciais": ["censo escolar conectividade assimetrias mec"],
                "fontes_primarias_desejadas": ["Dados censitários e relatórios governamentais de infraestrutura"],
                "riscos_de_vies": ["Subnotificação de carências regionais"],
                "evidencias_que_refutariam": ["Universalização comprovada de acesso em todas as regiões"],
                "criterio_de_conclusao": "Dados estatísticos oficiais comprovando a cobertura",
                "investigabilidade": "Dados abertos em microdados censitários do MEC",
                "eixo_essencial": True,
            },
            {
                "pergunta_principal": "Formação continuada e capacitação do corpo docente para uso pedagógico de IA",
                "subperguntas": ["Quais programas formais de capacitação existem para professores?"],
                "hipoteses": ["Menos de 30% dos professores receberam treinamento estruturado."],
                "consultas_iniciais": ["capacitacao docente ia unesco pesquisa"],
                "fontes_primarias_desejadas": ["Pesquisas com amostras representativas de docentes"],
                "riscos_de_vies": ["Amostragem concentrada em grandes centros urbanos"],
                "evidencias_que_refutariam": ["Programas governamentais obrigatórios com 100% de adesão"],
                "criterio_de_conclusao": "Pesquisa amostral canônica com metodologia transparente",
                "investigabilidade": "Relatórios de pesquisa disponíveis publicamente",
                "eixo_essencial": True,
            },
            {
                "pergunta_principal": "Marcos regulatórios internacionais e políticas públicas de proteção à infância",
                "subperguntas": ["Quais salvaguardas de privacidade de dados infantis são exigidas?"],
                "hipoteses": ["Regulamentações impõem consentimento parental estrito para menores."],
                "consultas_iniciais": ["regulacao ia protecao dados infancia gdpr lgpd"],
                "fontes_primarias_desejadas": ["Legislação vigente (LGPD, AI Act, GDPR) e pareceres jurídicos"],
                "riscos_de_vies": ["Interpretação abstrata da lei sem jurisprudência consolidada"],
                "evidencias_que_refutariam": ["Inexistência de cláusulas específicas para menores"],
                "criterio_de_conclusao": "Citação dos artigos canônicos das leis pertinentes",
                "investigabilidade": "Textos oficiais das leis em diários oficiais",
                "eixo_essencial": True,
            },
        ],
    }
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response(valid_payload)
    mock_net.custom_handlers["s.jina.ai"] = lambda r: make_serp_response([
        {"title": "Doc", "url": "https://fontes.org", "description": "Desc"}
    ])
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    jina_client = JinaClient(api_key="jina-key", transport=transport)
    llm_client = LLMClient(api_key="openai-key", transport=transport)

    planner = Planner(
        research_repo=repo,
        jina_client=jina_client,
        llm_client=llm_client,
        n_pontos=5,
    )

    pesquisa = await planner.execute_plan(tema="Tema Investigação Válida")
    assert pesquisa is not None
    assert pesquisa.id_pesquisa is not None
    pontos = await repo.list_points(pesquisa.id_pesquisa)
    assert len(pontos) == 5
