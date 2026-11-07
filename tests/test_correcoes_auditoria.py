"""Correções da auditoria: merge monotônico, URLs canônicas, host duro, blocklist."""

from __future__ import annotations

import pytest

from contracts import (
    PERGUNTAS_AUDITORIA_ESTATICAS,
    BuscadorSaida,
    chave_url,
    normalizar_urls,
)


def test_merge_monotonico_preserva_true():
    anteriores = {str(i): (i <= 8) for i in range(1, 13)}
    brutas = {str(i): (i in (1, 9)) for i in range(1, 13)}
    mescladas = {
        k: bool(anteriores.get(k, False) or brutas.get(k, False)) for k in anteriores
    }
    assert sum(mescladas.values()) == 9  # 8 antigas + pergunta 9 nova
    assert all(mescladas[str(i)] for i in range(1, 10))
    assert not any(mescladas[str(i)] for i in range(10, 13))


def test_carregar_auditoria_roundtrip_e_ausente(repositorio):
    from contracts import ResearchRequest

    repositorio.criar_run(
        "R-M",
        ResearchRequest(
            tema="tema teste",
            profundidade=1,
            veracidade_alvo=90,
            max_rodadas_auditoria=4,
            atualidade="ALL",
            callback_url="https://webhook.example/cb",
        ),
    )
    assert repositorio.carregar_auditoria(research_id="R-M", ponto_id=1) == {}
    repositorio.salvar_plano(
        "R-M",
        {"ok": True},
        [
            __import__("contracts").PontoPlano(
                ponto_id=1,
                enunciado="Ponto 1",
                subperguntas=["a", "b", "c"],
                hipoteses=["h1", "h2", "h3"],
                lacunas_iniciais=["l1", "l2", "l3"],
            )
        ],
    )
    respostas = {str(i): (i <= 4) for i in range(1, 13)}
    repositorio.salvar_auditoria(
        research_id="R-M",
        ponto_id=1,
        rodada=1,
        perguntas_respondidas=respostas,
        decisao={"porcentagem_aprovacao": 33.33, "aprovado": False},
    )
    assert repositorio.carregar_auditoria(research_id="R-M", ponto_id=1) == respostas


def test_merge_nunca_rebaixa_via_pipeline(config, repositorio):
    """R1 8/12 true, R2 só pergunta 9 true → ponto fica com 9/12 (nunca cai)."""
    from conftest import FakeExecutor
    from contracts import ResearchRequest
    from orchestrator import Pipeline

    def responder(papel, payload):
        if papel == "planner":
            return {
                "pontos": [
                    {
                        "ponto_id": 1,
                        "enunciado": "Ponto 1",
                        "subperguntas": ["a", "b", "c"],
                        "hipoteses": ["h1", "h2", "h3"],
                        "lacunas_iniciais": ["l1", "l2", "l3"],
                    }
                ]
            }
        if papel in ("historiador", "cetico", "visionario", "futurista"):
            url = f"https://exemplo.test/1/r{payload['rodada']}/{papel}"
            return {
                "informacao_coletada": f"fato ({url})",
                "urls_usadas": [url],
                "urls_lidas": [url],
            }
        if papel == "auditor":
            if payload["tentativa_atual"] == 1:
                return {"perguntas_respondidas": {str(i): (i <= 8) for i in range(1, 13)}}
            return {"perguntas_respondidas": {str(i): (i == 9) for i in range(1, 13)}}
        if papel == "redator":
            return {
                "relatorio_ponto": "relatorio",
                "lacunas_identificadas": "lacunas",
                "urls_citadas": payload["urls_usadas_acumuladas"],
            }
        raise AssertionError(papel)

    pipe = Pipeline(repositorio, FakeExecutor(responder), config, notificador=lambda *a, **k: None)
    rid = pipe.criar(
        ResearchRequest(
            tema="tema teste",
            profundidade=1,
            veracidade_alvo=90,
            max_rodadas_auditoria=4,
            atualidade="ALL",
            callback_url="https://webhook.example/cb",
        )
    )
    pipe.executar(rid)
    ponto = repositorio.obter_pontos(rid)[0]
    assert ponto["porcentagem_aprovacao"] == 75.0  # 9/12, nunca 8.33
    assert sum(1 for v in ponto["ultimo_resultado_auditor"].values() if v) == 9
    eventos = [e for e in repositorio.listar_eventos(rid) if e["tipo"] == "auditoria.executada"]
    assert [e["payload"]["rodada"] for e in eventos] == [1, 2, 3, 4]
    # Monotônico: true nunca cai — R2 já soma a 9 (1-8 da R1 + 9 nova) e mantém.
    trues = [sum(1 for v in e["payload"]["perguntas_respondidas"].values() if v) for e in eventos]
    assert trues == [8, 9, 9, 9]
    assert eventos[-1]["payload"]["perguntas_respondidas_rodada"] == {
        str(i): (i == 9) for i in range(1, 13)
    }
    assert sum(1 for v in eventos[-1]["payload"]["perguntas_respondidas"].values() if v) == 9


