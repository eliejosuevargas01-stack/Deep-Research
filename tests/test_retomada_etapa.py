"""Se o turno do Hermes morreu, a etapa é retomada em vez de esperar para sempre."""
from pathlib import Path

import pytest

from app.core import hermes_adapter


class ExecucaoFalsa:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.esperou = []

    async def aguardar_arquivo(self, nome, timeout=0.0):
        (self.workspace / nome).write_text("{}", encoding="utf-8")
        self.esperou.append(nome)


@pytest.mark.asyncio
async def test_auditoria_ausente_retoma_etapa_audit(tmp_path, monkeypatch):
    workspace = tmp_path / "pesquisas" / "tema-abc12345"
    workspace.mkdir(parents=True)
    chamadas = []

    async def iniciar_falso(tema, pesquisa_id, *, n_pontos=1, etapa=None, **kwargs):
        chamadas.append((pesquisa_id, etapa))
        return ExecucaoFalsa(workspace)

    monkeypatch.setattr(hermes_adapter.hermes_planner, "iniciar", iniciar_falso)
    monkeypatch.setattr(hermes_adapter.hermes_planner, "execucao_existente", lambda _id: None)
    monkeypatch.setattr(hermes_adapter, "_workspace_exato", lambda _id, _tema: workspace)

    destino = await hermes_adapter.aguardar_arquivo("pesq-1", "AUDITORIA.json", tema="Tema", timeout=1)
    assert destino == workspace
    assert chamadas == [("pesq-1", "audit")]


@pytest.mark.asyncio
async def test_dossie_ausente_retoma_etapa_write(tmp_path, monkeypatch):
    workspace = tmp_path / "pesquisas" / "tema-abc12345"
    workspace.mkdir(parents=True)
    chamadas = []

    async def iniciar_falso(tema, pesquisa_id, *, n_pontos=1, etapa=None, **kwargs):
        chamadas.append(etapa)
        return ExecucaoFalsa(workspace)

    monkeypatch.setattr(hermes_adapter.hermes_planner, "iniciar", iniciar_falso)
    monkeypatch.setattr(hermes_adapter.hermes_planner, "execucao_existente", lambda _id: None)
    monkeypatch.setattr(hermes_adapter, "_workspace_exato", lambda _id, _tema: workspace)

    await hermes_adapter.aguardar_arquivo("pesq-1", "DOSSIE.json", tema="Tema", timeout=1)
    assert chamadas == ["write"]


@pytest.mark.asyncio
async def test_artefato_presente_nao_retoma(tmp_path, monkeypatch):
    workspace = tmp_path / "pesquisas" / "tema-abc12345"
    workspace.mkdir(parents=True)
    (workspace / "AUDITORIA.json").write_text("{}", encoding="utf-8")
    chamadas = []

    async def iniciar_falso(*a, **k):
        chamadas.append(a)
        return ExecucaoFalsa(workspace)

    monkeypatch.setattr(hermes_adapter.hermes_planner, "iniciar", iniciar_falso)
    monkeypatch.setattr(hermes_adapter.hermes_planner, "execucao_existente", lambda _id: None)
    monkeypatch.setattr(hermes_adapter, "_workspace_exato", lambda _id, _tema: workspace)

    assert await hermes_adapter.aguardar_arquivo("pesq-1", "AUDITORIA.json", tema="Tema") == workspace
    assert chamadas == []


@pytest.mark.asyncio
async def test_workspace_ausente_mantem_erro(tmp_path, monkeypatch):
    monkeypatch.setattr(hermes_adapter.hermes_planner, "execucao_existente", lambda _id: None)
    monkeypatch.setattr(hermes_adapter, "_workspace_exato", lambda _id, _tema: tmp_path / "nao-existe")
    with pytest.raises(ValueError):
        await hermes_adapter.aguardar_arquivo("pesq-1", "AUDITORIA.json", tema="Tema")
