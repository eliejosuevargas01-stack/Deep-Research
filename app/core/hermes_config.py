"""Configuração do provedor OpenAI-compatible e do modelo de cada subagente.

O sistema não chama mais nenhum provedor por fora: tudo roda no Hermes. Estas
configurações viram variáveis de ambiente do subprocesso Hermes e um
`MODELS.json` no workspace de cada pesquisa.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

PAPEIS = (
    "planejador",
    "historiador",
    "pragmatico",
    "cetico",
    "visionario",
    "auditor",
    "redator",
)

CAMPOS = (
    "openai_base_url",
    "openai_api_key",
    "modelo_padrao",
    *(f"modelo_{papel}" for papel in PAPEIS),
)

_ENV_PAPEL = {
    "planejador": "DR_MODEL_PLANEJADOR",
    "historiador": "DR_MODEL_HISTORIADOR",
    "pragmatico": "DR_MODEL_PRAGMATICO",
    "cetico": "DR_MODEL_CETICO",
    "visionario": "DR_MODEL_VISIONARIO",
    "auditor": "DR_MODEL_AUDITOR",
    "redator": "DR_MODEL_REDATOR",
}


def caminho() -> Path:
    configurado = os.environ.get("DR_SETTINGS_FILE")
    if configurado:
        return Path(configurado).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "hermes_settings.json"


def carregar() -> Dict[str, str]:
    alvo = caminho()
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {campo: "" for campo in CAMPOS}
    if not isinstance(dados, dict):
        return {campo: "" for campo in CAMPOS}
    return {campo: str(dados.get(campo) or "").strip() for campo in CAMPOS}


def salvar(dados: Dict[str, Any]) -> Dict[str, str]:
    """Mescla o que veio, grava com permissão 0600 e devolve o estado final."""
    atuais = carregar()
    for campo in CAMPOS:
        if campo in dados and dados[campo] is not None:
            atuais[campo] = str(dados[campo]).strip()
    alvo = caminho()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps(atuais, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(alvo, 0o600)
    except OSError:
        pass
    return atuais


def modelos_por_papel(dados: Dict[str, str] | None = None) -> Dict[str, str]:
    dados = dados if dados is not None else carregar()
    padrao = dados.get("modelo_padrao") or ""
    return {papel: (dados.get(f"modelo_{papel}") or padrao) for papel in PAPEIS}


def env_hermes(dados: Dict[str, str] | None = None) -> Dict[str, str]:
    """Variáveis que o subprocesso Hermes recebe: provedor e modelos."""
    dados = dados if dados is not None else carregar()
    env: Dict[str, str] = {}
    base = dados.get("openai_base_url")
    chave = dados.get("openai_api_key")
    if base:
        env["LLM_BASE_URL"] = base
        env["OPENAI_BASE_URL"] = base
    if chave:
        env["OPENAI_API_KEY"] = chave
        env["LLM_API_KEY"] = chave
    for papel, modelo in modelos_por_papel(dados).items():
        if modelo:
            env[_ENV_PAPEL[papel]] = modelo
    principal = modelos_por_papel(dados).get("planejador") or dados.get("modelo_padrao")
    if principal:
        env["LLM_MODEL_STRONG"] = principal
    return env


def instrucao_modelos(dados: Dict[str, str] | None = None) -> str:
    """Linha de prompt com o modelo de cada papel (Hermes herda o do pai)."""
    modelos = modelos_por_papel(dados)
    partes = [f"{papel}={modelo}" for papel, modelo in modelos.items() if modelo]
    if not partes:
        return ""
    return (
        "Modelos por papel (use o indicado ao delegar; o filho herda o modelo do pai "
        f"quando o Hermes não permitir fixar): {', '.join(partes)}.\n"
    )
