"""Ponte SSE entre o workspace de uma pesquisa e o hub de eventos.

O perfil Hermes roda como um único processo e não conhece o contrato SSE da UI.
Este módulo observa os arquivos Markdown enquanto crescem e publica os eventos
canônicos (`stage.start`, `agent.delta`, `search.progress`, `audit.result`,
`writer.progress`, `point.status`, `pipeline.status`) no `PipelineEventHub`.

Contrato de arquivos: ver `hermes_planner` e o addendum v10.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Dict, Optional

from app.core.hermes_ids import ponto_de, pontos_de
from app.core.pipeline_runner import get_pipeline_event_hub
from app.core.urls import sanitizar_url_fonte

PERSONAS = {
    "historiador": "HISTORIADOR_SEARCH.json",
    "visionario": "VISIONARIO_SEARCH.json",
    "cetico": "CETICO_SEARCH.json",
    "futurista": "FUTURISTA_SEARCH.json",
}

PLANO = "PLAN.json"
AUDITORIA = "AUDITORIA.json"
DOSSIE = "DOSSIE.json"


class _Delegacao:
    """Traduz os logs dos subagentes em atividade visível por persona.

    Os 4 searchers só escrevem o `*_SEARCH.json` no fim; sem isso a UI fica minutos
    sem sinal de vida. Lemos os logs de delegação e publicamos um delta curto por
    ferramenta executada.
    """

    def __init__(self, dono: "WatchHermes") -> None:
        self.dono = dono
        self.dir: Optional[Path] = None
        self.offsets: dict[str, int] = {}

    def _raiz(self) -> Optional[Path]:
        """Delegação da pesquisa atual — nunca a pasta global de outra execução."""
        candidatos = []
        isolado = os.environ.get("DR_HERMES_DELEGATION_DIR")
        if isolado:
            candidatos.append(Path(isolado))
        base_local = self.dono.ws / ".hermes" / "cache" / "delegation" / "live"
        candidatos.append(base_local)
        home = os.environ.get("HERMES_HOME")
        perfil = os.environ.get("HERMES_PROFILE", "deep-research")
        if home:
            candidatos.append(
                Path(home) / "profiles" / perfil / "cache" / "delegation" / "live"
            )
        raiz_ws = self.dono.ws.resolve()
        for base in candidatos:
            try:
                if not base.exists():
                    continue
                if not base.resolve().is_relative_to(raiz_ws):
                    continue
            except OSError:
                continue
            dirs = sorted((d for d in base.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)
            if dirs:
                return dirs[-1]
        return None

    def bombear(self) -> None:
        """Publica atividade dos subagentes — só quando a fase ainda é de busca.

        Delegar durante `auditando`/`redigindo` (auditor, redator) não pode
        reabrir `stage.start` das personas: era o "AO VIVO" falso aos 18m49s.
        """
        if self.dono.status in ("auditando", "redigindo", "concluido", "falha"):
            return
        atual = self._raiz()
        if atual is None:
            return
        if atual != self.dir:
            self.dir = atual
            self.offsets.clear()
            for persona in PERSONAS:
                self.dono._inicia("search", persona)
            self.dono._status("buscando")
        for indice, persona in enumerate(PERSONAS):
            log = atual / f"task-{indice}.log"
            if not log.exists():
                continue
            tamanho = log.stat().st_size
            anterior = self.offsets.get(log.name, 0)
            if tamanho <= anterior:
                continue
            with log.open("rb") as fh:
                fh.seek(anterior)
                bruto = fh.read(min(tamanho - anterior, 20000))
            self.offsets[log.name] = anterior + len(bruto)
            texto = bruto.decode("utf-8", errors="replace")
            resumo = _resumo_atividade(texto)
            if resumo:
                self.dono._pub("agent.delta", stage="search", agent=persona, kind="reasoning", text=resumo)


def _resumo_atividade(texto: str) -> Optional[str]:
    """Extrai um sinal curto (url/ferramenta) do log do subagente.

    O log é stdout bruto (HTML/JSON escapado): a URL só entra depois de validada,
    senão o feed publica `https://^` e `.../relatorio\\nAirbnb`.
    """
    urls = [u for u in re.findall(r"https?://[^\s\"')\]]+", texto) if sanitizar_url_fonte(u)]
    if urls:
        # Uma linha por leitura: o renderer é Markdown, então linha solta viraria
        # parágrafo colado ("lendo a. lendo b"). Item de lista mantém uma por linha.
        return f"- lendo {urls[-1][:200]}\n"
    ferramentas = re.findall(r"\"tool\": \"([a-zA-Z_]+)\"", texto)
    if ferramentas:
        return f"- usando {ferramentas[-1]}\n"
    return None


def _parecer_markdown(rodada: dict) -> str:
    """Parecer legível da rodada — nunca o JSON bruto no acordeão do Auditor."""
    criterios = rodada.get("criterios") or []
    aprovados = sum(1 for c in criterios if c.get("aprovado"))
    veredito = str(rodada.get("veredito") or "EM ANÁLISE").upper()
    linhas = [f"**Rodada {rodada.get('rodada') or 1}** — {veredito} · {aprovados}/{len(criterios) or 12} critérios", ""]
    for c in criterios:
        marca = "✓" if c.get("aprovado") else "✗"
        nome = f" {c['nome']}" if c.get("nome") else ""
        linhas.append(f"- {marca} **Critério {c.get('id')}{nome}:** {c.get('justificativa') or ''}")
    if rodada.get("lacunas"):
        linhas += ["", f"**Lacunas:** {rodada['lacunas']}"]
    return "\n".join(linhas)


def _parecer_auditoria(workspace: Path) -> Optional[str]:
    try:
        dados = json.loads((workspace / "AUDITORIA.json").read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    rodadas = dados.get("rodadas") or []
    return _parecer_markdown(rodadas[-1]) if rodadas else None


class _Arquivo:
    __slots__ = ("offset", "texto")

    def __init__(self) -> None:
        self.offset = 0
        self.texto = ""


class WatchHermes:
    """Observa o workspace e publica deltas até ser cancelado."""

    def __init__(self, id_pesquisa: str, workspace: Path, intervalo: float = 2.0) -> None:
        self.id = id_pesquisa
        self.ws = workspace
        self.intervalo = intervalo
        self.hub = get_pipeline_event_hub()
        self.arquivos: Dict[str, _Arquivo] = {}
        self.estagios: set[str] = set()
        self.status = "planejado"
        self.personas_iniciadas: set[str] = set()
        self.personas_fechadas: set[str] = set()
        self.rodadas: set[int] = set()
        self.pendentes: list[tuple[str, dict]] = []
        self.delegacao = _Delegacao(self)

    # ----- publicação -----------------------------------------------------
    def _pub(self, evento: str, **dados) -> None:
        ponto = ponto_de(self.id)
        if ponto == self.id and dados.get("stage") != "plan":
            # O plano ainda não virou registro no banco: segura eventos por ponto para não
            # criar card fantasma na UI com o id da pesquisa no lugar do ponto.
            self.pendentes.append((evento, dados))
            return
        if "ponto_id" in dados or dados.get("stage") == "plan":
            dados.setdefault("ponto_id", ponto)
            self.hub.publish(self.id, evento, {"id_pesquisa": self.id, **dados})
            return
        # Evento de ponto: replica para cada ponto do plano (mesmo ciclo cobre todos).
        for indice, ponto_id in enumerate(pontos_de(self.id), start=1):
            corpo = {**dados, "ponto_id": ponto_id, "ponto_n": indice}
            self.hub.publish(self.id, evento, {"id_pesquisa": self.id, **corpo})

    def _status(self, novo: str) -> None:
        if novo == self.status:
            return
        self.status = novo
        self._pub("pipeline.status", status_pipeline=novo)

    def _inicia(self, estagio: str, agent: Optional[str] = None) -> None:
        chave = f"{estagio}:{agent or ''}"
        if chave in self.estagios:
            return
        self.estagios.add(chave)
        self._pub("stage.start", stage=estagio, agent=agent)

    def _encerra(self, estagio: str, agent: Optional[str] = None) -> None:
        chave = f"{estagio}:{agent or ''}"
        if chave not in self.estagios:
            return
        self.estagios.discard(chave)
        self._pub("stage.end", stage=estagio, agent=agent)

    # ----- leitura incremental -------------------------------------------
    def _novo(self, nome: str) -> str:
        est = self.arquivos.setdefault(nome, _Arquivo())
        caminho = self.ws / nome
        try:
            tamanho = caminho.stat().st_size
        except OSError:
            return ""
        if tamanho <= est.offset:
            return ""
        with caminho.open("rb") as fh:
            fh.seek(est.offset)
            bruto = fh.read(tamanho - est.offset)
        est.offset = tamanho
        trecho = bruto.decode("utf-8", errors="replace")
        est.texto += trecho
        return trecho

    # ----- ciclo ----------------------------------------------------------
    async def rodar(self) -> None:
        while True:
            try:
                self._tick()
            except Exception:  # observador nunca derruba a pesquisa
                pass
            await asyncio.sleep(self.intervalo)

    def _json(self, nome: str) -> Optional[dict]:
        """Lê o artefato JSON já gravado; arquivo em escrita ou torto devolve None."""
        try:
            return json.loads((self.ws / nome).read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return None

    def _tick(self) -> None:
        self.delegacao.bombear()
        while self.pendentes and ponto_de(self.id) != self.id:
            evento, dados = self.pendentes.pop(0)
            for indice, ponto_id in enumerate(pontos_de(self.id), start=1):
                corpo = {**dados, "ponto_id": ponto_id, "ponto_n": indice}
                self.hub.publish(self.id, evento, {"id_pesquisa": self.id, **corpo})

        delta_plano = self._novo(PLANO)
        if delta_plano:
            self._inicia("plan", "planejador")
            self._status("planejado")

        for persona, nome in PERSONAS.items():
            delta = self._novo(nome)
            if not delta:
                continue
            self._status("buscando")
            self._inicia("search", persona)
            tentativas = (self._json(nome) or {}).get("tentativas") or []
            if tentativas:
                self.personas_fechadas.add(persona)
                self._pub(
                    "search.progress",
                    persona=persona,
                    queries_executadas=sum(len(t.get("consultas") or []) for t in tentativas),
                    urls_lidas=sum(int(t.get("paginas_lidas") or 0) for t in tentativas),
                    falha_coleta=not any(t.get("urls_fonte") for t in tentativas),
                    reasoning_coleta=None,
                )

        delta_aud = self._novo(AUDITORIA)
        if delta_aud:
            self._status("auditando")
            self._inicia("audit", "auditor")
            parecer = _parecer_auditoria(self.ws)
            if parecer:
                self._pub("agent.delta", stage="audit", agent="auditor", kind="reasoning", text=parecer)
            for rodada in (self._json(AUDITORIA) or {}).get("rodadas") or []:
                numero = int(rodada.get("rodada") or 0)
                if not numero or numero in self.rodadas:
                    continue
                self.rodadas.add(numero)
                veredito = str(rodada.get("veredito") or "").upper()
                nota = int(rodada.get("nota") or 0)
                self._pub(
                    "audit.result",
                    ponto_n=1,
                    status="aprovado" if veredito == "APROVADO" else "reprovado",
                    pontuacao_percentual=round(nota / 12 * 100, 2),
                    criterios_aprovados=nota,
                    reasoning_auditoria=_parecer_markdown(rodada),
                    pontos_fracos=rodada.get("lacunas"),
                )
                self._pub("point.status", ponto_n=1, status=veredito.lower() or "reprovado", tentativas=numero)

        delta_dos = self._novo(DOSSIE)
        if delta_dos:
            self._status("redigindo")
            self._inicia("writer", "redator")
            texto = (self._json(DOSSIE) or {}).get("dossier_final") or ""
            self._pub("writer.progress", status="redigindo", total_caracteres=len(texto))

    # ----- consolidação final --------------------------------------------
    def consolidar(self, sucesso: bool) -> None:
        """Publica um evento final por agente já concluído (replay para quem chega depois)."""
        for chave in list(self.estagios):
            estagio, _, agent = chave.partition(":")
            self._encerra(estagio, agent or None)
        for persona, nome in PERSONAS.items():
            tentativas = (self._json(nome) or {}).get("tentativas") or []
            if not tentativas:
                continue
            self._pub(
                "search.progress",
                persona=persona,
                queries_executadas=sum(len(t.get("consultas") or []) for t in tentativas),
                urls_lidas=sum(int(t.get("paginas_lidas") or 0) for t in tentativas),
                falha_coleta=not any(t.get("urls_fonte") for t in tentativas),
                reasoning_coleta="\n\n".join(str(t.get("analise") or "") for t in tentativas)[-12000:],
            )
        rodadas = (self._json(AUDITORIA) or {}).get("rodadas") or []
        if rodadas:
            ultima = rodadas[-1]
            veredito = str(ultima.get("veredito") or "").upper()
            nota = int(ultima.get("nota") or 0)
            self._pub(
                "audit.result",
                ponto_n=1,
                status="aprovado" if veredito == "APROVADO" else "reprovado",
                pontuacao_percentual=round(nota / 12 * 100, 2),
                criterios_aprovados=nota,
                reasoning_auditoria=_parecer_markdown(ultima),
                pontos_fracos=ultima.get("lacunas"),
            )
        dossie = (self._json(DOSSIE) or {}).get("dossier_final") or ""
        if dossie:
            self._pub("writer.progress", status="concluido", total_caracteres=len(dossie))
            self._status("concluido")
            self._pub("report.final", status="concluido", dossier_final=dossie,
                      total_caracteres=len(dossie), concluido_em=None)
        else:
            self._status("concluido" if (sucesso or dossie) else "falha")


async def acompanhar(id_pesquisa: str, workspace: Path, parar: asyncio.Event) -> None:
    """Observa o workspace até `parar` ser setado."""
    watcher = WatchHermes(id_pesquisa, workspace)
    tarefa = asyncio.create_task(watcher.rodar())
    try:
        await parar.wait()
    finally:
        tarefa.cancel()
        try:
            await tarefa
        except (asyncio.CancelledError, Exception):
            pass
        watcher._tick()
        watcher.consolidar(sucesso=bool((watcher._json(DOSSIE) or {}).get("dossier_final")))
