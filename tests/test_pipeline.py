from __future__ import annotations

import sqlite3

import pytest

from conftest import FakeEngine
from contracts import PERSONAS, ResearchRequest
from orchestrator import Pipeline, PipelineError


def ponto(ponto_id: int) -> dict:
    return {
        "ponto_id": ponto_id,
        "enunciado": f"Ponto {ponto_id}",
        "subperguntas": [f"s{ponto_id}-{i}" for i in (1, 2, 3)],
        "hipoteses": [f"h{ponto_id}-{i}" for i in (1, 2, 3)],
        "lacunas_iniciais": [f"l{ponto_id}-{i}" for i in (1, 2, 3)],
        "perguntas_auditoria": {str(i): f"Pergunta {i} do ponto {ponto_id}" for i in range(1, 13)},
    }


def responder(papel, payload):
    if papel == "planner":
        return {"pontos": [ponto(i) for i in range(1, payload["profundidade"] + 1)]}
    if papel in PERSONAS:
        rodada = payload["rodada"]
        ponto_id = payload["ponto_id"]
        return {
            "informacao_coletada": f"coleta {papel} rodada {rodada} ponto {ponto_id}",
            "urls_usadas": [f"https://fonte/{papel}/{ponto_id}/{rodada}"],
            "urls_lidas": [
                f"https://fonte/{papel}/{ponto_id}/{rodada}",
                f"https://ignorada/{papel}/{ponto_id}/{rodada}",
            ],
        }
    if papel == "auditor":
        respostas = {str(i): True for i in range(1, 13)}
        if payload["tentativa_atual"] == 1:
            respostas.update({"4": False, "8": False, "10": False})
        else:
            respostas["8"] = False
        return {"perguntas_respondidas": respostas}
    if papel == "redator":
        acumulado = payload["informacao_coletada_acumulada_integral"]
        return {
            "relatorio_ponto": f"RELATORIO ponto {payload['ponto_id']} com {len(acumulado)} rodadas",
            "lacunas_identificadas": f"faltou a pergunta 8 do ponto {payload['ponto_id']}",
            "urls_citadas": payload["urls_usadas_acumuladas"],
        }
    raise AssertionError(f"papel inesperado: {papel}")


@pytest.fixture
def pipeline(config, repositorio):
    engine = FakeEngine(responder)
    webhooks: list[tuple[str, dict]] = []
    pipeline = Pipeline(
        repositorio,
        engine,
        config,
        notificador=lambda url, payload, timeout_s: webhooks.append((url, payload)),
    )
    pipeline.engine_fake = engine
    pipeline.webhooks = webhooks
    return pipeline


def test_pipeline_completo_com_retentativa_e_webhook(config, repositorio, pipeline):
    requisicao = ResearchRequest(
        tema="matriz energética brasileira",
        profundidade=2,
        veracidade_alvo=90,
        max_rodadas_auditoria=4,
        atualidade="24H",
        callback_url="https://webhook.example/cb",
    )
    research_id = pipeline.criar(requisicao)
    pipeline.executar(research_id)

    run = repositorio.obter_run(research_id)
    assert run["status"] == "COMPLETED"
    assert "## 1. Ponto 1" in run["relatorio_final_consolidado"]
    assert run["relatorio_final_consolidado"].index("## 1.") < run[
        "relatorio_final_consolidado"
    ].index("## 2.")

    pontos = repositorio.obter_pontos(research_id)
    assert [ponto["aprovado"] for ponto in pontos] == [True, True]
    assert [ponto["porcentagem_aprovacao"] for ponto in pontos] == [91.67, 91.67]
    assert [ponto["rodada_atual"] for ponto in pontos] == [2, 2]
    assert pontos[0]["ultimo_resultado_auditor"]["8"] is False

    engine: FakeEngine = pipeline.engine_fake
    auditorias = engine.payloads("auditor")
    for ponto_id in (1, 2):
        primeira = next(
            p for p in auditorias if p["ponto_id"] == ponto_id and p["tentativa_atual"] == 1
        )
        assert [bloco["rodada"] for bloco in primeira["informacao_coletada_acumulada"]] == [1]

        segunda = next(
            p for p in auditorias if p["ponto_id"] == ponto_id and p["tentativa_atual"] == 2
        )
        blocos = segunda["informacao_coletada_acumulada"]
        assert [bloco["rodada"] for bloco in blocos] == [1, 2]
        assert blocos[0]["historiador"] == f"coleta historiador rodada 1 ponto {ponto_id}"
        assert blocos[1]["futurista"] == f"coleta futurista rodada 2 ponto {ponto_id}"

    persona_rodada_2 = next(
        p for p in engine.payloads("historiador") if p["ponto_id"] == 1 and p["rodada"] == 2
    )
    assert set(persona_rodada_2["perguntas_auditoria_pendentes"]) == {"4", "8", "10"}
    assert persona_rodada_2["perguntas_auditoria_pendentes"]["8"] == "Pergunta 8 do ponto 1"
    assert len(persona_rodada_2["urls_lidas_ignoradas"]) == 8  # 4 personas x 2 URLs na rodada 1
    assert all("fonte/" in url or "ignorada/" in url for url in persona_rodada_2["urls_lidas_ignoradas"])

    redator = next(p for p in engine.payloads("redator") if p["ponto_id"] == 1)
    assert redator["resultado_final_auditor"]["8"] is False
    assert len(redator["informacao_coletada_acumulada_integral"]) == 2
    assert len(redator["urls_usadas_acumuladas"]) == 8

    # 1 planner + 2 pontos x (8 personas + 2 auditorias + 1 redator)
    with sqlite3.connect(config.pipeline.db_path) as con:
        total_execucoes = con.execute("SELECT COUNT(*) FROM agent_executions").fetchone()[0]
    assert total_execucoes == 23
    assert run["total_tokens"] == 23 * 160

    assert len(pipeline.webhooks) == 1
    url, payload = pipeline.webhooks[0]
    assert url == "https://webhook.example/cb"
    assert set(payload) == {
        "research_id",
        "relatorio_final",
        "lacunas_finais",
        "urls_usadas",
        "urls_lidas",
        "urls_lidas_nao_usadas",
        "metricas_tokens",
    }
    assert len(payload["urls_usadas"]) == 16  # 2 pontos x 4 personas x 2 rodadas
    assert len(payload["urls_lidas"]) == 32
    assert len(payload["urls_lidas_nao_usadas"]) == 16
    assert payload["metricas_tokens"]["total_tokens"] == 23 * 160


