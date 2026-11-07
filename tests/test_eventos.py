"""Eventos persistidos + SSE replay/snapshot + resiliência por ponto."""

from __future__ import annotations

import pytest

from conftest import FakeExecutor
from contracts import PERSONAS, ResearchRequest
from fastapi.testclient import TestClient

from api import create_app
from orchestrator import Pipeline


def ponto(ponto_id: int) -> dict:
    return {
        "ponto_id": ponto_id,
        "enunciado": f"Ponto {ponto_id}",
        "subperguntas": [f"s{ponto_id}-{i}" for i in (1, 2, 3)],
        "hipoteses": [f"h{ponto_id}-{i}" for i in (1, 2, 3)],
        "lacunas_iniciais": [f"l{ponto_id}-{i}" for i in (1, 2, 3)],
    }


def responder(papel, payload):
    if papel == "planner":
        return {"pontos": [ponto(i) for i in range(1, payload["profundidade"] + 1)]}
    if papel in PERSONAS:
        return {
            "informacao_coletada": f"coleta {papel}",
            "urls_usadas": [f"https://fonte/{papel}"],
            "urls_lidas": [f"https://fonte/{papel}"],
        }
    if papel == "auditor":
        return {"perguntas_respondidas": {str(i): True for i in range(1, 13)}}
    if papel == "redator":
        return {
            "relatorio_ponto": f"RELATORIO ponto {payload['ponto_id']}",
            "lacunas_identificadas": "nenhuma",
            "urls_citadas": payload["urls_usadas_acumuladas"],
        }
    raise AssertionError(f"papel inesperado: {papel}")


def requisicao(profundidade: int = 1, **extras) -> ResearchRequest:
    Padrao = {"tema": "tema de teste", "veracidade_alvo": 90, "callback_url": "https://webhook.example/cb"}
    Padrao.update(extras)
    return ResearchRequest(profundidade=profundidade, **Padrao)


def test_eventos_persistidos_na_ordem(repositorio):
    repositorio.criar_run("R-EV", requisicao())
    ids = [repositorio.emitir_evento("R-EV", f"t{i}", {"n": i}) for i in range(3)]
    assert ids == sorted(ids)
    eventos = repositorio.listar_eventos("R-EV")
    assert [e["tipo"] for e in eventos] == ["t0", "t1", "t2"]
    assert eventos[0]["payload"] == {"n": 0}
    depois = repositorio.listar_eventos("R-EV", depois_de=ids[0])
    assert [e["id"] for e in depois] == ids[1:]


def _ler_blocos(cliente, url, *, headers=None, limite_blocos=3, **params):
    """Lê N blocos SSE e fecha: o endpoint é um stream infinito."""
    blocos: list[str] = []
    atual: list[str] = []
    with cliente.stream("GET", url, headers=headers, params=params or None) as resposta:
        assert resposta.status_code == 200
        for linha in resposta.iter_lines():
            if linha == "":
                if atual:
                    blocos.append("\n".join(atual))
                    atual = []
                    if len(blocos) >= limite_blocos:
                        break
            elif not linha.startswith(":"):
                atual.append(linha)
    return blocos


def test_sse_snapshot_e_replay_last_event_id(config, repositorio):
    pipeline = Pipeline(
        repositorio, FakeExecutor(responder), config, notificador=lambda *a, **k: None
    )
    cliente = TestClient(create_app(pipeline))
    rid = pipeline.criar(requisicao(profundidade=1, veracidade_alvo=0, max_rodadas_auditoria=1))

    blocos = _ler_blocos(cliente, f"/research/{rid}/eventos", limite_blocos=1)
    assert blocos[0].startswith("id: ")
    assert "\nevent: snapshot\n" in blocos[0]
    assert f'"research_id": "{rid}"' in blocos[0]

    pipeline.executar(rid)
    eventos = repositorio.listar_eventos(rid)
    tipos = [e["tipo"] for e in eventos]
    for esperado in ("plano.pronto", "auditoria.executada", "tokens.atualizados", "run.concluido"):
        assert esperado in tipos
    assert [e["id"] for e in eventos] == sorted(e["id"] for e in eventos)

    segundo_id = eventos[1]["id"]
    blocos = _ler_blocos(
        cliente, f"/research/{rid}/eventos", headers={"Last-Event-ID": str(segundo_id)}, limite_blocos=2
    )
    primeiro = blocos[0]
    assert primeiro.startswith(f"id: {segundo_id + 1}\n")
    assert primeiro.split("\n")[1] == f"event: {eventos[2]['tipo']}"
    assert "event: snapshot" not in primeiro

    blocos = _ler_blocos(cliente, f"/research/{rid}/events?desde={segundo_id}", limite_blocos=1)
    assert blocos[0].startswith(f"id: {segundo_id + 1}\n")


def test_sse_404_para_run_inexistente(config, repositorio):
    pipeline = Pipeline(
        repositorio, FakeExecutor(responder), config, notificador=lambda *a, **k: None
    )
    cliente = TestClient(create_app(pipeline))
    assert cliente.get("/research/NOPE/eventos").status_code == 404


