"""Configuração do perfil Hermes (`hermes_home/profiles/deep-research/config.yaml`).

Provedor de LLM vem só do ambiente (`LLM_BASE_URL`, `LLM_API_KEY`); nunca do YAML nem
do `PUT /config`. O backend lê/grava no `config.yaml` do perfil só default_model,
modelos por papel e limites de delegação. Com engine isolado (`DR_ENGINE_URL`), o
engine é o dono do config: `aplicar_config` repassa via `PUT /config` do engine.
`DR_HERMES_PROFILE_DIR` aponta para outro perfil (produção monta o diretório do Hermes).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

RAIZ = Path(__file__).resolve().parent.parent
PAPEIS = (
    "planner",
    "historiador",
    "cetico",
    "visionario",
    "futurista",
    "auditor",
    "redator",
)

MODELO_FORTE_PADRAO = "ocg/deepseek-v4.1-flash"
MODELO_LEVE_PADRAO = "gemini/gemini-3.5-flash-lite"
MODELOS_PADRAO_POR_PAPEL = {
    "planner": MODELO_FORTE_PADRAO,
    "historiador": MODELO_LEVE_PADRAO,
    "cetico": MODELO_LEVE_PADRAO,
    "visionario": MODELO_LEVE_PADRAO,
    "futurista": MODELO_LEVE_PADRAO,
    "auditor": MODELO_FORTE_PADRAO,
    "redator": MODELO_FORTE_PADRAO,
}


def modelo_do_papel(papel: str) -> str:
    """Modelo efetivo do papel.

    `LLM_MODEL_<PAPEL>` vence; planner cai para `LLM_MODEL`; senão o default
    do papel (forte: planner/auditor/redator; leve: buscadores).
    """
    direto = (os.getenv(f"LLM_MODEL_{papel.upper()}") or "").strip()
    if direto:
        return direto
    if papel == "planner":
        return (os.getenv("LLM_MODEL") or "").strip() or MODELO_FORTE_PADRAO
    return MODELOS_PADRAO_POR_PAPEL[papel]


def diretorio_perfil() -> Path:
    return Path(
        os.getenv("DR_HERMES_PROFILE_DIR", RAIZ / "hermes_home" / "profiles" / "deep-research")
    )


def caminho_config() -> Path:
    return diretorio_perfil() / "config.yaml"


class ModelosPorPapel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planner: str | None = None
    historiador: str | None = None
    cetico: str | None = None
    visionario: str | None = None
    futurista: str | None = None
    auditor: str | None = None
    redator: str | None = None


class ConfigHermes(BaseModel):
    """Payload de `PUT /config` (SDD §5.2). Campos omitidos ficam como estão."""

    model_config = ConfigDict(extra="forbid")

    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    max_concurrent_children: int | None = Field(default=None, ge=1)
    max_spawn_depth: int | None = Field(default=None, ge=1)
    oneshot_max_children: int | None = Field(default=None, ge=0)
    modelos_por_papel: ModelosPorPapel | None = None

    @field_validator("base_url", "api_key")
    @classmethod
    def _proibido(cls, valor: str | None) -> str | None:
        if valor is not None and str(valor).strip() != "":
            raise ValueError("provedor vem do ambiente (LLM_BASE_URL/LLM_API_KEY)")
        return valor


def _secao(dados: dict[str, Any], chave: str) -> dict[str, Any]:
    valor = dados.get(chave)
    return valor if isinstance(valor, dict) else {}


def _ler_config_remota() -> dict[str, Any] | None:
    """GET /config do engine quando disponível; None cai no config local."""
    import httpx

    engine_url = (os.getenv("DR_ENGINE_URL") or "").rstrip("/")
    if not engine_url:
        return None
    token = os.getenv("DR_ENGINE_TOKEN") or os.getenv("ENGINE_TOKEN") or ""
    headers = {"X-Engine-Token": token} if token else {}
    try:
        with httpx.Client(timeout=10) as client:
            resposta = client.get(f"{engine_url}/config", headers=headers)
    except Exception:
        return None
    if resposta.status_code != 200:
        return None
    dados = resposta.json()
    return dados if isinstance(dados, dict) else None


def ler_config(caminho: Path | None = None) -> dict[str, Any]:
    caminho = caminho or caminho_config()
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    dados = dados if isinstance(dados, dict) else {}
    modelo = _secao(dados, "model")
    delegacao = _secao(dados, "delegation")
    backends = _secao(delegacao, "backends")
    por_papel = _secao(backends, "por_papel")
    modelos = _secao(por_papel, "modelos")
    padrao = (
        modelo.get("default", "")
        or os.getenv("LLM_MODEL", "")
        or MODELO_FORTE_PADRAO
    )
    return {
        "base_url": os.getenv("LLM_BASE_URL", "") or os.getenv("OPENAI_BASE_URL", ""),
        "api_key": "",
        "default_model": padrao,
        "provider_fonte": "env",
        "max_concurrent_children": delegacao.get("max_concurrent_children", 40),
        "max_spawn_depth": delegacao.get("max_spawn_depth", 2),
        "oneshot_max_children": delegacao.get("oneshot_max_children", 0),
        "modelos_por_papel": {papel: modelos.get(papel, "") for papel in PAPEIS},
    }


def materializar_perfil(caminho: Path | None = None) -> bool:
    """Compat: o provider vem só do ambiente; o YAML nunca guarda segredo.

    Mantida para chamadas legadas: garante `model.provider: env` e remove
    `base_url`/`api_key` caso existam. Retorna True quando gravou algo.
    """
    import re as _re

    caminho = caminho or caminho_config()
    if not caminho.exists():
        return False
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    if not isinstance(dados, dict):
        return False
    modelo = dados.get("model")
    if not isinstance(modelo, dict):
        return False
    mudou = False
    for chave in ("base_url", "api_key"):
        if chave in modelo:
            del modelo[chave]
            mudou = True
    if modelo.get("provider") != "env":
        modelo["provider"] = "env"
        mudou = True
    padrao = _re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
    for chave in ("default",):
        valor = modelo.get(chave)
        if not isinstance(valor, str) or "${" not in valor:
            continue
        novo = padrao.sub(lambda m: os.environ.get(m.group(1), m.group(0)), valor)
        if novo != valor:
            modelo[chave] = novo
            mudou = True
    if not mudou:
        return False
    # ponytail: reescreve o YAML inteiro e perde comentários; usar round-trip ruamel se o
    # arquivo passar a ser editado à mão em produção.
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=caminho.parent, delete=False, suffix=".tmp"
    ) as tmp:
        yaml.safe_dump(dados, tmp, sort_keys=False, allow_unicode=True)
        temporario = Path(tmp.name)
    os.replace(temporario, caminho)
    return True


def aplicar_config(payload: ConfigHermes, caminho: Path | None = None) -> dict[str, Any]:
    """Grava default_model, modelos por papel e limites; nunca segredos.

    Com `DR_ENGINE_URL` configurado, o engine é dono do config: repassa os campos
    permitidos via `PUT /config` do engine e devolve a resposta dele. Sem engine,
    aplica no YAML local (dev/testes).
    """
    # Defesa em profundidade: o validator do pydantic já barra, mas validação
    # direta (sem modelo) não deve gravar segredo silenciosamente.
    for campo in ("base_url", "api_key"):
        valor = getattr(payload, campo, None)
        if valor is not None and str(valor).strip() != "":
            raise ValueError("provedor vem do ambiente (LLM_BASE_URL/LLM_API_KEY)")
    engine_url = (os.getenv("DR_ENGINE_URL") or "").rstrip("/")
    if engine_url:
        return _aplicar_no_engine(engine_url, payload)
    caminho = caminho or caminho_config()
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    dados = dados if isinstance(dados, dict) else {}

    modelo = dados.setdefault("model", {})
    delegacao = dados.setdefault("delegation", {})
    backends = delegacao.setdefault("backends", {})
    por_papel = backends.setdefault("por_papel", {})
    modelos = por_papel.setdefault("modelos", {})

    if payload.base_url is not None or payload.api_key is not None:
        pass  # validado acima: só chega aqui com valores vazios/nulos
    if payload.default_model is not None:
        modelo["default"] = payload.default_model
    if payload.max_concurrent_children is not None:
        delegacao["max_concurrent_children"] = payload.max_concurrent_children
    if payload.max_spawn_depth is not None:
        delegacao["max_spawn_depth"] = payload.max_spawn_depth
    if payload.oneshot_max_children is not None:
        delegacao["oneshot_max_children"] = payload.oneshot_max_children
    # O backend por papel é o contrato da spec; não deixamos o arquivo em outro backend.
    delegacao["backend"] = "por_papel"
    if payload.modelos_por_papel is not None:
        for papel, valor in payload.modelos_por_papel.model_dump(exclude_none=True).items():
            modelos[papel] = valor

    # ponytail: reescreve o YAML inteiro e perde comentários; usar round-trip ruamel se o
    # arquivo passar a ser editado à mão em produção.
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=caminho.parent, delete=False, suffix=".tmp"
    ) as tmp:
        yaml.safe_dump(dados, tmp, sort_keys=False, allow_unicode=True)
        temporario = Path(tmp.name)
    os.replace(temporario, caminho)
    return ler_config(caminho)


def _carga_engine(payload: ConfigHermes) -> dict[str, Any]:
    carga: dict[str, Any] = {}
    if payload.default_model is not None:
        carga["default_model"] = payload.default_model
    for campo in ("max_concurrent_children", "max_spawn_depth", "oneshot_max_children"):
        valor = getattr(payload, campo)
        if valor is not None:
            carga[campo] = valor
    if payload.modelos_por_papel is not None:
        carga["modelos_por_papel"] = payload.modelos_por_papel.model_dump(exclude_none=True)
    return carga


def _aplicar_no_engine(engine_url: str, payload: ConfigHermes) -> dict[str, Any]:
    import httpx  # import local: caminho sem engine segue sem a dependência

    token = os.getenv("DR_ENGINE_TOKEN") or os.getenv("ENGINE_TOKEN") or ""
    headers = {"X-Engine-Token": token} if token else {}
    try:
        with httpx.Client(timeout=30) as client:
            resposta = client.put(f"{engine_url}/config", json=_carga_engine(payload), headers=headers)
    except Exception as exc:
        raise RuntimeError(f"Engine não aplicou config: {exc}") from exc
    if resposta.status_code == 422:
        raise ValueError(resposta.text)
    if resposta.status_code != 200:
        raise RuntimeError(f"Engine falhou ({resposta.status_code}): {resposta.text[:800]}")
    dados = resposta.json()
    return dados if isinstance(dados, dict) else {}
