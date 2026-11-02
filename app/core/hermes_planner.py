"""Pesquisa executada por um perfil Hermes em vez de chamadas diretas ao modelo.

Um único processo `HERMES_PROFILE=deep-research hermes -z <prompt>` roda o ciclo
inteiro: plano, 4 searchers, auditor (até 3 reprovações) e redator. A troca entre
papéis é por arquivos Markdown dentro do diretório isolado da pesquisa — não há
JSON de etapa para etapa.

Contrato de arquivos no diretório da pesquisa:
    PLAN.md                       (planner, reescrevível)
    HISTORIADOR_SEARCH.md         (append-only)
    VISIONARIO_SEARCH.md          (append-only)
    CETICO_SEARCH.md              (append-only)
    FUTURISTA_SEARCH.md           (append-only)
    AUDITORIA.md                  (append-only, 1 seção por rodada)
    DOSSIE.md                     (redator, final)

ponytail: append-only é garantido por instrução no SOUL do perfil; se precisar de
garantia física, montar cada arquivo com `chattr +a` ou rodar o subagente em sandbox
com sistema de arquivos somente-acréscimo.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional

PERSONAS: Dict[str, str] = {
    "historiador": "HISTORIADOR_SEARCH.md",
    "visionario": "VISIONARIO_SEARCH.md",
    "cetico": "CETICO_SEARCH.md",
    "futurista": "FUTURISTA_SEARCH.md",
}

ARQUIVOS_OBRIGATORIOS = ["PLAN.md", *PERSONAS.values(), "AUDITORIA.md", "DOSSIE.md"]


def _raiz_pesquisas() -> Path:
    """Diretório raiz das pesquisas Hermes (default: <repo>/data/pesquisas)."""
    configurado = os.environ.get("DR_HERMES_PESQUISAS_DIR")
    if configurado:
        return Path(configurado).expanduser().resolve()
    return (Path(__file__).resolve().parents[2] / "data" / "pesquisas").resolve()


def _slug(tema: str, limite: int = 60) -> str:
    normalizado = unicodedata.normalize("NFKD", tema).encode("ascii", "ignore").decode()
    normalizado = re.sub(r"[^a-zA-Z0-9]+", "-", normalizado).strip("-").lower()
    return (normalizado[:limite].rstrip("-") or "pesquisa")


def _ajustar_dono(caminho: Path) -> None:
    """Entrega o workspace ao uid que roda o Hermes embutido na imagem.

    A API costuma rodar como root; o Hermes pode rodar como outro usuário e precisa
    gravar nos mesmos arquivos. Sem `DR_HERMES_RUNAS_UID` nada muda.
    """
    bruto = (os.environ.get("DR_HERMES_RUNAS_UID") or "").strip()
    if not bruto or os.geteuid() != 0:
        return
    try:
        uid = int(bruto)
        gid = int(os.environ.get("DR_HERMES_RUNAS_GID") or uid)
    except ValueError:
        return
    for alvo in [caminho, *caminho.rglob("*")]:
        try:
            os.chown(alvo, uid, gid)
        except OSError:
            pass


def criar_workspace(pesquisa_id: str, tema: str) -> Path:
    """Cria (ou reabre) o diretório isolado de uma pesquisa."""
    destino = _raiz_pesquisas() / f"{_slug(tema)}-{pesquisa_id[:8]}"
    destino.mkdir(parents=True, exist_ok=True)
    _ajustar_dono(destino)
    return destino


def _binario_hermes() -> str:
    caminho = os.environ.get("DR_HERMES_BIN") or shutil.which("hermes")
    if not caminho:
        raise FileNotFoundError(
            "Binário `hermes` não encontrado no PATH. Defina DR_HERMES_BIN ou instale o Hermes Agent."
        )
    return caminho


def montar_prompt(tema: str, workspace: Path, max_rodadas: int = 3) -> str:
    """Prompt do turno. O protocolo completo vive no SOUL do perfil planner."""
    return (
        f"Tema da pesquisa: {tema}\n"
        f"Diretório de trabalho: {workspace}\n"
        f"Máximo de reprovações do auditor: {max_rodadas}\n\n"
        "Execute o protocolo completo descrito no seu SOUL e responda apenas "
        "`OK <caminho absoluto do DOSSIE.md>`."
    )


def _conta_rodadas_auditoria(workspace: Path) -> int:
    auditoria = workspace / "AUDITORIA.md"
    if not auditoria.exists():
        return 0
    texto = auditoria.read_text(encoding="utf-8", errors="replace")
    return len(re.findall(r"^##\s+Rodada\s+\d+", texto, flags=re.MULTILINE))


def _inventario(workspace: Path) -> Dict[str, int]:
    return {
        nome: (workspace / nome).stat().st_size
        for nome in ARQUIVOS_OBRIGATORIOS
        if (workspace / nome).exists()
    }


_EXTRATOR_URL = re.compile(r'https?://[^\s)\]>"]+')


def _urls(texto: str) -> set[str]:
    return {u.rstrip(".,;)]") for u in _EXTRATOR_URL.findall(texto)}


def _urls_fora_do_acervo(workspace: Path) -> list[str]:
    """URLs citadas no dossiê que nenhum searcher registrou no acervo.

    Não corrige nem remove: sinaliza, porque reescrever saída de agente por regex
    esconde o problema em vez de expor.
    """
    dossie = workspace / "DOSSIE.md"
    if not dossie.exists():
        return []
    acervo: set[str] = set()
    for nome in PERSONAS.values():
        arquivo = workspace / nome
        if arquivo.exists():
            acervo |= _urls(arquivo.read_text(encoding="utf-8", errors="replace"))
    return sorted(_urls(dossie.read_text(encoding="utf-8", errors="replace")) - acervo)



def _mapear(caminho: Path) -> str:
    """Traduz o caminho local para o caminho visto pelo processo Hermes.

    `DR_HERMES_PATH_MAP="origem=destino[,origem=destino]"` cobre o caso em que a API
    roda em container e o Hermes roda em outro (host ou container vizinho), como na
    hermes-vps: /app/data=... → /opt/data/projects/deep-research/Deep-Research/data.
    Sem a variável, o caminho passa intacto.
    """
    bruto = (os.environ.get("DR_HERMES_PATH_MAP") or "").strip()
    if not bruto:
        return str(caminho)
    texto = str(caminho)
    for par in bruto.split(","):
        if "=" not in par:
            continue
        origem, destino = (p.strip().rstrip("/") for p in par.split("=", 1))
        if texto == origem or texto.startswith(origem + "/"):
            return destino + texto[len(origem):]
    return texto


async def executar(
    tema: str,
    pesquisa_id: str,
    *,
    perfil: Optional[str] = None,
    max_rodadas: int = 3,
    timeout_segundos: int = 3600,
) -> Dict[str, Any]:
    """Roda a pesquisa inteira em um processo Hermes e devolve o inventário final."""
    perfil = perfil or os.environ.get("DR_HERMES_PROFILE", "deep-research")
    if max_rodadas < 1 or max_rodadas > 3:
        raise ValueError("max_rodadas deve estar entre 1 e 3")

    workspace = criar_workspace(pesquisa_id, tema)
    caminho_exec = _mapear(workspace)
    prompt = montar_prompt(tema, Path(caminho_exec), max_rodadas)
    (workspace / "TEMA.md").write_text(
        f"# Tema\n\n{tema}\n\n## Prompt do turno\n\n```\n{prompt}\n```\n", encoding="utf-8"
    )

    argv = [
        _binario_hermes(),
        "-z", prompt,
        "--usage-file", f"{caminho_exec}/usage.json",
    ]
    # HERMES_HOME (perfil embutido na imagem) é herdado; só a sessão do processo pai é descartada.
    env = {k: v for k, v in os.environ.items() if k != "HERMES_SESSION_ID"}
    env["HERMES_PROFILE"] = perfil
    env["HERMES_DR_ALLOWED_PATH"] = caminho_exec
    env["DR_ALLOWED_PATH"] = caminho_exec
    env["DR_HERMES_EXEC_CWD"] = caminho_exec
    log_path = workspace / "hermes.log"
    inicio = time.monotonic()

    with log_path.open("wb") as log:
        processo = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workspace),
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=log,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            codigo = await asyncio.wait_for(processo.wait(), timeout=timeout_segundos)
            erro = None
        except asyncio.TimeoutError:
            processo.kill()
            await processo.wait()
            codigo = -1
            erro = f"tempo esgotado após {timeout_segundos}s"

    duracao = round(time.monotonic() - inicio, 1)
    dossie = workspace / "DOSSIE.md"
    inventario = _inventario(workspace)
    concluido = bool(inventario.get("DOSSIE.md"))

    usage: Optional[Dict[str, Any]] = None
    if (workspace / "usage.json").exists():
        try:
            usage = json.loads((workspace / "usage.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            usage = None

    return {
        "pesquisa_id": pesquisa_id,
        "diretorio": str(workspace),
        "status": "concluido" if concluido and codigo == 0 else "falha",
        "dossie": str(dossie) if concluido else None,
        "arquivos": inventario,
        "rodadas_auditoria": _conta_rodadas_auditoria(workspace),
        "urls_fora_do_acervo": _urls_fora_do_acervo(workspace),
        "duracao_segundos": duracao,
        "exit_code": codigo,
        "erro": erro if erro else (None if codigo == 0 else f"hermes saiu com código {codigo}"),
        "usage": usage,
    }
