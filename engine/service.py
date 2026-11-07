"""Serviço interno do engine: executa o Hermes isolado (porta 8100).

Contrato com o backend (`api`):
- `GET /health` (sem auth) -> {"status": "ok", "model": <default>}
- demais rotas exigem `X-Engine-Token: $ENGINE_TOKEN`.
- `POST /run` executa `hermes -p deep-research -z <instrucao>` no workspace.
- `GET /PUT /config` lê/ajusta o config.yaml do perfil (sem segredos).
"""

from __future__ import annotations

import asyncio
import hmac
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml  # venv local / api
except ImportError:  # imagem do engine: só ruamel.yaml existe
    from ruamel.yaml import YAML as _YAML

    class _ShimYaml:
        @staticmethod
        def safe_load(texto):
            return _YAML(typ="safe").load(texto) if texto else None

        @staticmethod
        def safe_dump(dados, fp, **_kw):
            _YAML().dump(dados, fp)

    yaml = _ShimYaml()  # type: ignore[no-redef]

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

PAPEIS = (
    "planner",
    "historiador",
    "cetico",
    "visionario",
    "futurista",
    "auditor",
    "redator",
)

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data"))
CONFIG_PATH = HERMES_HOME / "profiles" / "deep-research" / "config.yaml"
WORKSPACES_DIR = Path(os.environ.get("WORKSPACES_DIR", "/workspaces"))
RUN_TIMEOUT_MAX = 3600
OUTPUT_MAX = 200_000

app = FastAPI(title="deep-research engine", docs_url=None, redoc_url=None)


class ModelosPorPapel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planner: str | None = None
    historiador: str | None = None
    cetico: str | None = None
    visionario: str | None = None
    futurista: str | None = None
    auditor: str | None = None
    redator: str | None = None


class AtualizacaoConfig(BaseModel):
    """Payload de `PUT /config`. base_url/api_key aqui -> 422 (só via env)."""

    model_config = ConfigDict(extra="forbid")

    default_model: str | None = None
    modelos_por_papel: ModelosPorPapel | None = None
    max_concurrent_children: int | None = Field(default=None, ge=1)
    max_spawn_depth: int | None = Field(default=None, ge=1)
    oneshot_max_children: int | None = Field(default=None, ge=0)


class PedidoRun(BaseModel):
    workspace: str
    instrucao: str
    timeout_s: int = 600
    toolsets: list[str] | None = None


def _auth(x_engine_token: str | None = Header(default=None)) -> None:
    esperado = os.environ.get("ENGINE_TOKEN", "")
    if not esperado:
        raise HTTPException(status_code=500, detail="ENGINE_TOKEN não configurado")
    if not x_engine_token or not hmac.compare_digest(x_engine_token, esperado):
        raise HTTPException(status_code=401, detail="token inválido")


AUTENTICADO = Depends(_auth)


def _ler_yaml() -> dict[str, Any]:
    try:
        dados = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _secao(dados: dict[str, Any], chave: str) -> dict[str, Any]:
    valor = dados.get(chave)
    return valor if isinstance(valor, dict) else {}


def _config_publica() -> dict[str, Any]:
    dados = _ler_yaml()
    modelo = _secao(dados, "model")
    delegacao = _secao(dados, "delegation")
    por_papel = _secao(_secao(delegacao, "backends"), "por_papel")
    modelos = _secao(por_papel, "modelos")
    return {
        "base_url": os.environ.get("LLM_BASE_URL", ""),
        "api_key": "",
        "default_model": modelo.get("default", ""),
        "max_concurrent_children": delegacao.get("max_concurrent_children", 40),
        "max_spawn_depth": delegacao.get("max_spawn_depth", 2),
        "oneshot_max_children": delegacao.get("oneshot_max_children", 0),
        "modelos_por_papel": {papel: modelos.get(papel, "") for papel in PAPEIS},
        "provider_fonte": "env",
    }


def _gravar_yaml(dados: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=CONFIG_PATH.parent, delete=False, suffix=".tmp"
    ) as tmp:
        yaml.safe_dump(dados, tmp, sort_keys=False, allow_unicode=True)
        temporario = Path(tmp.name)
    os.replace(temporario, CONFIG_PATH)


