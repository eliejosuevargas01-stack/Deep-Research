"""Regressões de latência (51min -> ~10): coerção, toolset por papel, fonte.lida viva.

Sem docker, sem LLM: tudo estático/host.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from conftest import FakeExecutor
from contracts import BuscadorSaida, RedatorSaida
from engine import Tarefa
from orchestrator import Pipeline
from service import PedidoRun, _montar_comando


def test_redator_aceita_lista_real_de_lacunas():
    # Payload real do run 83590D40C3F4007A: lacunas_identificadas veio como LISTA.
    lacunas = [
        "Faltou apurar a pergunta 8: números divergentes sem metodologia.",
        "  ",
        "Faltou delimitar a janela de atualidade da pergunta 10.",
    ]
    saida = RedatorSaida.model_validate(
        {
            "relatorio_ponto": "relatorio final do ponto",
            "lacunas_identificadas": lacunas,
            "urls_citadas": [],
        }
    )
    assert "Faltou apurar a pergunta 8" in saida.lacunas_identificadas
    assert "Faltou delimitar" in saida.lacunas_identificadas
    assert "\n- " in saida.lacunas_identificadas


def test_redator_e_buscador_coagem_lista_em_texto():
    saida = RedatorSaida.model_validate(
        {
            "relatorio_ponto": ["parte 1", "", "parte 2"],
            "lacunas_identificadas": [],
            "urls_citadas": [],
        }
    )
    assert saida.relatorio_ponto == "parte 1\n- parte 2"
    assert saida.lacunas_identificadas == ""

    busca = BuscadorSaida.model_validate(
        {
            "informacao_coletada": ["fato a", "fato b"],
            "urls_usadas": [],
            "urls_lidas": [],
        }
    )
    assert busca.informacao_coletada == "fato a\n- fato b"


def test_comando_engine_inclui_t_clarify_quando_toolsets():
    pedido = PedidoRun(workspace="/workspaces/x", instrucao="faca", toolsets=["clarify"])
    comando = _montar_comando(pedido, Path("/workspaces/x"))
    assert comando[-2:] == ["-t", "clarify"]


def test_comando_engine_sem_t_quando_none():
    pedido = PedidoRun(workspace="/workspaces/x", instrucao="faca")
    comando = _montar_comando(pedido, Path("/workspaces/x"))
    assert "-t" not in comando


def test_runner_envia_toolsets_no_post_run(config, tmp_path, monkeypatch):
    import httpx as _httpx

    from hermes_runner import HermesRunner

    config.pipeline.engine_url = "http://engine:8090"
    visto: dict = {}

    def _handler(requisicao: _httpx.Request) -> _httpx.Response:
        visto["json"] = json.loads(requisicao.content.decode())
        return _httpx.Response(200, json={"ok": True})

    transporte = _httpx.MockTransport(_handler)
    _RealClient = _httpx.Client
    monkeypatch.setattr(
        _httpx, "Client", lambda *a, **k: _RealClient(transport=transporte, timeout=k.get("timeout"))
    )
    runner = HermesRunner(config)
    erro = runner._acionar(tmp_path / "ws", "z", ["clarify"])
    assert erro == ""
    assert visto["json"]["toolsets"] == ["clarify"]

    # None some do corpo (backend não impõe toolset).
    visto.clear()
    erro = runner._acionar(tmp_path / "ws", "z", None)
    assert erro == ""
    assert "toolsets" not in visto["json"]


def test_toolsets_por_papel_no_pipeline(config, repositorio):
    from test_pipeline import pipeline as _fabrica, responder  # noqa: F401 (fixture local)

    engine = FakeExecutor(responder)
    pipe = Pipeline(repositorio, engine, config, notificador=lambda *a, **k: None)
    vistos: dict[str, tuple[str, ...] | None] = {}
    original = engine._chamar

    def _espiao(workspace, tarefa: Tarefa):
        vistos[tarefa.id] = tarefa.toolsets
        return original(workspace, tarefa)

    engine._chamar = _espiao  # type: ignore[method-assign]
    from contracts import ResearchRequest

    rid = pipe.criar(
        ResearchRequest(
            tema="tema teste latencia",
            profundidade=1,
            veracidade_alvo=50,
            max_rodadas_auditoria=1,
            atualidade="ALL",
            callback_url="https://webhook.example/cb",
        )
    )
    pipe.executar(rid)
    # Filhos herdam o toolset do pai menos os bloqueados: `file` é obrigatório para
    # escrever saidas/<id>.json; `delegation` é o que permite ao orquestrador delegar.
    assert vistos["planner"] == ("web", "file")
    coleta = [v for k, v in vistos.items() if k.startswith("historiador_p1")]
    assert coleta and all(v == ("web", "file", "delegation") for v in coleta)
    assert vistos.get("auditor_p1_r1") == ("file", "delegation")
    assert vistos.get("redator_p1") == ("file", "delegation")


def test_fonte_viva_emite_durante_coleta_sem_duplicar(config, repositorio, tmp_path):
    """Executor cria saidas/<id>.json com atraso; fonte.lida sai antes do fim do lote."""
    from contracts import ResearchRequest
    from test_pipeline import responder

    workspace = tmp_path / "ws"
    saidas = workspace / "saidas"
    saidas.mkdir(parents=True)

    class ExecutorLento(FakeExecutor):
        def executar(self, workspace, tarefas):
            chamadas = {}
            for tarefa in tarefas:
                (workspace / "saidas").mkdir(parents=True, exist_ok=True)
                (workspace / "saidas" / f"{tarefa.id}.json").write_text(
                    json.dumps(
                        {
                            "informacao_coletada": f"coleta {tarefa.id}",
                            "urls_usadas": [f"https://vivo.test/{tarefa.id}"],
                            "urls_lidas": [f"https://vivo.test/{tarefa.id}"],
                        }
                    ),
                    encoding="utf-8",
                )
                if tarefa.id == tarefas[0].id:
                    time.sleep(4)  # > poll de 2s: observador pega ainda no lote
                chamadas[tarefa.id] = self._chamar(workspace, tarefa)
            return chamadas

    engine = ExecutorLento(responder)
    pipe = Pipeline(repositorio, engine, config, notificador=lambda *a, **k: None)
    rid = pipe.criar(
        ResearchRequest(
            tema="tema vivo",
            profundidade=1,
            veracidade_alvo=100,
            max_rodadas_auditoria=1,
            atualidade="ALL",
            callback_url="https://webhook.example/cb",
        )
    )
    pipe.executar(rid)
    eventos = repositorio.listar_eventos(rid, limite=500)
    fontes = [e for e in eventos if e["tipo"] == "fonte.lida"]
    vivas = [e for e in fontes if "vivo.test" in json.dumps(e["payload"])]
    assert vivas, "observador não emitiu fonte.lida durante a coleta"
    # Sem duplicata: cada persona emite uma vez (vivo ou final).
    def _chave(e):
        p = e["payload"]
        p = json.loads(p) if isinstance(p, str) else p
        return (p["persona"], p["rodada"])

    chaves = [_chave(e) for e in fontes]
    assert len(chaves) == len(set(chaves))


def test_redator_aceita_aliases():
    saida = RedatorSaida.model_validate(
        {
            "relatorio": "Texto analítico em relatorio",
            "lacunas": "Resumo de lacunas em lacunas",
            "fontes": ["https://fonte.test/1"],
        }
    )
    assert saida.relatorio_ponto == "Texto analítico em relatorio"
    assert saida.lacunas_identificadas == "Resumo de lacunas em lacunas"
    assert saida.urls_citadas == ["https://fonte.test/1"]


def test_validador_redator_aceita_variacoes_canonicas(config, repositorio):
    from orchestrator import Pipeline
    import pytest

    pipe = Pipeline(repositorio, None, config)
    validador = pipe._validador_redator(["https://epe.gov.br/ben/"])

    # Variações canônicas (www., sem barra, maiúsculas) devem passar
    saida = validador(
        {
            "relatorio_ponto": "Relatório citando https://www.epe.gov.br/ben",
            "lacunas_identificadas": "Nenhuma lacuna",
            "urls_citadas": ["https://EPE.gov.br/ben/"],
        }
    )
    assert saida.relatorio_ponto

    # URL realmente inventada deve falhar
    with pytest.raises(ValueError, match="URLs fora de urls_usadas_acumuladas"):
        validador(
            {
                "relatorio_ponto": "Relatório citando https://inventada.test/x",
                "lacunas_identificadas": "Nenhuma lacuna",
                "urls_citadas": [],
            }
        )

