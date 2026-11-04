from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts import AuditorSaida, BuscadorSaida, PontoPlano, ResearchRequest
from planner import ACAO_NOVA_RODADA, ACAO_REDATOR, ACAO_REDATOR_LIMITE, avaliar, taxa_aprovacao


def perguntas_auditoria() -> dict[str, str]:
    return {str(i): f"Pergunta {i}" for i in range(1, 13)}


def ponto(**overrides) -> PontoPlano:
    dados = {
        "ponto_id": 1,
        "enunciado": "Enunciado",
        "subperguntas": ["a", "b", "c"],
        "hipoteses": ["h1", "h2", "h3"],
        "lacunas_iniciais": ["l1", "l2", "l3"],
        "perguntas_auditoria": perguntas_auditoria(),
    }
    dados.update(overrides)
    return PontoPlano(**dados)


def test_requisicao_rejeita_profundidade_fora_da_faixa():
    with pytest.raises(ValidationError):
        ResearchRequest(
            tema="matriz energética",
            profundidade=11,
            veracidade_alvo=90,
            callback_url="https://webhook.example/cb",
        )


def test_ponto_exige_as_doze_perguntas():
    incompletas = perguntas_auditoria()
    incompletas.pop("12")
    with pytest.raises(ValidationError):
        ponto(perguntas_auditoria=incompletas)


def test_ponto_exige_minimo_de_tres_por_lista():
    with pytest.raises(ValidationError):
        ponto(subperguntas=["a", "b"])


def test_auditor_coerce_strings_e_exige_doze_chaves():
    saida = AuditorSaida.model_validate(
        {"perguntas_respondidas": {str(i): "true" if i != 8 else "false" for i in range(1, 13)}}
    )
    assert saida.perguntas_respondidas["8"] is False
    assert sum(saida.perguntas_respondidas.values()) == 11

    with pytest.raises(ValidationError):
        AuditorSaida.model_validate({"perguntas_respondidas": {"1": True}})


def test_auditor_rejeita_valor_nao_booleano():
    with pytest.raises(ValidationError):
        AuditorSaida.model_validate({"perguntas_respondidas": {str(i): 1 for i in range(1, 13)}})


def test_buscador_normaliza_urls_e_calcula_diferenca():
    saida = BuscadorSaida.model_validate(
        {
            "informacao_coletada": " texto ",
            "urls_usadas": ["https://usada", " https://usada "],
            "urls_lidas": ["https://lida-nao-usada", "https://usada"],
        }
    )
    assert saida.informacao_coletada == "texto"
    assert saida.urls_usadas == ["https://usada"]
    assert saida.urls_lidas == ["https://lida-nao-usada", "https://usada"]
    assert saida.urls_lidas_nao_usadas == ["https://lida-nao-usada"]


@pytest.mark.parametrize(
    "rodada,qtd_true,porcentagem,aprovado,proxima_acao",
    [
        (1, 8, 66.67, False, ACAO_NOVA_RODADA),
        (2, 10, 83.33, False, ACAO_NOVA_RODADA),
        (2, 11, 91.67, True, ACAO_REDATOR),
        (3, 12, 100.0, True, ACAO_REDATOR),
        (4, 9, 75.0, False, ACAO_REDATOR_LIMITE),
    ],
)
def test_tabela_de_decisao_do_feature_06(rodada, qtd_true, porcentagem, aprovado, proxima_acao):
    respostas = {str(i): i <= qtd_true for i in range(1, 13)}
    decisao = avaliar(
        perguntas_respondidas=respostas,
        veracidade_alvo=90,
        tentativa_atual=rodada,
        max_rodadas_auditoria=4,
    )
    assert decisao["porcentagem_aprovacao"] == porcentagem
    assert decisao["aprovado"] is aprovado
    assert decisao["proxima_acao"] == proxima_acao


def test_taxa_usa_doze_como_denominador():
    assert taxa_aprovacao({str(i): False for i in range(1, 13)}) == 0.0
    assert taxa_aprovacao({str(i): True for i in range(1, 13)}) == 100.0
