"""Regressão R5 do roteamento de persona no MockNetwork (causa 3 do writer-r5).

O contexto legítimo enviado pelo Writer ao avaliador auditor_redacao contém o
plano da investigação (eixos/pontos) e evidências; o despacho anterior por
texto integral casava as regras amplas "planejador/pontos/eixos" ANTES da
persona auditando o artigo, devolvendo JSON do planejador em vez do vetor 12
de qualidade. A persona específica do system role deve ser priorizada, sem
perder o texto do usuário para extração de refs/URLs.

Mock não prova mérito factual de artigo: prova apenas o DESPACHO correto da
persona simulada. Roda sobre o mock R4 sem edições de app.
"""

import json

import pytest

from app.core.writer import Writer
from app.tools.llm_client import LLMClient
from tests.mocks.http_mock import MockNetwork, create_mock_transport


@pytest.mark.asyncio
async def test_mock_routes_auditor_redacao_system_over_user_plano_context() -> None:
    """Persona auditor_redacao no system role deve prevalecer sobre contexto do usuário
    com plano/pontos/eixos: o fake devolve vetor 12 de qualidade com refs conhecidas,
    nunca o JSON estruturado do planejador."""
    net = MockNetwork()
    llm = LLMClient(api_key="key", transport=create_mock_transport(net))

    system_prompt = Writer._construir_prompt_avaliacao(None)

    contexto_usuario = {
        "plano": {
            "pedido_original": "Impacto da IA na Educação",
            "publico": "Educadores e pesquisadores",
            "eixos": [
                {"pergunta_principal": "Adoção de tutores inteligentes baseados em IA"},
                {"pergunta_principal": "Desafios de plágio e integridade acadêmica"},
            ],
            "pontos": [
                "Adoção de tutores inteligentes baseados em IA e impactos no letramento",
                "Desafios de plágio, integridade acadêmica e novas diretrizes de avaliação",
            ],
        },
        "eixos": [
            {"pergunta_principal": "Adoção de tutores inteligentes baseados em IA"},
            {"pergunta_principal": "Desafios de plágio e integridade acadêmica"},
        ],
        "pontos": [
            "Adoção de tutores inteligentes baseados em IA e impactos no letramento",
            "Desafios de plágio, integridade acadêmica e novas diretrizes de avaliação",
        ],
        "fontes": {
            "https://unesdoc.unesco.org/ark:/48223/pf0000377897": "trecho coletado na leitura",
        },
        "claims": [{"claim_id": "clm_1", "afirmacao": "Evidência primária."}],
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "CONTEXTO ESTRUTURADO DE EVIDÊNCIAS E PARECERES:\n"
            + json.dumps(contexto_usuario, ensure_ascii=False)
            + "\n\nAvalie o artigo e devolva estritamente o JSON com os 12 critérios canônicos.",
        },
    ]

    envelope = await llm.call_envelope(
        model=llm.model_strong,
        messages=messages,
        response_format={"type": "json_object"},
    )

    parsed = json.loads(envelope.content_final or "")

    # Deve ser a avaliação do artigo (vetor 12), NÃO o JSON do planejador
    assert "criterios" in parsed, (
        "Persona auditor_redacao deve receber vetor 12 do avaliador; "
        "despacho por texto integral devolveu JSON do planejador."
    )
    assert "eixos" not in parsed and "pontos" not in parsed, "JSON do plano não pode vazar como avaliação"

    criterios = parsed["criterios"]
    assert len(criterios) == 12
    assert [c["id"] for c in criterios] == list(range(1, 13))
    assert all(c["aprovado"] is True for c in criterios)

    # Refs conhecidas extraídas do texto integral do usuário (fontes/URLs/claims preservados)
    assert criterios[0]["source_ids"] == ["https://unesdoc.unesco.org/ark:/48223/pf0000377897"]
    assert criterios[0]["claim_ids"] == ["clm_1"]

    # Requisição de fato despachada ao LLM simulado
    assert any("chat/completions" in str(r.url) for r in net.requests)

    await llm.aclose()
