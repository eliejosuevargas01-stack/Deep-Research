"""Configuração do provedor OpenAI-compatible e do modelo de cada subagente.

O sistema não chama mais nenhum provedor por fora: tudo roda no Hermes. Estas
configurações viram variáveis de ambiente do subprocesso Hermes e um
`MODELS.json` no workspace de cada pesquisa.
"""

from __future__ import annotations

import json
import os
import re
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


def perfil_hermes(perfil: str | None = None) -> Path | None:
    """Diretório do perfil usado pelo subprocesso (`HERMES_HOME/profiles/<perfil>`)."""
    home = os.environ.get("HERMES_HOME")
    if not home:
        return None
    raiz = Path(home).expanduser()
    nome = perfil or os.environ.get("DR_HERMES_PROFILE") or os.environ.get("HERMES_PROFILE") or "deep-research"
    candidato = raiz / "profiles" / nome
    if candidato.is_dir():
        return candidato
    return raiz if (raiz / "SOUL.md").exists() else None


def sincronizar_perfil(dados: Dict[str, str] | None = None, perfil: str | None = None) -> bool:
    """Grava base_url/modelo/chave concretos no config.yaml do perfil Hermes.

    O Hermes 0.22 não expande `${VAR}` no `model:` do perfil; sem isso o processo
    sobe com modelo vazio. Mantém o resto do arquivo (delegação, limites) intacto.
    """
    dados = dados if dados is not None else carregar()
    destino = perfil_hermes(perfil)
    if destino is None:
        return False
    config = destino / "config.yaml"
    try:
        texto = config.read_text(encoding="utf-8")
    except OSError:
        return False

    modelo = modelos_por_papel(dados).get("planejador") or dados.get("modelo_padrao") or ""
    base = dados.get("openai_base_url") or ""
    chave = dados.get("openai_api_key") or ""
    if not (modelo or base or chave):
        return False

    def troca(campo: str, valor: str, atual: str) -> str:
        if not valor:
            return atual
        padrao = re.compile(rf"(?m)^(\s{{2}}{campo}:\s*).*$")
        return padrao.sub(lambda m: m.group(1) + json.dumps(valor), atual, count=1)

    novo = texto
    novo = troca("default", modelo, novo)
    novo = troca("base_url", base, novo)
    novo = troca("api_key", chave, novo)
    if novo == texto:
        return False
    try:
        tmp = config.with_suffix(".yaml.tmp")
        tmp.write_text(novo, encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(config)
    except OSError:
        return False
    return True