def _recarregar_gateway() -> None:
    """`hermes gateway restart` se houver gateway rodando; senão nada."""
    if not shutil.which("hermes"):
        return
    try:
        status = subprocess.run(
            ["hermes", "gateway", "status"], capture_output=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    if status.returncode != 0:
        return
    try:
        subprocess.run(
            ["hermes", "gateway", "restart"], capture_output=True, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _resolver_workspace(caminho: str) -> Path:
    base = WORKSPACES_DIR.resolve()
    alvo = Path(caminho)
    if not alvo.is_absolute():
        alvo = base / alvo
    try:
        if alvo.resolve().is_relative_to(base):
            return alvo.resolve()
    except OSError:
        pass
    raise HTTPException(status_code=403, detail="workspace fora de /workspaces")


def _cortar(texto: str | bytes | None) -> str:
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8", "replace")
    texto = texto or ""
    return texto[-OUTPUT_MAX:]


@app.get("/health")
def saude() -> dict[str, Any]:
    return {"status": "ok", "model": _config_publica()["default_model"]}


@app.get("/config")
def ler_config(_: None = AUTENTICADO) -> dict[str, Any]:
    return _config_publica()


@app.put("/config")
async def gravar_config(payload: AtualizacaoConfig, _: None = AUTENTICADO) -> dict[str, Any]:
    dados = _ler_yaml()
    modelo = dados.setdefault("model", {})
    delegacao = dados.setdefault("delegation", {})
    backends = delegacao.setdefault("backends", {})
    if not isinstance(backends, dict):
        backends = delegacao["backends"] = {}
    por_papel = backends.setdefault("por_papel", {})
    if not isinstance(por_papel, dict):
        por_papel = backends["por_papel"] = {}
    modelos = por_papel.setdefault("modelos", {})
    if not isinstance(modelos, dict):
        modelos = por_papel["modelos"] = {}

    # Provedor vive só em env: nunca persiste base_url/api_key.
    modelo["provider"] = "env"
    modelo.pop("base_url", None)
    modelo.pop("api_key", None)
    if payload.default_model is not None:
        modelo["default"] = payload.default_model
    if payload.max_concurrent_children is not None:
        delegacao["max_concurrent_children"] = payload.max_concurrent_children
    if payload.max_spawn_depth is not None:
        delegacao["max_spawn_depth"] = payload.max_spawn_depth
    if payload.oneshot_max_children is not None:
        delegacao["oneshot_max_children"] = payload.oneshot_max_children
    delegacao["backend"] = "por_papel"
    if payload.modelos_por_papel is not None:
        for papel, valor in payload.modelos_por_papel.model_dump(
            exclude_none=True
        ).items():
            modelos[papel] = valor

    await asyncio.to_thread(_gravar_yaml, dados)
    asyncio.create_task(asyncio.to_thread(_recarregar_gateway))
    return _config_publica()


def _montar_comando(pedido: PedidoRun, workspace: Path) -> list[str]:
    comando = [
        "hermes",
        "-p",
        "deep-research",
        "-z",
        pedido.instrucao,
        "--usage-file",
        str(workspace / "usage.json"),
    ]
    if pedido.toolsets is not None:
        comando += ["-t", ",".join(pedido.toolsets)]
    return comando


@app.post("/run")
async def rodar(pedido: PedidoRun, _: None = AUTENTICADO) -> dict[str, Any]:
    workspace = _resolver_workspace(pedido.workspace)
    timeout = min(max(pedido.timeout_s, 1), RUN_TIMEOUT_MAX)
    workspace.mkdir(parents=True, exist_ok=True)
    comando = _montar_comando(pedido, workspace)
    try:
        processo = await asyncio.to_thread(
            subprocess.run,
            comando,
            cwd=workspace,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "returncode": processo.returncode,
            "stdout": _cortar(processo.stdout),
            "stderr": _cortar(processo.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "stdout": _cortar(exc.stdout),
            "stderr": _cortar(f"{exc.stderr or ''}\nHermes excedeu {timeout}s"),
        }
    except OSError as exc:
        return {"returncode": 127, "stdout": "", "stderr": _cortar(str(exc))}
