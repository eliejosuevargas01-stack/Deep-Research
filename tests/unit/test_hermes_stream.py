"""Ponte SSE do workspace Hermes: eventos canônicos publicados a partir dos arquivos."""

import pytest

from app.core import hermes_ids
from app.core.hermes_stream import WatchHermes
from app.core.pipeline_runner import get_pipeline_event_hub

PLAN = """# Plano
```json
{"versao": "1", "tema": "t", "objetivo": "o", "escopo": "e", "perguntas": ["p"],
 "personas": {"historiador": "a", "visionario": "b", "cetico": "c", "futurista": "d"},
 "criterios_evidencia": ["x"], "criterios_aprovacao": ["y"]}
```
"""

SEARCH = """tentativa 1
## Consultas
- https://exemplo.test/a
TOTAL: 3 páginas
"""

AUDITORIA = """# Auditoria
## Rodada 1 — REPROVADO — nota 10/12
Faltou recência.
"""

DOSSIE = "# Dossiê\n\nConteúdo final.\n"


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

    (workspace / "PLAN.md").write_text(PLAN, encoding="utf-8")
    w._tick()
    (workspace / "HISTORIADOR_SEARCH.md").write_text(SEARCH, encoding="utf-8")
    w._tick()
    (workspace / "AUDITORIA.md").write_text(AUDITORIA, encoding="utf-8")
    w._tick()
    (workspace / "DOSSIE.md").write_text(DOSSIE, encoding="utf-8")
    w._tick()
    w.consolidar(sucesso=True)

    eventos = _eventos(pid)
    for esperado in ("stage.start", "agent.delta", "search.progress", "audit.result", "point.status"):
        assert esperado in eventos, f"{esperado} ausente em {set(eventos)}"

    historico = dict(get_pipeline_event_hub().get_history(pid))
    assert historico["audit.result"]["status"] == "reprovado"
    assert historico["audit.result"]["criterios_aprovados"] == 10
    assert historico["search.progress"]["urls_lidas"] == 3
    assert historico["report.final"]["total_caracteres"] == len(DOSSIE)
    assert historico["pipeline.status"]["status_pipeline"] == "concluido"
    assert historico["audit.result"]["ponto_id"] == f"{pid}-ponto1"
    assert "search.progress" in eventos and historico["search.progress"]["ponto_id"] == f"{pid}-ponto1"


def test_sem_dossie_marca_falha(workspace):
    pid = "teste-stream-falha"
    hermes_ids.registrar(pid, [f"{pid}-ponto1"])
    hub = get_pipeline_event_hub()
    hub.clear(pid)
    w = WatchHermes(pid, workspace)
    (workspace / "PLAN.md").write_text(PLAN, encoding="utf-8")
    w._tick()
    w.consolidar(sucesso=False)

    eventos = dict(get_pipeline_event_hub().get_history(pid))
    assert eventos["pipeline.status"]["status_pipeline"] == "falha"
    assert "report.final" not in eventos
