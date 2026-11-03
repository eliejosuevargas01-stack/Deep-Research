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


_EXECUCOES: Dict[str, "Execucao"] = {}


class Execucao:
    """Um ciclo Hermes em andamento (ou concluído) para uma pesquisa."""

    def __init__(self, pesquisa_id: str, workspace: Path, processo, parar: asyncio.Event,
                 observador: "asyncio.Task", inicio: float, timeout: int) -> None:
        self.pesquisa_id = pesquisa_id
        self.workspace = workspace
        self.processo = processo
        self.parar = parar
        self.observador = observador
        self.inicio = inicio
        self.timeout = timeout
        self.codigo: Optional[int] = None
        self.erro: Optional[str] = None
        self.resultado: Optional[Dict[str, Any]] = None
        self.tarefa: Optional["asyncio.Task"] = None

    async def aguardar(self) -> Dict[str, Any]:
        """Bloqueia até o processo Hermes terminar e devolve o inventário final."""
        if self.tarefa is not None:
            await self.tarefa
        return self.resultado or {}

    async def aguardar_arquivo(self, nome: str, timeout: float) -> bool:
        """Espera o arquivo existir e parar de crescer por 2s (ou o ciclo terminar)."""
        limite = time.monotonic() + timeout
        anterior = -1
        while time.monotonic() < limite:
            alvo = self.workspace / nome
            tamanho = alvo.stat().st_size if alvo.exists() else 0
            if tamanho and tamanho == anterior:
                return True
            anterior = tamanho
            if self.tarefa is not None and self.tarefa.done():
                return (self.workspace / nome).exists()
            await asyncio.sleep(2.0)
        return (self.workspace / nome).exists()


async def _ciclo(ex: Execucao) -> None:
    try:
        try:
            ex.codigo = await asyncio.wait_for(ex.processo.wait(), timeout=ex.timeout)
        except asyncio.TimeoutError:
            ex.processo.kill()
            await ex.processo.wait()
            ex.codigo = -1
            ex.erro = f"tempo esgotado após {ex.timeout}s"
    finally:
        ex.parar.set()
        await ex.observador

    workspace = ex.workspace
    duracao = round(time.monotonic() - ex.inicio, 1)
    dossie = workspace / "DOSSIE.md"
    inventario = _inventario(workspace)
    concluido = bool(inventario.get("DOSSIE.md"))

    usage: Optional[Dict[str, Any]] = None
    if (workspace / "usage.json").exists():
        try:
            usage = json.loads((workspace / "usage.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            usage = None

    ex.resultado = {
        "pesquisa_id": ex.pesquisa_id,
        "diretorio": str(workspace),
        "status": "concluido" if concluido and ex.codigo == 0 else "falha",
        "dossie": str(dossie) if concluido else None,
        "arquivos": inventario,
        "rodadas_auditoria": _conta_rodadas_auditoria(workspace),
        "urls_fora_do_acervo": _urls_fora_do_acervo(workspace),
        "duracao_segundos": duracao,
        "exit_code": ex.codigo,
        "erro": ex.erro if ex.erro else (None if ex.codigo == 0 else f"hermes saiu com código {ex.codigo}"),
        "usage": usage,
    }


async def iniciar(
    tema: str,
    pesquisa_id: str,
    *,
    perfil: Optional[str] = None,
    max_rodadas: Optional[int] = None,
    timeout_segundos: Optional[int] = None,
) -> Execucao:
    """Dispara o perfil Hermes e volta assim que o processo existe (sem esperar o ciclo)."""
    perfil = perfil or os.environ.get("DR_HERMES_PROFILE", "deep-research")
    if max_rodadas is None:
        max_rodadas = int(os.environ.get("DR_MAX_RODADAS", "3"))
    if max_rodadas < 1 or max_rodadas > 3:
        raise ValueError("max_rodadas deve estar entre 1 e 3")
    if timeout_segundos is None:
        timeout_segundos = int(os.environ.get("DR_HERMES_TIMEOUT", "3600"))

    workspace = criar_workspace(pesquisa_id, tema)
    caminho_exec = _mapear(workspace)
    prompt = montar_prompt(tema, Path(caminho_exec), max_rodadas)
    (workspace / "TEMA.md").write_text(
        f"# Tema\n\n{tema}\n\n## Prompt do turno\n\n```\n{prompt}\n```\n", encoding="utf-8"
    )

    argv = [
        _binario_hermes(),
        "-p", perfil,
        "-z", prompt,
        "--usage-file", f"{caminho_exec}/usage.json",
    ]
    env = {k: v for k, v in os.environ.items() if k != "HERMES_SESSION_ID"}
    env["HERMES_PROFILE"] = perfil
    env["HERMES_DR_ALLOWED_PATH"] = caminho_exec
    env["DR_ALLOWED_PATH"] = caminho_exec
    env["DR_HERMES_EXEC_CWD"] = caminho_exec

    from app.core import hermes_stream

    parar = asyncio.Event()
    observador = asyncio.create_task(hermes_stream.acompanhar(pesquisa_id, workspace, parar))
    with (workspace / "hermes.log").open("wb") as log:
        processo = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workspace),
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=log,
            stderr=asyncio.subprocess.STDOUT,
        )
    ex = Execucao(pesquisa_id, workspace, processo, parar, observador, time.monotonic(), timeout_segundos)
    ex.tarefa = asyncio.create_task(_ciclo(ex))
    _EXECUCOES[pesquisa_id] = ex
    return ex


def execucao_existente(pesquisa_id: str) -> Optional["Execucao"]:
    return _EXECUCOES.get(pesquisa_id)


async def obter_ou_iniciar(tema: str, pesquisa_id: str) -> "Execucao":
    """Retoma o ciclo em memória; se o processo morreu com o servidor, começa de novo."""
    ex = _EXECUCOES.get(pesquisa_id)
    if ex is not None and (ex.tarefa is None or not ex.tarefa.done()):
        return ex
    return await iniciar(tema, pesquisa_id)


async def executar(
    tema: str,
    pesquisa_id: str,
    *,
    perfil: Optional[str] = None,
    max_rodadas: Optional[int] = None,
    timeout_segundos: Optional[int] = None,
) -> Dict[str, Any]:
    """Roda a pesquisa inteira e devolve o inventário final (usado por CLI/testes)."""
    ex = await iniciar(
        tema,
        pesquisa_id,
        perfil=perfil,
        max_rodadas=max_rodadas,
        timeout_segundos=timeout_segundos,
    )
    return await ex.aguardar()
