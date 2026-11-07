from __future__ import annotations

import json

import hydrator
from evidencias import compactar_acumulado, compactar_texto

from contracts import PERGUNTAS_AUDITORIA_ESTATICAS

PONTO = {
    "ponto_id": 1,
    "enunciado": "Ponto único",
    "subperguntas": ["a"],
    "hipoteses": ["a"],
    "lacunas_iniciais": ["a"],
    "perguntas_auditoria": dict(PERGUNTAS_AUDITORIA_ESTATICAS),
}


def test_linhas_unicas_permanecem_duplicatas_somem():
    texto = "Fato solar 42% em 2024 (https://fonte.test/a)\nCompartilhar\nFato solar 42% em 2024 (https://fonte.test/a)\nOutro fato único"
    compacto, est = compactar_texto(texto)
    assert "Fato solar 42% em 2024 (https://fonte.test/a)" in compacto
    assert "Outro fato único" in compacto
    assert compacto.count("Fato solar 42%") == 1
    assert "Compartilhar" not in compacto
    assert est["linhas_antes"] == 4 and est["linhas_depois"] == 2
    assert est["chars_depois"] < est["chars_antes"]


def test_numeros_urls_datas_intactos():
    texto = "Receita R$ 1.234,56 em 12/03/2024, veja https://exemplo.org/x?a=1"
    compacto, _ = compactar_texto(texto)
    assert compacto == texto
    texto2 = "Home > seção\nDado com 7 unidades relevante"
    compacto2, _ = compactar_texto(texto2)
    assert "Dado com 7 unidades relevante" in compacto2  # dígito protege do ruído


def test_payloads_auditor_redator_menores_shape_igual():
    acumulado = [
        {
            "rodada": 1,
            "historiador": "Fato A 10% (https://f.test/a)\nCompartilhar\nFato A 10% (https://f.test/a)",
            "cetico": "Fato A 10% (https://f.test/a)\nFato B 20/01/2024",
        }
    ]
    antes = len(json.dumps(acumulado, ensure_ascii=False))
    auditor = hydrator.payload_auditor(
        research_id="R",
        atualidade="24H",
        ponto=PONTO,
        tentativa_atual=1,
        max_rodadas_auditoria=2,
        acumulado=acumulado,
    )
    redator = hydrator.payload_redator(
        research_id="R",
        ponto=PONTO,
        resultado_final_auditor={str(i): True for i in range(1, 13)},
        urls_usadas_acumuladas=["https://f.test/a"],
        acumulado_integral=acumulado,
    )
    for chave in (
        "research_id",
        "ponto_id",
        "persona",
        "soul",
        "atualidade",
        "tentativa_atual",
        "max_rodadas_auditoria",
        "perguntas_auditoria",
        "informacao_coletada_acumulada",
    ):
        assert chave in auditor
    for chave in (
        "research_id",
        "ponto_id",
        "persona",
        "soul",
        "ponto_enunciado",
        "resultado_final_auditor",
        "perguntas_auditoria",
        "perguntas_nao_concluidas",
        "erro_coleta",
        "urls_usadas_acumuladas",
        "informacao_coletada_acumulada_integral",
    ):
        assert chave in redator
    depois_a = len(json.dumps(auditor["informacao_coletada_acumulada"], ensure_ascii=False))
    depois_r = len(json.dumps(redator["informacao_coletada_acumulada_integral"], ensure_ascii=False))
    assert depois_a < antes and depois_r < antes
    corpo = auditor["informacao_coletada_acumulada"][0]
    assert corpo["rodada"] == 1
    assert "10%" in corpo["historiador"] and "https://f.test/a" in corpo["historiador"]
    assert auditor["compactacao"]["chars_depois"] < auditor["compactacao"]["chars_antes"]
    # Persistido intacto: entrada original não foi mutada.
    assert acumulado[0]["historiador"].count("Fato A 10%") == 2


def test_compactar_acumulado_preserva_chaves_nao_texto():
    acumulado = [{"rodada": 2, "nota": 7, "nada": None, "txt": "x\nx\ny"}]
    saida, _ = compactar_acumulado(acumulado)
    assert saida[0]["rodada"] == 2 and saida[0]["nota"] == 7 and saida[0]["nada"] is None
    assert saida[0]["txt"] == "x\ny"
