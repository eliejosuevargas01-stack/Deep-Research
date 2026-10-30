# -*- coding: utf-8 -*-
"""Testes de reprodução e regressão para BUG-20261023-KLXD (DR-002, DR-010, DR-015).

Alvo: Auditoria com deliberação programática estrita baseada nas 12 perguntas (vetor 12).
Defeito demonstrado:
1. O auditor aprova com base em nota e status subjetivos emitidos livremente pelo LLM,
   sem validar a existência e integridade do vetor estruturado das 12 perguntas.
2. Não há cálculo determinístico no backend: sum(c['aprovado'] for c in criterios).
3. Meta 85%+ exige default de 11/12 (91,67%). 10/12 (83,33%) é abaixo de 85% e deve
   reprovar por padrão (com opção de limiar configurável explícito 10).
"""
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient
from app.core.auditor import Auditor
from tests.mocks.http_mock import MockNetwork, create_mock_transport
from tests.unit.test_reproduction_gate1_helpers import make_llm_json_response


def _make_criterios_vector(aprovados_count: int) -> list:
    """Gera lista canônica de 12 critérios com IDs 1..12 e N aprovados."""
    return [
        {
            "id": i,
            "aprovado": (i <= aprovados_count),
            "justificativa": f"Justificativa para o critério {i}",
            "claim_ids": [f"claim_{i}"],
            "source_ids": [f"source_{i}"],
        }
        for i in range(1, 13)
    ]


@pytest.mark.asyncio
async def test_auditor_freeform_status_without_criteria_vector_must_not_approve(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] O auditor não pode aprovar sem o vetor das 12 perguntas preenchido.
    
    Cenário DR-002 / F-AUDIT-CONFORMIDADE-01:
    O modelo retorna JSON com status='aprovado' e pontuacao_percentual=95, mas omite
    completamente o vetor estruturado 'criterios' com as 12 respostas booleanas.
    O backend não pode aceitar a nota livre do modelo; deve exigir o vetor e deliberar
    pela soma dos critérios.
    """
    mock_net = MockNetwork()
    payload = {
        "status": "aprovado",
        "pontuacao_percentual": 95,
        "pontos_fracos": None,
        "resumo_auditoria": "Parecer intuitivo sem critérios estruturados",
        # 'criterios' ausente propositalmente!
    }
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response(payload)
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Tema Auditoria", pontos_textos=["Ponto 1"])
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Evidência real coletada com fonte",
        urls_lidas=["https://exemplo.org"],
        urls_fonte=["https://exemplo.org"],
    )

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    auditor = Auditor(research_repo=repo, llm_client=llm_client)

    resultado = await auditor.execute_audit(id_pesquisa=pesquisa.id_pesquisa)
    auditoria = resultado["auditorias"][0]

    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL):
    # app/core/auditor.py:179-180 lê parsed.get('status') == 'aprovado' e pontuacao >= 85,
    # aprovando o ponto sem validar o vetor 12!
    assert auditoria["status"] != "aprovado", (
        "DEFEITO CONFIRMADO (BUG-20261023-KLXD): Auditoria aprovou ponto com base em status livre "
        "do LLM sem validar o vetor obrigatório das 12 perguntas."
    )


@pytest.mark.asyncio
async def test_auditor_vector_9_of_12_must_be_reproved(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Vetor com 9 verdadeiros (75%) deve ser REPROVADO em qualquer configuração."""
    mock_net = MockNetwork()
    payload = {
        "status": "aprovado",  # LLM tenta aprovar erroneamente
        "pontuacao_percentual": 90,  # Nota livre inflada
        "criterios": _make_criterios_vector(9),  # 9 True, 3 False
        "resumo_auditoria": "9 de 12 critérios atendidos",
    }
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response(payload)
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Tema Auditoria", pontos_textos=["Ponto 1"])
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Evidência",
        urls_lidas=["https://exemplo.org"],
        urls_fonte=["https://exemplo.org"],
    )

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    auditor = Auditor(research_repo=repo, llm_client=llm_client)

    resultado = await auditor.execute_audit(id_pesquisa=pesquisa.id_pesquisa)
    auditoria = resultado["auditorias"][0]

    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL):
    # Código atual não calcula sum(aprovado for c in criterios), confia no status="aprovado"!
    assert auditoria["status"] == "reprovado", (
        "DEFEITO CONFIRMADO (BUG-20261023-KLXD): Ponto com 9/12 critérios verdadeiros foi aprovado "
        "porque o LLM emitiu status='aprovado'."
    )


