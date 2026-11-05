"""Persistência e hidratação a partir do banco (SDD §5-6)."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

from contracts import PERSONAS, PontoPlano, ResearchRequest, normalizar_urls
from db.sqlite_manager import conectar
from engine import AgentCall

CAMPOS_JSON_RUN = (
    "plano_inicial",
    "lacunas_finais_consolidadas",
    "urls_usadas_globais",
    "urls_lidas_globais",
    "urls_nao_usadas_globais",
)
CAMPOS_JSON_PONTO = (
    "subperguntas",
    "hipoteses",
    "lacunas_iniciais",
    "perguntas_auditoria",
    "ultimo_resultado_auditor",
)


def _dumps(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False)


def _loads(valor: str | None, padrao: Any = None) -> Any:
    return json.loads(valor) if valor else padrao


class Repositorio:
    def __init__(self, caminho: str | Path):
        self._con = conectar(caminho)
        self._lock = threading.RLock()

    def fechar(self) -> None:
        with self._lock:
            self._con.close()

    # -- escrita -----------------------------------------------------------
    def _executar(self, sql: str, parametros: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cursor = self._con.execute(sql, tuple(parametros))
            self._con.commit()
            return cursor

    def criar_run(self, research_id: str, requisicao: ResearchRequest) -> None:
        self._executar(
            "INSERT INTO research_runs (research_id, tema, profundidade, veracidade_alvo,"
            " max_rodadas_auditoria, atualidade, callback_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                research_id,
                requisicao.tema,
                requisicao.profundidade,
                float(requisicao.veracidade_alvo),
                requisicao.max_rodadas_auditoria,
                requisicao.atualidade,
                str(requisicao.callback_url),
            ),
        )

    def salvar_plano(self, research_id: str, plano: dict[str, Any], pontos: list[PontoPlano]) -> None:
        with self._lock:
            self._con.execute(
                "UPDATE research_runs SET plano_inicial = ? WHERE research_id = ?",
                (_dumps(plano), research_id),
            )
            self._con.execute("DELETE FROM research_points WHERE research_id = ?", (research_id,))
            self._con.executemany(
                "INSERT INTO research_points (research_id, ponto_id, enunciado, subperguntas,"
                " hipoteses, lacunas_iniciais, perguntas_auditoria) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        research_id,
                        ponto.ponto_id,
                        ponto.enunciado,
                        _dumps(ponto.subperguntas),
                        _dumps(ponto.hipoteses),
                        _dumps(ponto.lacunas_iniciais),
                        _dumps(ponto.perguntas_auditoria),
                    )
                    for ponto in pontos
                ],
            )
            self._con.commit()

    def registrar_execucao(
        self,
        *,
        research_id: str,
        ponto_id: int | None,
        rodada: int,
        agent_role: str,
        model_used: str | None = None,
        input_prompt_payload: dict[str, Any],
        call: AgentCall,
        informacao_coletada: str | None = None,
        urls_usadas: Iterable[str] = (),
        urls_lidas: Iterable[str] = (),
    ) -> str:
        usadas = normalizar_urls(urls_usadas)
        lidas = normalizar_urls([*urls_lidas, *usadas])
        nao_usadas = [url for url in lidas if url not in set(usadas)]
        total = call.total_tokens or (call.prompt_tokens + call.completion_tokens)
        with self._lock:
            cursor = self._con.execute(
                "INSERT INTO agent_executions (research_id, ponto_id, rodada, agent_role,"
                " model_used, input_prompt_payload, raw_output_payload, informacao_coletada,"
                " reasoning_trace, tool_calls, urls_usadas, urls_lidas, urls_lidas_nao_usadas,"
                " prompt_tokens, completion_tokens, reasoning_tokens, total_tokens, latency_ms)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    research_id,
                    ponto_id,
                    rodada,
                    agent_role,
                    model_used,
                    _dumps(input_prompt_payload),
                    _dumps(call.dados if call.dados else {"texto": call.texto}),
                    informacao_coletada,
                    call.reasoning_trace or None,
                    _dumps(call.tool_calls),
                    _dumps(usadas),
                    _dumps(lidas),
                    _dumps(nao_usadas),
                    call.prompt_tokens,
                    call.completion_tokens,
                    call.reasoning_tokens,
                    total,
                    call.latency_ms,
                ),
            )
            self._con.execute(
                "UPDATE research_runs SET total_prompt_tokens = total_prompt_tokens + ?,"
                " total_completion_tokens = total_completion_tokens + ?,"
                " total_reasoning_tokens = total_reasoning_tokens + ?,"
                " total_tokens = total_tokens + ? WHERE research_id = ?",
                (
                    call.prompt_tokens,
                    call.completion_tokens,
                    call.reasoning_tokens,
                    total,
                    research_id,
                ),
            )
            self._con.commit()
            return str(cursor.lastrowid)

    def salvar_auditoria(
        self,
        *,
        research_id: str,
        ponto_id: int,
        rodada: int,
        perguntas_respondidas: dict[str, bool],
        decisao: dict[str, Any],
    ) -> None:
        self._executar(
            "UPDATE research_points SET ultimo_resultado_auditor = ?, porcentagem_aprovacao = ?,"
            " aprovado = ?, rodada_atual = ? WHERE research_id = ? AND ponto_id = ?",
            (
                _dumps(perguntas_respondidas),
                decisao["porcentagem_aprovacao"],
                int(bool(decisao["aprovado"])),
                rodada,
                research_id,
                ponto_id,
            ),
        )

    def salvar_relatorio(
        self, *, research_id: str, ponto_id: int, relatorio: str, lacunas: str
    ) -> None:
        self._executar(
            "UPDATE research_points SET relatorio_ponto = ?, lacunas_ponto = ?"
            " WHERE research_id = ? AND ponto_id = ?",
            (relatorio, lacunas, research_id, ponto_id),
        )

    def marcar_status(self, research_id: str, status: str) -> None:
        self._executar(
            "UPDATE research_runs SET status = ?, completed_at = CASE WHEN ? = 'COMPLETED'"
            " THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now') ELSE completed_at END"
            " WHERE research_id = ?",
            (status, status, research_id),
        )

    # -- leitura -----------------------------------------------------------
    def obter_run(self, research_id: str) -> dict[str, Any] | None:
        with self._lock:
            linha = self._con.execute(
                "SELECT * FROM research_runs WHERE research_id = ?", (research_id,)
            ).fetchone()
        if linha is None:
            return None
        run = dict(linha)
        for campo in CAMPOS_JSON_RUN:
            run[campo] = _loads(run.get(campo), [] if campo.startswith("urls_") else None)
        return run

    def obter_pontos(self, research_id: str) -> list[dict[str, Any]]:
        with self._lock:
            linhas = self._con.execute(
                "SELECT * FROM research_points WHERE research_id = ? ORDER BY ponto_id ASC",
                (research_id,),
            ).fetchall()
        pontos = []
        for linha in linhas:
            ponto = dict(linha)
            for campo in CAMPOS_JSON_PONTO:
                ponto[campo] = _loads(ponto.get(campo))
            ponto["aprovado"] = bool(ponto["aprovado"])
            pontos.append(ponto)
        return pontos

    def obter_execucoes(
        self, research_id: str, ponto_id: int | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM agent_executions WHERE research_id = ?"
        parametros: list[Any] = [research_id]
        if ponto_id is not None:
            sql += " AND ponto_id = ?"
            parametros.append(ponto_id)
        sql += " ORDER BY rowid ASC"
        with self._lock:
            linhas = self._con.execute(sql, tuple(parametros)).fetchall()
        campos_json = (
            "input_prompt_payload",
            "raw_output_payload",
            "tool_calls",
            "urls_usadas",
            "urls_lidas",
            "urls_lidas_nao_usadas",
        )
        execucoes = []
        for linha in linhas:
            execucao = dict(linha)
            for campo in campos_json:
                execucao[campo] = _loads(execucao[campo])
            execucoes.append(execucao)
        return execucoes

    def hidratar(self, research_id: str, ponto_id: int) -> dict[str, Any]:
        """Tudo o que o auditor/redator precisam do ponto, sem truncamento (SDD §6)."""
        marcadores = ", ".join("?" for _ in PERSONAS)
        with self._lock:
            linhas = self._con.execute(
                "SELECT rodada, agent_role, informacao_coletada FROM agent_executions"
                f" WHERE research_id = ? AND ponto_id = ? AND agent_role IN ({marcadores})"
                " AND informacao_coletada IS NOT NULL ORDER BY rodada ASC, rowid ASC",
                (research_id, ponto_id, *PERSONAS),
            ).fetchall()
            urls = self._con.execute(
                "SELECT urls_usadas, urls_lidas FROM agent_executions"
                " WHERE research_id = ? AND ponto_id = ? ORDER BY rowid ASC",
                (research_id, ponto_id),
            ).fetchall()

        por_rodada: dict[int, dict[str, str]] = {}
        for linha in linhas:
            por_rodada.setdefault(int(linha["rodada"]), {})[linha["agent_role"]] = linha[
                "informacao_coletada"
            ]
        rodadas = [
            {"rodada": rodada, **{persona: textos[persona] for persona in PERSONAS if persona in textos}}
            for rodada, textos in sorted(por_rodada.items())
        ]

        usadas: list[str] = []
        lidas: list[str] = []
        for linha in urls:
            usadas.extend(_loads(linha["urls_usadas"], []))
            lidas.extend(_loads(linha["urls_lidas"], []))
        return {
            "rodadas": rodadas,
            "urls_usadas": normalizar_urls(usadas),
            "urls_lidas": normalizar_urls(lidas),
        }

    def urls_lidas(self, research_id: str, ponto_id: int) -> list[str]:
        return self.hidratar(research_id, ponto_id)["urls_lidas"]

    def consolidar(self, research_id: str) -> dict[str, Any]:
        """Consolida os pontos e fecha o run (PRD RF08, feature 10)."""
        with self._lock:
            linhas = self._con.execute(
                "SELECT ponto_id, enunciado, relatorio_ponto, lacunas_ponto FROM research_points"
                " WHERE research_id = ? ORDER BY ponto_id ASC",
                (research_id,),
            ).fetchall()
            if not linhas:
                raise ValueError(f"pesquisa {research_id} não tem pontos")
            sem_relatorio = [linha["ponto_id"] for linha in linhas if not linha["relatorio_ponto"]]
            if sem_relatorio:
                raise ValueError(f"pontos sem relatório: {sem_relatorio}")

            relatorios = [
                f"## {linha['ponto_id']}. {linha['enunciado']}\n\n{linha['relatorio_ponto']}"
                for linha in linhas
            ]
            lacunas = [
                {"ponto_id": linha["ponto_id"], "lacunas": linha["lacunas_ponto"]}
                for linha in linhas
                if linha["lacunas_ponto"]
            ]

            execucoes = self._con.execute(
                "SELECT urls_usadas, urls_lidas FROM agent_executions"
                " WHERE research_id = ? ORDER BY rowid ASC",
                (research_id,),
            ).fetchall()
            usadas: list[str] = []
            lidas: list[str] = []
            for linha in execucoes:
                usadas.extend(_loads(linha["urls_usadas"], []))
                lidas.extend(_loads(linha["urls_lidas"], []))
            usadas = normalizar_urls(usadas)
            lidas = normalizar_urls(lidas)
            nao_usadas = [url for url in lidas if url not in set(usadas)]

            tokens = self._con.execute(
                "SELECT COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,"
                " COALESCE(SUM(completion_tokens), 0) AS completion_tokens,"
                " COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens,"
                " COALESCE(SUM(total_tokens), 0) AS total_tokens"
                " FROM agent_executions WHERE research_id = ?",
                (research_id,),
            ).fetchone()

            relatorio_final = "\n\n".join(relatorios)
            self._con.execute(
                "UPDATE research_runs SET status = 'COMPLETED', relatorio_final_consolidado = ?,"
                " lacunas_finais_consolidadas = ?, urls_usadas_globais = ?,"
                " urls_lidas_globais = ?, urls_nao_usadas_globais = ?,"
                " completed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE research_id = ?",
                (
                    relatorio_final,
                    _dumps(lacunas),
                    _dumps(usadas),
                    _dumps(lidas),
                    _dumps(nao_usadas),
                    research_id,
                ),
            )
            self._con.commit()

        return {
            "research_id": research_id,
            "relatorio_final": relatorio_final,
            "lacunas_finais": lacunas,
            "urls_usadas": usadas,
            "urls_lidas": lidas,
            "urls_lidas_nao_usadas": nao_usadas,
            "metricas_tokens": {
                "prompt_tokens": int(tokens["prompt_tokens"]),
                "completion_tokens": int(tokens["completion_tokens"]),
                "reasoning_tokens": int(tokens["reasoning_tokens"]),
                "total_tokens": int(tokens["total_tokens"]),
            },
        }
