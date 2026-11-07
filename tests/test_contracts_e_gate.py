from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts import (
    PERGUNTAS_AUDITORIA_ESTATICAS,
    AuditorSaida,
    BuscadorSaida,
    PontoPlano,
    ResearchRequest,
)
from planner import ACAO_NOVA_RODADA, ACAO_REDATOR, ACAO_REDATOR_LIMITE, avaliar, taxa_aprovacao


def perguntas_auditoria() -> dict[str, str]:
    return dict(PERGUNTAS_AUDITORIA_ESTATICAS)


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


def test_auditor_exige_booleanos_estritos():
    saida = AuditorSaida.model_validate(
        {"perguntas_respondidas": {str(i): (i != 8) for i in range(1, 13)}}
    )
    assert saida.perguntas_respondidas["8"] is False
    assert sum(saida.perguntas_respondidas.values()) == 11

    with pytest.raises(ValidationError):
        AuditorSaida.model_validate({"perguntas_respondidas": {"1": True}})

    for bruto in ("true", "false", 1, 0, None):
        with pytest.raises(ValidationError):
            AuditorSaida.model_validate(
                {"perguntas_respondidas": {str(i): (True if str(i) != "1" else bruto) for i in range(1, 13)}}
            )


def test_auditor_rejeita_valor_nao_booleano():
    with pytest.raises(ValidationError):
        AuditorSaida.model_validate({"perguntas_respondidas": {str(i): 1 for i in range(1, 13)}})


def test_buscador_rejeita_url_invalida():
    from contracts import normalizar_urls

    assert normalizar_urls(["https://fonte.test/x).", "  https://fonte.test/y]; "]) == [
        "https://fonte.test/x",
        "https://fonte.test/y",
    ]
    for ruim in ["ftp://fonte.test/x", "sem-esquema", "https://", "https://exa mplo/x"]:
        with pytest.raises(ValidationError):
            BuscadorSaida.model_validate(
                {"informacao_coletada": "fato", "urls_usadas": [ruim], "urls_lidas": []}
            )


def test_buscador_normaliza_urls_e_calcula_diferenca():
    saida = BuscadorSaida.model_validate(
        {
            "informacao_coletada": " texto ",
            "urls_usadas": ["https://usada.test", " https://usada.test "],
            "urls_lidas": ["https://lida-nao-usada.test", "https://usada.test"],
        }
    )
    assert saida.informacao_coletada == "texto"
    assert saida.urls_usadas == ["https://usada.test"]
    assert saida.urls_lidas == ["https://lida-nao-usada.test", "https://usada.test"]
    assert saida.urls_lidas_nao_usadas == ["https://lida-nao-usada.test"]


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


def test_avaliacao_pontos_monta_objeto_sdd_57():
    """SDD §5.7: agregado exato da spec a partir das decisões já calculadas."""
    from planner import avaliacao_pontos

    respostas_1 = {str(i): i != 8 for i in range(1, 13)}  # 11/12
    respostas_2 = {str(i): i <= 8 for i in range(1, 13)}  # 8/12
    decisao_1 = {"ponto_id": 1, **avaliar(
        perguntas_respondidas=respostas_1, veracidade_alvo=90,
        tentativa_atual=2, max_rodadas_auditoria=4,
    )}
    decisao_2 = {"ponto_id": 2, **avaliar(
        perguntas_respondidas=respostas_2, veracidade_alvo=90,
        tentativa_atual=2, max_rodadas_auditoria=4,
    )}

    objeto = avaliacao_pontos(
        research_id="123ABC321", tema="matriz energetica no Brasil.",
        tentativa_atual=2, avaliacoes=[decisao_1, decisao_2],
    )

    assert objeto == {
        "research_id": "123ABC321",
        "tentativa_atual": 2,
        "tema": "matriz energetica no Brasil.",
        "avaliacao_pontos": [
            {
                "ponto_id": 1, "perguntas_true": 11, "total_perguntas": 12,
                "porcentagem_aprovacao": 91.67, "meta_veracidade_alvo": 90.0,
                "aprovado": True,
            },
            {
                "ponto_id": 2, "perguntas_true": 8, "total_perguntas": 12,
                "porcentagem_aprovacao": 66.67, "meta_veracidade_alvo": 90.0,
                "aprovado": False,
            },
        ],
    }


def test_perguntas_estaticas_sao_doze_binarias_sem_ponto():
    assert set(PERGUNTAS_AUDITORIA_ESTATICAS) == {str(i) for i in range(1, 13)}
    for texto in PERGUNTAS_AUDITORIA_ESTATICAS.values():
        assert "(sim/não)" in texto


def test_ponto_sem_perguntas_usa_estaticas():
    sem = PontoPlano(
        ponto_id=1,
        enunciado="Enunciado",
        subperguntas=["a", "b", "c"],
        hipoteses=["h1", "h2", "h3"],
        lacunas_iniciais=["l1", "l2", "l3"],
    )
    assert sem.perguntas_auditoria == PERGUNTAS_AUDITORIA_ESTATICAS
