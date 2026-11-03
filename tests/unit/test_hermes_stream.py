"""Ponte SSE do workspace Hermes: eventos canônicos publicados a partir dos arquivos."""

import pytest

from app.core import hermes_ids
from app.core.hermes_stream import WatchHermes
from app.core.pipeline_runner import get_pipeline_event_hub

import json

CRITERIOS = [
    {"id": i, "nome": f"criterio_{i}", "aprovado": i <= 10, "justificativa": "ok" if i <= 10 else "falhou"}
    for i in range(1, 13)
]

PLAN = json.dumps({
    "pedido_original": "tema de teste",
    "pedido_normalizado": "escopo de teste",
    "publico": "técnico",
    "formato_entrega": "relatório",
    "recorte_temporal": None,
    "data_referencia": "2026-11-03",
    "politica_recencia": "auto",
    "pressupostos": [],
    "ambiguidades": [],
    "pergunta_de_esclarecimento": None,
    "eixos": [
        {
            "pergunta_principal": "Pergunta do eixo de teste?",
            "subperguntas": ["sub 1"],
            "hipoteses": ["hipótese 1"],
            "consultas_iniciais": ["consulta 1"],
            "fontes_primarias_desejadas": ["fonte 1"],
            "riscos_de_vies": ["viés 1"],
            "evidencias_que_refutariam": ["evidência 1"],
            "criterio_de_conclusao": "conclusão observável",
            "investigabilidade": "fonte pública",
            "eixo_essencial": True,
        }
    ],
    "personas": {"historiador": "a", "visionario": "b", "cetico": "c", "futurista": "d"},
}, ensure_ascii=False)

SEARCH = json.dumps({
    "persona": "historiador",
    "tentativas": [{
        "rodada": 1,
        "consultas": ["consulta"],
        "analise": "achado em https://exemplo.test/a",
        "lacunas": [],
        "urls_lidas": ["https://exemplo.test/a"],
        "urls_fonte": ["https://exemplo.test/a"],
        "paginas_lidas": 3,
    }],
})

AUDITORIA = json.dumps({
    "rodadas": [{
        "rodada": 1,
        "veredito": "REPROVADO",
        "nota": 10,
        "criterios": CRITERIOS,
        "lacunas": "Faltou recência.",
    }]
})

DOSSIE = json.dumps({"dossier_final": "# Dossiê\n\nConteúdo final.\n"})


def _eventos(id_pesquisa):
    return [nome for nome, _ in get_pipeline_event_hub().get_history(id_pesquisa)]


@pytest.fixture()
def workspace(tmp_path):
    return tmp_path


def test_publica_ciclo_completo(workspace):
    pid = "teste-stream-completo"
    hermes_ids.registrar(pid, [f"{pid}-ponto1"])
    w = WatchHermes(pid, workspace)
    hub = get_pipeline_event_hub()
    hub.clear(pid)

    (workspace / "PLAN.json").write_text(PLAN, encoding="utf-8")
    w._tick()
    (workspace / "HISTORIADOR_SEARCH.json").write_text(SEARCH, encoding="utf-8")
    w._tick()
    (workspace / "AUDITORIA.json").write_text(AUDITORIA, encoding="utf-8")
    w._tick()
    (workspace / "DOSSIE.json").write_text(DOSSIE, encoding="utf-8")
    w._tick()
    w.consolidar(sucesso=True)

    eventos = _eventos(pid)
    for esperado in ("stage.start", "agent.delta", "search.progress", "audit.result", "point.status"):
        assert esperado in eventos, f"{esperado} ausente em {set(eventos)}"

    historico = dict(get_pipeline_event_hub().get_history(pid))
    assert historico["audit.result"]["status"] == "reprovado"
    assert historico["audit.result"]["criterios_aprovados"] == 10
    assert historico["search.progress"]["urls_lidas"] == 3
    assert historico["report.final"]["total_caracteres"] == len(json.loads(DOSSIE)["dossier_final"])
    assert historico["pipeline.status"]["status_pipeline"] == "concluido"
    assert historico["audit.result"]["ponto_id"] == f"{pid}-ponto1"
    assert "search.progress" in eventos and historico["search.progress"]["ponto_id"] == f"{pid}-ponto1"


def test_sem_dossie_marca_falha(workspace):
    pid = "teste-stream-falha"
    hermes_ids.registrar(pid, [f"{pid}-ponto1"])
    hub = get_pipeline_event_hub()
    hub.clear(pid)
    w = WatchHermes(pid, workspace)
    (workspace / "PLAN.json").write_text(PLAN, encoding="utf-8")
    w._tick()
    w.consolidar(sucesso=False)

    eventos = dict(get_pipeline_event_hub().get_history(pid))
    assert eventos["pipeline.status"]["status_pipeline"] == "falha"
    assert "report.final" not in eventos