def test_auditor_ausente_reaproveita_merge(config, repositorio):
    from conftest import FakeExecutor
    from contracts import ResearchRequest
    from orchestrator import Pipeline

    chamadas = {"n": 0}

    def responder(papel, payload):
        if papel == "planner":
            return {
                "pontos": [
                    {
                        "ponto_id": 1,
                        "enunciado": "Ponto 1",
                        "subperguntas": ["a", "b", "c"],
                        "hipoteses": ["h1", "h2", "h3"],
                        "lacunas_iniciais": ["l1", "l2", "l3"],
                    }
                ]
            }
        if papel in ("historiador", "cetico", "visionario", "futurista"):
            url = f"https://exemplo.test/1/r{payload['rodada']}/{papel}"
            return {"informacao_coletada": f"fato ({url})", "urls_usadas": [url], "urls_lidas": [url]}
        if papel == "auditor":
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return {"perguntas_respondidas": {str(i): (i <= 6) for i in range(1, 13)}}
            return None  # simula auditor sem saída na rodada 2
        if papel == "redator":
            return {
                "relatorio_ponto": "relatorio",
                "lacunas_identificadas": "lacunas",
                "urls_citadas": payload["urls_usadas_acumuladas"],
            }
        raise AssertionError(papel)

    pipe = Pipeline(repositorio, FakeExecutor(responder), config, notificador=lambda *a, **k: None)
    rid = pipe.criar(
        ResearchRequest(
            tema="tema teste",
            profundidade=1,
            veracidade_alvo=90,
            max_rodadas_auditoria=4,
            atualidade="ALL",
            callback_url="https://webhook.example/cb",
        )
    )
    pipe.executar(rid)
    ponto = repositorio.obter_pontos(rid)[0]
    assert sum(1 for v in ponto["ultimo_resultado_auditor"].values() if v) == 6
    redator = pipe._executor.payloads("redator")[0]
    assert sorted(redator["perguntas_nao_concluidas"], key=int) == [str(i) for i in range(7, 13)]


def test_normalizar_urls_colapsa_variantes():
    assert normalizar_urls(
        [
            "https://www.EPE.gov.br/BEN/",
            "https://epe.gov.br/BEN",
            "https://epe.gov.br/%42EN",
            "https://EPE.GOV.BR/ben#frag",
        ]
    ) == ["https://www.EPE.gov.br/BEN/"]
    assert normalizar_urls(["https://epe.gov.br/a?x=1", "https://www.epe.gov.br/a?x=1"]) == [
        "https://epe.gov.br/a?x=1"
    ]


def test_url_valida_rejeita_host_truncado():
    with pytest.raises(ValueError, match="fazenda.pt-br"):
        normalizar_urls(["https://www.fazenda.pt-br/composicao/"])
    with pytest.raises(ValueError, match="fazenda.pt-br"):
        BuscadorSaida.model_validate(
            {
                "informacao_coletada": "fato",
                "urls_usadas": ["https://www.fazenda.pt-br/composicao/"],
                "urls_lidas": [],
            }
        )
    # IDN punycode é domínio válido e não pode virar ValueError.
    assert normalizar_urls(["https://example.xn--p1ai/a"]) == ["https://example.xn--p1ai/a"]


def test_blocklist_descarta_sem_erro(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="contracts"):
        saidas = normalizar_urls(
            [
                "https://www.prezi.com/abc/slides",
                "https://x.com/user/status/1",
                "https://epe.gov.br/ben",
            ]
        )
    assert saidas == ["https://epe.gov.br/ben"]
    assert "prezi.com" in caplog.text and "x.com" in caplog.text


def test_chave_url_estavel():
    # www, caixa, barra final, porta default, fragment e percent-encoding colapsam;
    # scheme e query distinguem (http ≠ https, query distinta).
    assert chave_url("https://WWW.epe.gov.br/BEN/") == chave_url("https://epe.gov.br:443/ben#x")
    assert chave_url("http://epe.gov.br:80/BEN") == chave_url("http://epe.gov.br/ben")
    assert chave_url("https://epe.gov.br/a") != chave_url("http://epe.gov.br/a")
    assert chave_url("https://EPE.gov.br/%62en") == "https://epe.gov.br/ben"
    assert chave_url("https://epe.gov.br/a?x=1") != chave_url("https://epe.gov.br/a?x=2")


def test_nao_usadas_compara_por_chave(repositorio):
    from contracts import ResearchRequest
    from engine import AgentCall

    repositorio.criar_run(
        "R-U",
        ResearchRequest(
            tema="tema teste",
            profundidade=1,
            veracidade_alvo=90,
            max_rodadas_auditoria=4,
            atualidade="ALL",
            callback_url="https://webhook.example/cb",
        ),
    )
    repositorio.registrar_execucao(
        research_id="R-U",
        ponto_id=1,
        rodada=1,
        agent_role="historiador",
        input_prompt_payload={},
        call=AgentCall(dados={"ok": True}),
        informacao_coletada="fato",
        urls_usadas=["https://epe.gov.br/ben"],
        urls_lidas=["https://www.EPE.gov.br/BEN/", "https://blog-antigo.com/x"],
    )
    execucao = repositorio.obter_execucoes("R-U")[0]
    assert execucao["urls_lidas_nao_usadas"] == ["https://blog-antigo.com/x"]


def test_perguntas_4_e_8_novo_texto():
    assert "metodologia claramente identificadas" in PERGUNTAS_AUDITORIA_ESTATICAS["4"]
    assert "divergências metodológicas" in PERGUNTAS_AUDITORIA_ESTATICAS["8"]