@pytest.mark.asyncio
async def test_auditor_vector_10_of_12_without_score_reproved_under_default_threshold_11(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Meta 85%+ exige default 11/12 (91,67%). 10/12 (83,33%) sem nota livre DEVE REPROVAR.
    
    Cenário DR-002 / F-AUDIT-ERROS-01:
    O modelo retorna status='aprovado', sem emitir pontuacao_percentual (ou nota livre nula),
    com 10 critérios True e 2 False.
    No código atual, como pontuacao_percentual é None, a guarda de 85% é ignorada e o status
    'aprovado' é aceito cegamente.
    O comportamento esperado é calcular sum(c['aprovado'] for c in criterios) == 10 e, sob o
    default 11, deliberar como REPROVADO.
    """
    mock_net = MockNetwork()
    payload = {
        "status": "aprovado",
        "pontuacao_percentual": None,  # Nota ausente!
        "criterios": _make_criterios_vector(10),  # 10 True, 2 False
        "resumo_auditoria": "10 de 12 critérios atendidos",
    }
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response(payload)
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Tema Auditoria", pontos_textos=["Ponto 1"])
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Evidência",
        urls_lidas=["https://exemplo.org"],
        urls_fonte=["https://exemplo.org"],
    )

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    auditor = Auditor(research_repo=repo, llm_client=llm_client)

    resultado = await auditor.execute_audit(id_pesquisa=pesquisa.id_pesquisa)
    auditoria = resultado["auditorias"][0]

    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL):
    # O código atual faz: status = "aprovado" if status_raw == "aprovado" else "reprovado"
    # e como pontuacao é None, não executa o if float(pontuacao) < 85.0!
    assert auditoria["status"] == "reprovado", (
        "DEFEITO CONFIRMADO (BUG-20261023-KLXD): Ponto com 10/12 critérios e nota ausente foi aprovado "
        "cegamente pelo status do LLM, violando o default 11/12 da meta 85%+."
    )


@pytest.mark.asyncio
async def test_auditor_explicit_threshold_10_configuration(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] A implementação futura deve oferecer limiar configurável explícito 10 ou 11.
    
    Na configuração 10: 9 reprova e 10/11/12 aprovam.
    Na configuração 11 (padrão): 10 reprova.
    No código atual, o Auditor não suporta parâmetro de limiar (min_criterios_aprovados ou threshold)
    e não calcula os critérios programaticamente.
    """
    mock_net = MockNetwork()
    payload_10 = {
        "criterios": _make_criterios_vector(10),
        "resumo_auditoria": "10 de 12 atendidos",
    }
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response(payload_10)
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Tema Auditoria", pontos_textos=["Ponto 1"])
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Evidência",
        urls_lidas=["https://exemplo.org"],
        urls_fonte=["https://exemplo.org"],
    )

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    
    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL):
    # O Auditor atual não possui suporte a limiar explícito configurável 10/11:
    # passar min_aprovados=10 ou threshold=10 gera TypeError no __init__ ou execute_audit,
    # demonstrando ausência da funcionalidade exigida no backlog DR-002/DR-010.
    with pytest.raises((TypeError, ValueError)):
        # Demonstra que a API existente não oferece limiar configurável
        Auditor(research_repo=repo, llm_client=llm_client, min_aprovados=10)


@pytest.mark.asyncio
async def test_auditor_invalid_criteria_vector_ids_and_types_must_not_approve(
    db_session: AsyncSession,
) -> None:
    """[REPRODUÇÃO] Vetor com cardinalidade errada (11 itens), IDs duplicados ou 'sim' textual não pode aprovar.
    
    Invariantes obrigatórias do vetor 12:
    - len(criterios) == 12
    - [c['id'] for c in criterios] == list(range(1, 13))
    - all(isinstance(c['aprovado'], bool) for c in criterios)
    """
    mock_net = MockNetwork()
    # Vetor corrompido: 11 itens, id duplicado e bool em string ("sim")
    corrupted_vector = [
        {"id": 1, "aprovado": "sim"},  # String em vez de bool
        {"id": 1, "aprovado": True},   # ID duplicado
    ] + [
        {"id": i, "aprovado": True} for i in range(3, 12)  # Falta o id 12 (apenas 11 itens)
    ]
    payload = {
        "status": "aprovado",
        "pontuacao_percentual": 100,
        "criterios": corrupted_vector,
        "resumo_auditoria": "Vetor inválido",
    }
    mock_net.custom_handlers["chat/completions"] = lambda r: make_llm_json_response(payload)
    transport = create_mock_transport(mock_net)

    repo = ResearchRepository(session=db_session)
    pesquisa = await repo.create_research(tema="Tema Auditoria", pontos_textos=["Ponto 1"])
    ponto = (await repo.list_points(pesquisa.id_pesquisa))[0]
    await repo.save_collected_content(
        id_pesquisa=pesquisa.id_pesquisa,
        ponto_id=ponto.ponto_id,
        tema=pesquisa.tema,
        ponto=ponto.ponto,
        conteudo_coletado="Evidência",
        urls_lidas=["https://exemplo.org"],
        urls_fonte=["https://exemplo.org"],
    )

    llm_client = LLMClient(api_key="openai-key", transport=transport)
    auditor = Auditor(research_repo=repo, llm_client=llm_client)

    resultado = await auditor.execute_audit(id_pesquisa=pesquisa.id_pesquisa)
    auditoria = resultado["auditorias"][0]

    # ASSERÇÃO DE CONTRATO (FALHA NO CÓDIGO ATUAL):
    # Código atual não valida se len==12, ids==1..12 ou se aprovado é bool.
    assert auditoria["status"] != "aprovado", (
        "DEFEITO CONFIRMADO (BUG-20261023-KLXD): Vetor com IDs duplicados, cardinalidade errada "
        "e 'sim' textual foi aceito e aprovado pelo sistema."
    )
