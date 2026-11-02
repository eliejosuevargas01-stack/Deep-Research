"""Invocação do processo Hermes: perfil por env, sem `-p` e sem bwrap por default."""

import pytest

from app.core import hermes_planner


class _Proc:
    def __init__(self, code: int = 0) -> None:
        self.returncode = code

    async def wait(self) -> int:
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9


@pytest.mark.asyncio
async def test_executar_invoca_hermes_com_perfil_por_env(tmp_path, monkeypatch):
    capturado = {}

    async def fake_exec(*argv, **kwargs):
        capturado["argv"] = argv
        capturado["env"] = kwargs["env"]
        capturado["cwd"] = kwargs["cwd"]
        return _Proc()

    monkeypatch.setattr(hermes_planner.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setenv("DR_HERMES_PESQUISAS_DIR", str(tmp_path))
    monkeypatch.setenv("DR_HERMES_BIN", "/usr/local/bin/hermes")
    monkeypatch.setenv("HERMES_HOME", "/app/hermes-home")
    monkeypatch.delenv("DR_HERMES_SANDBOX", raising=False)
    monkeypatch.delenv("DR_HERMES_PROFILE", raising=False)

    resultado = await hermes_planner.executar("Computação quântica", "abcd1234efgh")

    argv = list(capturado["argv"])
    workspace = tmp_path / "computacao-quantica-abcd1234"
    assert argv[0] == "/usr/local/bin/hermes"
    assert "-p" not in argv
    assert argv[1:3] == ["-z", argv[2]]
    assert argv[3] == "--usage-file"
    assert argv[4] == f"{workspace}/usage.json"
    assert not any("bwrap" in parte for parte in argv[:2])
    assert capturado["env"]["HERMES_PROFILE"] == "deep-research"
    assert capturado["env"]["HERMES_HOME"] == "/app/hermes-home"
    assert capturado["cwd"] == str(workspace)
    assert resultado["status"] == "falha"  # sem DOSSIE.md, mesmo com exit 0


@pytest.mark.asyncio
async def test_executar_respeita_dr_hermes_profile(tmp_path, monkeypatch):
    capturado = {}

    async def fake_exec(*argv, **kwargs):
        capturado["env"] = kwargs["env"]
        return _Proc()

    monkeypatch.setattr(hermes_planner.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setenv("DR_HERMES_PESQUISAS_DIR", str(tmp_path))
    monkeypatch.setenv("DR_HERMES_BIN", "/usr/local/bin/hermes")
    monkeypatch.setenv("DR_HERMES_PROFILE", "deep-research-custom")

    await hermes_planner.executar("Tema qualquer", "abcd1234efgh")

    assert capturado["env"]["HERMES_PROFILE"] == "deep-research-custom"
