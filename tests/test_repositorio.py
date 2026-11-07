from __future__ import annotations

from contracts import ResearchRequest
from engine import AgentCall


def requisicao() -> ResearchRequest:
    return ResearchRequest(
        tema="matriz energética brasileira",
        profundidade=1,
        veracidade_alvo=90,
        max_rodadas_auditoria=4,
        atualidade="24H",
        callback_url="https://webhook.example/cb",
    )


def test_urls_lidas_nao_usadas_calculadas_na_persistencia(repositorio):
    repositorio.criar_run("R1", requisicao())
    repositorio.registrar_execucao(
        research_id="R1",
        ponto_id=1,
        rodada=1,
        agent_role="historiador",
        input_prompt_payload={"x": 1},
        call=AgentCall(dados={"ok": True}, total_tokens=10, prompt_tokens=6, completion_tokens=4),
        informacao_coletada="texto",
        urls_usadas=["https://epe.gov.br/ben"],
        urls_lidas=["https://epe.gov.br/ben", "https://blog-antigo.com"],
    )
    run = repositorio.obter_run("R1")
    assert run["total_tokens"] == 10

    execucao = repositorio.obter_execucoes("R1")[0]
    assert execucao["urls_lidas_nao_usadas"] == ["https://blog-antigo.com"]
    assert execucao["urls_usadas"] == ["https://epe.gov.br/ben"]
    assert execucao["urls_lidas"] == ["https://epe.gov.br/ben", "https://blog-antigo.com"]


def test_hidratacao_preserva_todas_as_rodadas_e_personas(repositorio):
    repositorio.criar_run("R2", requisicao())
    textos = {}
    for rodada in (1, 2, 3):
        for persona in ("historiador", "cetico", "visionario", "futurista"):
            texto = f"{persona} rodada {rodada} " + ("x" * 500)
            textos[(rodada, persona)] = texto
            repositorio.registrar_execucao(
                research_id="R2",
                ponto_id=1,
                rodada=rodada,
                agent_role=persona,
                input_prompt_payload={},
                call=AgentCall(dados={}),
                informacao_coletada=texto,
                urls_usadas=[f"https://fonte/{persona}/{rodada}"],
                urls_lidas=[
                    f"https://fonte/{persona}/{rodada}",
                    f"https://ignorada/{persona}/{rodada}",
                ],
            )

    acumulado = repositorio.hidratar("R2", 1)
    assert [bloco["rodada"] for bloco in acumulado["rodadas"]] == [1, 2, 3]
    for bloco in acumulado["rodadas"]:
        assert list(bloco) == ["rodada", "historiador", "cetico", "visionario", "futurista"]
        for persona in ("historiador", "cetico", "visionario", "futurista"):
            assert bloco[persona] == textos[(bloco["rodada"], persona)]
    assert len(acumulado["urls_lidas"]) == 24  # 3 rodadas x 4 personas x 2 URLs
    assert len(acumulado["urls_usadas"]) == 12  # 3 rodadas x 4 personas


def test_replanejamento_substitui_os_pontos(repositorio):
    from contracts import PontoPlano

    repositorio.criar_run("R3", requisicao())

    def ponto(ponto_id):
        from contracts import PERGUNTAS_AUDITORIA_ESTATICAS

        return PontoPlano(
            ponto_id=ponto_id,
            enunciado=f"p{ponto_id}",
            subperguntas=["a", "b", "c"],
            hipoteses=["a", "b", "c"],
            lacunas_iniciais=["a", "b", "c"],
            perguntas_auditoria=dict(PERGUNTAS_AUDITORIA_ESTATICAS),
        )

    repositorio.salvar_plano("R3", {"pontos": []}, [ponto(1), ponto(2)])
    repositorio.salvar_plano("R3", {"pontos": []}, [ponto(1)])
    assert [p["ponto_id"] for p in repositorio.obter_pontos("R3")] == [1]


def test_fallback_de_total_soma_reasoning_tokens(repositorio):
    """RNF01 lacuna (d): total_tokens==0 não pode descartar reasoning_tokens."""
    repositorio.criar_run("R4", requisicao())
    repositorio.registrar_execucao(
        research_id="R4",
        ponto_id=1,
        rodada=1,
        agent_role="historiador",
        input_prompt_payload={},
        call=AgentCall(
            dados={"ok": True}, total_tokens=0, prompt_tokens=10, completion_tokens=5, reasoning_tokens=3
        ),
    )

    execucao = repositorio.obter_execucoes("R4")[0]
    assert execucao["total_tokens"] == 18  # 10 + 5 + 3, não 15
    assert repositorio.obter_run("R4")["total_tokens"] == 18
