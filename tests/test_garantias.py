"""Garantias da spec v1.2: payload completo, blacklist programática, citação restrita e model_used."""

from __future__ import annotations

import pytest

from conftest import FakeExecutor
from contracts import ResearchRequest
from hydrator import SOULS
from orchestrator import Pipeline

URL_FIXA = "https://fonte.test/mesma-url"


def responder(papel: str, payload: dict, *_, **__):
    if papel == "planner":
        ponto = {
            "ponto_id": 1,
            "enunciado": "Ponto 1",
            "subperguntas": ["a", "b", "c"],
            "hipoteses": ["h1", "h2", "h3"],
            "lacunas_iniciais": ["l1", "l2", "l3"],
            "perguntas_auditoria": {str(i): f"criterio {i}" for i in range(1, 13)},
        }
        return {"pontos": [ponto]}
    if papel in ("historiador", "cetico", "visionario", "futurista"):
        return {
            "informacao_coletada": f"{papel} rodada {payload['rodada']} ({URL_FIXA})",
            "urls_usadas": [URL_FIXA],
            "urls_lidas": [URL_FIXA],
        }
    if papel == "auditor":
        respostas = {str(i): True for i in range(1, 13)}
        if payload["tentativa_atual"] == 1:
            respostas["8"] = False
        return {"perguntas_respondidas": respostas}
    if papel == "redator":
        if payload["ponto_id"] == 1 and not getattr(responder, "ja_corrigiu", False):
            responder.ja_corrigiu = True
            return {
                "relatorio_ponto": "relatorio com fonte inventada https://inventada.test/x",
                "lacunas_identificadas": "nenhuma",
                "urls_citadas": [URL_FIXA],
            }
        return {
            "relatorio_ponto": f"relatorio final citando {URL_FIXA}",
            "lacunas_identificadas": "nenhuma",
            "urls_citadas": [URL_FIXA],
        }
    raise AssertionError(f"papel inesperado: {papel}")


@pytest.fixture
def pipeline(config, repositorio):
    responder.ja_corrigiu = False
    executor = FakeExecutor(responder)
    pipeline = Pipeline(repositorio, executor, config, notificador=lambda *a, **k: None)
    pipeline.executor_fake = executor
    return pipeline


def _executar(pipeline) -> str:
    research_id = pipeline.criar(
        ResearchRequest(
            tema="tema de teste",
            profundidade=1,
            veracidade_alvo=90,
            max_rodadas_auditoria=4,
            atualidade="24H",
            callback_url="https://webhook.example/cb",
        )
    )
    pipeline.executar(research_id)
    return research_id


def test_payloads_carregam_atualidade_e_lacunas(pipeline):
    _executar(pipeline)
    executor: FakeExecutor = pipeline.executor_fake

    buscador = executor.payloads("historiador")[0]
    assert buscador["atualidade"] == "24H"
    assert buscador["lacunas_iniciais"] == ["l1", "l2", "l3"]
    auditor_payload = executor.payloads("auditor")[0]
    assert auditor_payload["atualidade"] == "24H"
    assert SOULS["planner"].startswith("Você é o planner. Faça a varredura exploratória")


def test_blacklist_remove_url_repetida_entre_rodadas(pipeline, repositorio):
    research_id = _executar(pipeline)

    execucoes = repositorio.obter_execucoes(research_id, ponto_id=1)
    rodada_1 = [
        url
        for execucao in execucoes
        if execucao["rodada"] == 1
        and execucao["agent_role"] in ("historiador", "cetico", "visionario", "futurista")
        for url in execucao["urls_lidas"]
    ]
    rodada_2 = [
        url
        for execucao in execucoes
        if execucao["rodada"] == 2
        and execucao["agent_role"] in ("historiador", "cetico", "visionario", "futurista")
        for url in execucao["urls_lidas"]
    ]
    assert rodada_1 == [URL_FIXA] * 4
    assert rodada_2 == []
    assert repositorio.urls_lidas(research_id, 1) == [URL_FIXA]


def test_redator_rejeita_url_fora_das_usadas(pipeline, repositorio):
    research_id = _executar(pipeline)

    redatores = [
        execucao
        for execucao in repositorio.obter_execucoes(research_id, ponto_id=1)
        if execucao["agent_role"] == "redator"
    ]
    assert len(redatores) == 2
    assert "inventada.test" in redatores[0]["raw_output_payload"]["relatorio_ponto"]
    assert "inventada" not in redatores[1]["raw_output_payload"]["relatorio_ponto"]
    assert "urls_usadas_acumuladas" in redatores[1]["input_prompt_payload"]

    run = repositorio.obter_run(research_id)
    assert "inventada" not in run["relatorio_final_consolidado"]


def test_model_used_persistido_por_papel(pipeline, repositorio):
    research_id = _executar(pipeline)

    execucoes = repositorio.obter_execucoes(research_id)
    assert execucoes
    assert all(execucao["model_used"] for execucao in execucoes)
    assert {execucao["model_used"] for execucao in execucoes} == {
        f"fake/{papel}"
        for papel in ("planner", "historiador", "cetico", "visionario", "futurista", "auditor", "redator")
    }


def test_tokens_do_delegador_entram_como_orquestrador(config, repositorio):
    from engine import AgentCall

    class ExecutorComPai(FakeExecutor):
        def executar(self, workspace, tarefas):
            saidas = super().executar(workspace, tarefas)
            saidas["__orquestrador__"] = AgentCall(
                dados={},
                prompt_tokens=10,
                completion_tokens=5,
                reasoning_tokens=1,
                total_tokens=16,
                model_used="fake/delegador",
            )
            return saidas

    responder.ja_corrigiu = False
    pipeline = Pipeline(
        repositorio, ExecutorComPai(responder), config, notificador=lambda *a, **k: None
    )
    research_id = _executar(pipeline)

    orquestradores = [
        execucao
        for execucao in repositorio.obter_execucoes(research_id)
        if execucao["agent_role"] == "orquestrador"
    ]
    assert orquestradores
    assert all(execucao["total_tokens"] == 16 for execucao in orquestradores)
    assert all(execucao["model_used"] == "fake/delegador" for execucao in orquestradores)
    run = repositorio.obter_run(research_id)
    assert run["total_tokens"] >= 16 * len(orquestradores)