def test_eventos_carregam_arrays_e_totais_utilizaveis(config, repositorio):
    """fonte/ponto/auditoria/tokens no shape que a UI consome (sem dupla contagem)."""
    pipeline = Pipeline(
        repositorio, FakeExecutor(responder), config, notificador=lambda *a, **k: None
    )
    rid = pipeline.criar(
        requisicao(profundidade=1, veracidade_alvo=0, max_rodadas_auditoria=1)
    )
    pipeline.executar(rid)

    eventos = {e["tipo"]: [] for e in repositorio.listar_eventos(rid)}
    for e in repositorio.listar_eventos(rid):
        eventos[e["tipo"]].append(e["payload"])

    fonte = eventos["fonte.lida"][0]
    assert isinstance(fonte["urls_lidas"], list) and fonte["urls_lidas"]
    assert isinstance(fonte["urls_usadas"], list) and fonte["urls_usadas"]

    coletado = eventos["ponto.coletado"][0]
    assert isinstance(coletado["urls_usadas"], list) and coletado["urls_usadas"]
    assert isinstance(coletado["urls_lidas"], list) and coletado["urls_lidas"]
    assert set(coletado["urls_usadas"]) <= set(coletado["urls_lidas"])
    assert coletado["personas"] and set(coletado["personas"]) <= set(PERSONAS)

    auditoria = eventos["auditoria.executada"][0]
    assert sorted(auditoria["perguntas_respondidas"], key=int) == [str(i) for i in range(1, 13)]
    assert auditoria["model_used"]
    assert auditoria["total_tokens"] > 0

    deltas = [e["tokens_execucao"] for e in eventos["tokens.atualizados"]]
    assert deltas and all(d > 0 for d in deltas)
    somas = [e["total_tokens"] for e in eventos["tokens.atualizados"]]
    assert somas == sorted(somas)  # cumulativo monotônico
    assert somas[-1] == sum(deltas)  # sem dupla contagem
    por_papel = eventos["tokens.atualizados"][-1]["tokens_por_papel"]
    assert sum(por_papel.values()) == somas[-1]


def test_auditor_todo_false_vai_ao_redator_com_12_nao_concluidas(config, repositorio):
    def tudo_false(papel, payload):
        if papel == "auditor":
            return {"perguntas_respondidas": {str(i): False for i in range(1, 13)}}
        return responder(papel, payload)

    engine = FakeExecutor(tudo_false)
    pipeline = Pipeline(repositorio, engine, config, notificador=lambda *a, **k: None)
    rid = pipeline.criar(requisicao(profundidade=1, max_rodadas_auditoria=1))
    pipeline.executar(rid)

    assert repositorio.obter_run(rid)["status"] == "COMPLETED"
    redator = engine.payloads("redator")[0]
    assert sorted(redator["perguntas_nao_concluidas"], key=int) == [str(i) for i in range(1, 13)]
    tipos = [e["tipo"] for e in repositorio.listar_eventos(rid)]
    assert "auditoria.executada" in tipos and "run.concluido" in tipos


def test_ponto_zero_personas_em_run_multiplo_conclui_com_falhos(config, repositorio):
    """Ponto 2 sem coleta, ponto 1 saudável → COMPLETED com pontos_falhos=[2]."""
    def sem_ponto_2(papel, payload):
        if papel in PERSONAS and payload.get("ponto_id") == 2:
            raise RuntimeError("persona caiu")
        return responder(papel, payload)

    webhooks: list[tuple[str, dict]] = []
    pipeline = Pipeline(
        repositorio,
        FakeExecutor(sem_ponto_2),
        config,
        notificador=lambda u, p, timeout_s: webhooks.append((u, p)),
    )
    rid = pipeline.criar(requisicao(profundidade=2, veracidade_alvo=0, max_rodadas_auditoria=1))
    pipeline.executar(rid)

    run = repositorio.obter_run(rid)
    assert run["status"] == "COMPLETED"
    assert "## 1." in run["relatorio_final_consolidado"]
    assert "Ponto incompleto" in run["relatorio_final_consolidado"]
    assert webhooks and [f["ponto_id"] for f in webhooks[0][1]["pontos_falhos"]] == [2]
    tipos = [e["tipo"] for e in repositorio.listar_eventos(rid)]
    assert "ponto.erro" in tipos and "ponto.finalizado" in tipos


def test_run_todo_sem_coleta_marca_failed(config, repositorio):
    """Nenhum ponto redigiu → FAILED (run inteiro falhou) + evento run.falhou."""
    def sem_tudo(papel, payload):
        if papel in PERSONAS:
            raise RuntimeError("sem engine")
        return responder(papel, payload)

    pipeline = Pipeline(
        repositorio, FakeExecutor(sem_tudo), config, notificador=lambda *a, **k: None
    )
    rid = pipeline.criar(requisicao(profundidade=1, max_rodadas_auditoria=1))
    with pytest.raises(ValueError, match="nenhum ponto com relatório"):
        pipeline.executar(rid)
    assert repositorio.obter_run(rid)["status"] == "FAILED"
    tipos = [e["tipo"] for e in repositorio.listar_eventos(rid)]
    assert "ponto.erro" in tipos and "run.falhou" in tipos
