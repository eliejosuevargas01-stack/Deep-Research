"""Ponte SSE entre o workspace de uma pesquisa e o hub de eventos.

O perfil Hermes roda como um único processo e não conhece o contrato SSE da UI.
Este módulo observa os arquivos Markdown enquanto crescem e publica os eventos
canônicos (`stage.start`, `agent.delta`, `search.progress`, `audit.result`,
`writer.progress`, `point.status`, `pipeline.status`) no `PipelineEventHub`.

Contrato de arquivos: ver `hermes_planner` e o addendum v10.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Dict, Optional

from app.core.hermes_ids import ponto_de
from app.core.pipeline_runner import get_pipeline_event_hub

PERSONAS = {
    "historiador": "HISTORIADOR_SEARCH.md",
    "visionario": "VISIONARIO_SEARCH.md",
    "cetico": "CETICO_SEARCH.md",
    "futurista": "FUTURISTA_SEARCH.md",
}

_RODADA = re.compile(r"^##\s+Rodada\s+(\d+)\s*[—:-]\s*(APROVADO|REPROVADO)\s*[—:-]\s*nota\s*(\d+)\s*/\s*12", re.M)
_TOTAL = re.compile(r"TOTAL:\s*(\d+)\s*p[áa]ginas", re.I)
_TENTATIVA = re.compile(r"^tentativa\s+(\d+)", re.M | re.I)


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

    # ----- publicação -----------------------------------------------------
    def _pub(self, evento: str, **dados) -> None:
        ponto = ponto_de(self.id)
        dados.setdefault("ponto_id", ponto)
        self.hub.publish(self.id, evento, {"id_pesquisa": self.id, **dados})

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

    def _tick(self) -> None:
        delta_plano = self._novo("PLAN.md")
        if delta_plano:
            self._inicia("plan", "planejador")
            self._pub("agent.delta", stage="plan", agent="planejador", kind="reasoning", text=delta_plano)
            self._status("planejado")

        for persona, nome in PERSONAS.items():
            delta = self._novo(nome)
            if not delta:
                continue
            self._status("buscando")
            self._inicia("search", persona)
            self._pub("agent.delta", stage="search", agent=persona, kind="reasoning", text=delta)
            texto = self.arquivos[nome].texto
            if _TOTAL.search(delta) or _TENTATIVA.search(delta):
                self.personas_fechadas.add(persona)
                self._pub(
                    "search.progress",
                    ponto_id=self.id,
                    persona=persona,
                    queries_executadas=len(_TENTATIVA.findall(texto)) or 1,
                    urls_lidas=sum(int(m) for m in _TOTAL.findall(texto)),
                    falha_coleta=False,
                    reasoning_coleta=None,
                )

        delta_aud = self._novo("AUDITORIA.md")
        if delta_aud:
            self._status("auditando")
            self._inicia("audit", "auditor")
            self._pub("agent.delta", stage="audit", agent="auditor", kind="reasoning", text=delta_aud)
            for numero, veredito, nota in _RODADA.findall(self.arquivos["AUDITORIA.md"].texto):
                n = int(numero)
                if n in self.rodadas:
                    continue
                self.rodadas.add(n)
                self._pub(
                    "audit.result",
                    ponto_id=self.id,
                    ponto_n=1,
                    status="aprovado" if veredito == "APROVADO" else "reprovado",
                    pontuacao_percentual=round(int(nota) / 12 * 100, 2),
                    criterios_aprovados=int(nota),
                    reasoning_auditoria=None,
                    pontos_fracos=None,
                )
                self._pub("point.status", ponto_id=self.id, ponto_n=1, status=veredito.lower(), tentativas=n)

        delta_dos = self._novo("DOSSIE.md")
        if delta_dos:
            self._status("redigindo")
            self._inicia("writer", "redator")
            self._pub("agent.delta", stage="writer", agent="redator", kind="reasoning", text=delta_dos)
            self._pub("writer.progress", status="redigindo", total_caracteres=len(self.arquivos["DOSSIE.md"].texto))

    # ----- consolidação final --------------------------------------------
    def consolidar(self, sucesso: bool) -> None:
        """Publica um evento final por agente já concluído (replay para quem chega depois)."""
        for chave in list(self.estagios):
            estagio, _, agent = chave.partition(":")
            self._encerra(estagio, agent or None)
        for persona, nome in PERSONAS.items():
            texto = self.arquivos.get(nome, _Arquivo()).texto
            if not texto:
                continue
            self._pub(
                "search.progress",
                ponto_id=self.id,
                persona=persona,
                queries_executadas=len(_TENTATIVA.findall(texto)) or 1,
                urls_lidas=sum(int(m) for m in _TOTAL.findall(texto)),
                falha_coleta=False,
                reasoning_coleta=texto[-12000:],
            )
        auditoria = self.arquivos.get("AUDITORIA.md", _Arquivo()).texto
        if auditoria:
            ultima = _RODADA.findall(auditoria)[-1:] or []
            if ultima:
                _, veredito, nota = ultima[0]
                self._pub(
                    "audit.result",
                    ponto_id=self.id,
                    ponto_n=1,
                    status="aprovado" if veredito == "APROVADO" else "reprovado",
                    pontuacao_percentual=round(int(nota) / 12 * 100, 2),
                    criterios_aprovados=int(nota),
                    reasoning_auditoria=auditoria[-12000:],
                    pontos_fracos=None,
                )
        dossie = self.arquivos.get("DOSSIE.md", _Arquivo()).texto
        if dossie:
            self._pub("writer.progress", status="concluido", total_caracteres=len(dossie))
            self._status("concluido")
            self._pub("report.final", status="concluido", dossier_final=dossie,
                      total_caracteres=len(dossie), concluido_em=None)
        else:
            self._status("concluido" if sucesso else "falha")


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
        watcher.consolidar(sucesso=bool(watcher.arquivos.get("DOSSIE.md", _Arquivo()).texto))