def test_planner_invalido_retenta_e_registra_tentativa_rejeitada(config, repositorio):
    tentativas = {"planner": 0}

    def responder_com_falha(papel, payload):
        if papel == "planner":
            tentativas["planner"] += 1
            if tentativas["planner"] == 1:
                incompleto = ponto(1)
                incompleto["perguntas_auditoria"].pop("12")
                return {"pontos": [incompleto]}
        return responder(papel, payload)

    engine = FakeEngine(responder_com_falha)
    pipeline = Pipeline(
        repositorio, engine, config, notificador=lambda *args, **kwargs: None
    )
    research_id = pipeline.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=2,
            veracidade_alvo=90,
            callback_url="https://webhook.example/cb",
        )
    )
    pipeline.executar(research_id)

    assert repositorio.obter_run(research_id)["status"] == "COMPLETED"
    assert len(engine.payloads("planner")) == 2
    with sqlite3.connect(config.pipeline.db_path) as con:
        rejeitadas = con.execute(
            "SELECT COUNT(*) FROM agent_executions WHERE agent_role = 'planner'"
        ).fetchone()[0]
    assert rejeitadas == 2


def test_falha_de_uma_persona_nao_derruba_o_ponto(config, repositorio):
    def responder_sem_cetico(papel, payload):
        if papel == "cetico":
            raise RuntimeError("provider fora do ar")
        return responder(papel, payload)

    engine = FakeEngine(responder_sem_cetico)
    pipeline = Pipeline(repositorio, engine, config, notificador=lambda *args, **kwargs: None)
    research_id = pipeline.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=1,
            veracidade_alvo=90,
            callback_url="https://webhook.example/cb",
        )
    )
    pipeline.executar(research_id)

    assert repositorio.obter_run(research_id)["status"] == "COMPLETED"
    auditoria = engine.payloads("auditor")[0]
    personas = set(auditoria["informacao_coletada_acumulada"][0]) - {"rodada"}
    assert personas == {"historiador", "visionario", "futurista"}


def test_falha_total_do_ponto_marca_run_como_failed(config, repositorio):
    def responder_quebrado(papel, payload):
        if papel in PERSONAS:
            raise RuntimeError("sem engine")
        return responder(papel, payload)

    pipeline = Pipeline(
        repositorio, FakeEngine(responder_quebrado), config, notificador=lambda *a, **k: None
    )
    research_id = pipeline.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=1,
            veracidade_alvo=90,
            callback_url="https://webhook.example/cb",
        )
    )
    with pytest.raises(PipelineError):
        pipeline.executar(research_id)
    assert repositorio.obter_run(research_id)["status"] == "FAILED"
