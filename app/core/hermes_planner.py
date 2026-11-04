"""Pesquisa executada por um perfil Hermes em vez de chamadas diretas ao modelo.

Um único processo `HERMES_PROFILE=deep-research hermes -z <prompt>` roda o ciclo
inteiro: plano, 4 searchers, auditor (até 3 reprovações) e redator. A troca entre
papéis é por artefatos JSON no diretório isolado da pesquisa; o backend valida cada
artefato e persiste no banco.

Contrato de arquivos no diretório da pesquisa (`app/schemas/artefatos.py`):
    PLAN.json                     planner   contrato DR-006 + personas
    HISTORIADOR_SEARCH.json       searcher  tentativas da persona
    VISIONARIO_SEARCH.json        searcher
    CETICO_SEARCH.json            searcher
    FUTURISTA_SEARCH.json         searcher
    AUDITORIA.json                auditor   rodadas com os 12 critérios
    DOSSIE.json                   redator   dossiê final + fontes

ponytail: o searcher reescreve o próprio JSON ao acrescentar tentativa; concorrência
entre personas não existe porque cada uma tem arquivo próprio (auditor é escritor
único de AUDITORIA.json).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

PERSONAS: Dict[str, str] = {
    "historiador": "HISTORIADOR_SEARCH.json",
    "visionario": "VISIONARIO_SEARCH.json",
    "cetico": "CETICO_SEARCH.json",
    "futurista": "FUTURISTA_SEARCH.json",
}

ARQUIVOS_OBRIGATORIOS = [
    "PLAN.json",
    *PERSONAS.values(),
    "AUDITORIA.json",
    "DOSSIE.json",
]


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


_ID_COM_SUFIXO = re.compile(r"^plan-\d+-(?P<cauda>[0-9a-f]{8,})$")


def sufixo_workspace(pesquisa_id: str) -> str:
    """Sufixo estável e único do workspace para um id de pesquisa.

    `plan-<timestamp>-<aleatório>`: usa a cauda aleatória. `pesquisa_id[:8]`
    pegava `plan-179`, constante por ~11 dias, e duas pesquisas do mesmo tema
    caíam na mesma pasta (dossiê e usage.json de outra execução).
    Ids sem esse formato mantêm os 8 primeiros caracteres (contrato antigo).
    """
    achado = _ID_COM_SUFIXO.match(pesquisa_id or "")
    if achado:
        return achado.group("cauda")[:8]
    limpo = re.sub(r"[^a-zA-Z0-9]", "", pesquisa_id or "")
    if len(limpo) >= 8:
        return limpo[:8]
    return hashlib.sha256((pesquisa_id or "pesquisa").encode("utf-8")).hexdigest()[:8]


def caminho_workspace(pesquisa_id: str, tema: str) -> Path:
    """Caminho determinístico do workspace de uma pesquisa."""
    return _raiz_pesquisas() / f"{_slug(tema)}-{sufixo_workspace(pesquisa_id)}"


def criar_workspace(pesquisa_id: str, tema: str) -> Path:
    """Cria (ou reabre) o diretório isolado de uma pesquisa."""
    destino = caminho_workspace(pesquisa_id, tema)
    destino.mkdir(parents=True, exist_ok=True)
    marca = destino / ".pesquisa_id"
    if marca.exists():
        dono = marca.read_text(encoding="utf-8", errors="replace").strip()
        if dono and dono != pesquisa_id:
            # Nunca herda artefatos de outra execução: colisão de nome vira pasta nova.
            destino = destino.with_name(f"{destino.name}-{uuid.uuid4().hex[:4]}")
            destino.mkdir(parents=True, exist_ok=True)
            marca = destino / ".pesquisa_id"
    marca.write_text(pesquisa_id, encoding="utf-8")
    _ajustar_dono(destino)
    return destino


def _binario_hermes() -> str:
    caminho = os.environ.get("DR_HERMES_BIN") or shutil.which("hermes")
    if not caminho:
        raise FileNotFoundError(
            "Binário `hermes` não encontrado no PATH. Defina DR_HERMES_BIN ou instale o Hermes Agent."
        )
    return caminho


def montar_prompt(tema: str, workspace: Path, max_rodadas: int = 3, n_pontos: int = 1) -> str:
    """Prompt do turno. O protocolo completo vive no SOUL do perfil planner."""
    return (
        f"Tema da pesquisa: {tema}\n"
        f"Diretório de trabalho: {workspace}\n"
        f"Máximo de reprovações do auditor: {max_rodadas}\n"
        f"Pontos analíticos (perguntas) do plano: exatamente {n_pontos}\n\n"
        "Regras de isolamento (inquebráveis): trabalhe exclusivamente dentro de "
        f"{workspace}. Não leia, não escreva e não cite nada de `..`, `/` ou de "
        "qualquer outro diretório de pesquisa em workspaces/.\n"
        "Execute o protocolo completo descrito no seu SOUL e responda apenas "
        "`OK <caminho absoluto do DOSSIE.json>`."
    )


def _json_do_workspace(workspace: Path, nome: str) -> Optional[dict]:
    """Lê um artefato JSON do workspace; ausente ou torto devolve None."""
    alvo = workspace / nome
    if not alvo.exists():
        return None
    try:
        return json.loads(alvo.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return None


def _conta_rodadas_auditoria(workspace: Path) -> int:
    dados = _json_do_workspace(workspace, "AUDITORIA.json") or {}
    rodadas = dados.get("rodadas")
    return len(rodadas) if isinstance(rodadas, list) else 0


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
    dossie = _json_do_workspace(workspace, "DOSSIE.json")
    if not dossie:
        return []
    acervo: set[str] = set()
    for nome in PERSONAS.values():
        dados = _json_do_workspace(workspace, nome) or {}
        for tentativa in dados.get("tentativas") or []:
            acervo |= {str(u).rstrip(".,;)]") for u in (tentativa.get("urls_lidas") or [])}
            acervo |= {str(u).rstrip(".,;)]") for u in (tentativa.get("urls_fonte") or [])}
    citadas = _urls(str(dossie.get("dossier_final") or ""))
    return sorted(citadas - acervo)



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
    dossie = workspace / "DOSSIE.json"
    inventario = _inventario(workspace)
    concluido = bool(inventario.get("DOSSIE.json"))

    usage: Optional[Dict[str, Any]] = None
    if (workspace / "usage.json").exists():
        try:
            usage = json.loads((workspace / "usage.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            usage = None
    from app.core import usage as usage_mod

    resumo_usage = usage_mod.gravar_resumo(workspace)
    # Sem usage.json, o acumulado dos `usage_<etapa>.json` responde pelos tokens.
    usage = usage or resumo_usage["total"] or None

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
        "usage": {**usage, "resumo": resumo_usage} if usage else resumo_usage,
    }

    from app.core.hermes_adapter import persistir_ciclo

    await persistir_ciclo(ex.pesquisa_id, workspace)


def _hermes_home_isolado(workspace: Path, perfil: str) -> Dict[str, str]:
    """`HERMES_HOME` dentro do workspace da pesquisa.

    Sessões e logs de delegação (`cache/delegation/live`) passam a viver na pasta
    desta execução: nenhuma pesquisa lê a delegação de outra.
    """
    if os.environ.get("DR_HERMES_HOME_ISOLADO", "0") != "1":
        # Desligado por padrão: o processo Hermes mantém o home do perfil (contrato
        # testado). O watcher já só lê a delegação dentro desta pesquisa.
        return {}
    origem = os.environ.get("HERMES_HOME")
    if not origem:
        return {}
    try:
        home = workspace / ".hermes"
        perfis = home / "profiles"
        perfis.mkdir(parents=True, exist_ok=True)
        alvo = perfis / perfil
        base = Path(origem) / "profiles" / perfil
        if not alvo.exists() and base.exists():
            alvo.symlink_to(base, target_is_directory=True)
        return {"HERMES_HOME": _mapear(home)}
    except OSError:
        return {}


async def iniciar(
    tema: str,
    pesquisa_id: str,
    *,
    perfil: Optional[str] = None,
    max_rodadas: Optional[int] = None,
    n_pontos: int = 1,
    timeout_segundos: Optional[int] = None,
    etapa: Optional[str] = None,
    ponto: int = 1,
    rodada: int = 1,
) -> Execucao:
    """Dispara o perfil Hermes e volta assim que o processo existe (sem esperar o ciclo).

    `etapa` decide o `--usage-file`: cada invocação grava o próprio arquivo
    (`usage_plan.json`, `usage_search_ponto_1.json`, ...) em vez de sobrescrever
    o mesmo `usage.json`. Sem etapa, mantém o contrato antigo de um arquivo só.
    """
    perfil = perfil or os.environ.get("DR_HERMES_PROFILE", "deep-research")
    etapa = etapa or os.environ.get("DR_HERMES_ETAPA") or None
    if max_rodadas is None:
        max_rodadas = int(os.environ.get("DR_MAX_RODADAS", "3"))
    if max_rodadas < 1 or max_rodadas > 3:
        raise ValueError("max_rodadas deve estar entre 1 e 3")
    if timeout_segundos is None:
        timeout_segundos = int(os.environ.get("DR_HERMES_TIMEOUT", "3600"))

    workspace = criar_workspace(pesquisa_id, tema)
    caminho_exec = _mapear(workspace)
    from app.core import hermes_config, usage as usage_mod

    config_modelos = hermes_config.carregar()
    (workspace / "MODELS.json").write_text(
        json.dumps(hermes_config.modelos_por_papel(config_modelos), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    hermes_config.sincronizar_perfil(config_modelos, perfil)
    prompt = montar_prompt(tema, Path(caminho_exec), max_rodadas, n_pontos)
    prompt += hermes_config.instrucao_modelos(config_modelos)
    (workspace / "TEMA.md").write_text(
        f"# Tema\n\n{tema}\n\n## Prompt do turno\n\n```\n{prompt}\n```\n", encoding="utf-8"
    )

    argv = [
        _binario_hermes(),
        "-p", perfil,
        "-z", prompt,
        "--usage-file", f"{caminho_exec}/{usage_mod.nome_arquivo_uso(etapa, ponto, rodada)}",
    ]
    modelo_planejador = config_modelos.get("modelo_planejador") or config_modelos.get("modelo_padrao")
    if modelo_planejador:
        argv += ["-m", modelo_planejador]
    config_hermes = config_modelos
    env = {k: v for k, v in os.environ.items() if k != "HERMES_SESSION_ID"}
    env.update(hermes_config.env_hermes(config_hermes))
    env["HERMES_PROFILE"] = perfil
    env["HERMES_DR_ALLOWED_PATH"] = caminho_exec
    env["DR_ALLOWED_PATH"] = caminho_exec
    env["DR_HERMES_EXEC_CWD"] = caminho_exec
    env["DR_MODELOS_FILE"] = f"{caminho_exec}/MODELS.json"
    env.update(_hermes_home_isolado(workspace, perfil))

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


async def obter_ou_iniciar(tema: str, pesquisa_id: str, n_pontos: int = 1) -> "Execucao":
    """Retoma o ciclo em memória; se o processo morreu com o servidor, começa de novo."""
    ex = _EXECUCOES.get(pesquisa_id)
    if ex is not None and (ex.tarefa is None or not ex.tarefa.done()):
        return ex
    return await iniciar(tema, pesquisa_id, n_pontos=n_pontos)


async def executar(
    tema: str,
    pesquisa_id: str,
    *,
    perfil: Optional[str] = None,
    max_rodadas: Optional[int] = None,
    n_pontos: int = 1,
    timeout_segundos: Optional[int] = None,
    etapa: Optional[str] = None,
    ponto: int = 1,
    rodada: int = 1,
) -> Dict[str, Any]:
    """Roda a pesquisa inteira e devolve o inventário final (usado por CLI/testes)."""
    ex = await iniciar(
        tema,
        pesquisa_id,
        perfil=perfil,
        max_rodadas=max_rodadas,
        n_pontos=n_pontos,
        timeout_segundos=timeout_segundos,
        etapa=etapa,
        ponto=ponto,
        rodada=rodada,
    )
    return await ex.aguardar()
