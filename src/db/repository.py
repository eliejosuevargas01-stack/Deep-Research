"""Persistência e hidratação a partir do banco (SDD §5-6)."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

from contracts import PERSONAS, PontoPlano, ResearchRequest, chave_url, normalizar_urls
from db.sqlite_manager import conectar
from engine import AgentCall
import planner

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
        chaves_usadas = {chave_url(url) for url in usadas}
        nao_usadas = [url for url in lidas if chave_url(url) not in chaves_usadas]
        total = call.total_tokens or (
            call.prompt_tokens + call.completion_tokens + call.reasoning_tokens
        )
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

    def carregar_auditoria(self, *, research_id: str, ponto_id: int) -> dict[str, bool]:
        """Último resultado persistido do auditor; JSON inválido/ausente vira {}."""
        with self._lock:
            linha = self._con.execute(
                "SELECT ultimo_resultado_auditor FROM research_points"
                " WHERE research_id = ? AND ponto_id = ?",
                (research_id, ponto_id),
            ).fetchone()
        if linha is None:
            return {}
        try:
            dado = _loads(linha["ultimo_resultado_auditor"], {})
        except (ValueError, TypeError):
            return {}
        if not isinstance(dado, dict):
            return {}
        return {str(k): bool(v) for k, v in dado.items()}

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

    # -- eventos SSE (persistidos antes de publicar) --------------------------
    def emitir_evento(self, research_id: str, tipo: str, payload: dict[str, Any] | None = None) -> int:
        with self._lock:
            cursor = self._con.execute(
                "INSERT INTO research_events (research_id, tipo, payload) VALUES (?, ?, ?)",
                (research_id, tipo, _dumps(payload or {})),
            )
            self._con.commit()
            return int(cursor.lastrowid)

    def listar_eventos(self, research_id: str, depois_de: int = 0, limite: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            linhas = self._con.execute(
                "SELECT id, tipo, payload FROM research_events"
                " WHERE research_id = ? AND id > ? ORDER BY id ASC LIMIT ?",
                (research_id, depois_de, limite),
            ).fetchall()
        return [
            {"id": linha["id"], "tipo": linha["tipo"], "payload": _loads(linha["payload"], {})}
            for linha in linhas
        ]

    def ultimo_evento_id(self, research_id: str) -> int:
        with self._lock:
            linha = self._con.execute(
                "SELECT COALESCE(MAX(id), 0) AS maximo FROM research_events WHERE research_id = ?",
                (research_id,),
            ).fetchone()
        return int(linha["maximo"]) if linha else 0

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

    def obter_auditorias(self, research_id: str) -> list[dict[str, Any]]:
        """Histórico completo de auditorias (D-04): uma linha por rodada, sem sobrescrever."""
        with self._lock:
            linhas = self._con.execute(
                "SELECT ponto_id, rodada, raw_output_payload, model_used,"
                " prompt_tokens, completion_tokens, reasoning_tokens, total_tokens,"
                " created_at FROM agent_executions"
                " WHERE research_id = ? AND agent_role = 'auditor'"
                " ORDER BY ponto_id ASC, rodada ASC, rowid ASC",
                (research_id,),
            ).fetchall()
        auditorias = []
        for linha in linhas:
            saida = _loads(linha["raw_output_payload"], {})
            perguntas = saida.get("perguntas_respondidas") if isinstance(saida, dict) else None
            if not isinstance(perguntas, dict):
                perguntas = {}
            auditorias.append(
                {
                    "ponto_id": linha["ponto_id"],
                    "rodada": linha["rodada"],
                    "perguntas_respondidas": perguntas,
                    "model_used": linha["model_used"],
                    "prompt_tokens": linha["prompt_tokens"],
                    "completion_tokens": linha["completion_tokens"],
                    "reasoning_tokens": linha["reasoning_tokens"],
                    "total_tokens": linha["total_tokens"],
                    "created_at": linha["created_at"],
                }
            )
        return auditorias

    def obter_avaliacao(self, research_id: str) -> dict[str, Any] | None:
        """Boletim oficial de veracidade (SDD §5.7); None se o run ainda não tem pontos."""
        with self._lock:
            return self._avaliacao_locked(research_id)

    def _avaliacao_locked(self, research_id: str) -> dict[str, Any] | None:
        run = self._con.execute(
            "SELECT research_id, tema, veracidade_alvo, max_rodadas_auditoria"
            " FROM research_runs WHERE research_id = ?",
            (research_id,),
        ).fetchone()
        if run is None:
            return None
        pontos = self._con.execute(
            "SELECT ponto_id, ultimo_resultado_auditor, rodada_atual FROM research_points"
            " WHERE research_id = ? ORDER BY ponto_id ASC",
            (research_id,),
        ).fetchall()
        if not pontos:
            return None
        auditados = [p for p in pontos if p["ultimo_resultado_auditor"]]
        if not auditados:
            return None
        avaliacoes = []
        for ponto in auditados:
            respostas = _loads(ponto["ultimo_resultado_auditor"], {}) or {}
            decisao = planner.avaliar(
                perguntas_respondidas=respostas,
                veracidade_alvo=run["veracidade_alvo"],
                tentativa_atual=ponto["rodada_atual"] or 1,
                max_rodadas_auditoria=run["max_rodadas_auditoria"],
            )
            avaliacoes.append({"ponto_id": ponto["ponto_id"], **decisao})
        tentativa = max(int(ponto["rodada_atual"] or 1) for ponto in auditados)
        return planner.avaliacao_pontos(
            research_id=run["research_id"],
            tema=run["tema"],
            tentativa_atual=tentativa,
            avaliacoes=avaliacoes,
        )

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
        """Consolida os pontos e fecha o run (PRD RF08, feature 10).

        Pontos sem relatório viram seção de ponto incompleto em vez de abortar o run;
        FAILED só quando o run inteiro falha (nenhum ponto redigido).
        """
        with self._lock:
            linhas = self._con.execute(
                "SELECT ponto_id, enunciado, relatorio_ponto, lacunas_ponto FROM research_points"
                " WHERE research_id = ? ORDER BY ponto_id ASC",
                (research_id,),
            ).fetchall()
            if not linhas:
                raise ValueError(f"pesquisa {research_id} não tem pontos")
            pontos_falhos: list[dict[str, Any]] = []
            for linha in linhas:
                if not linha["relatorio_ponto"]:
                    lacuna = self._lacuna_ponto(research_id, linha["ponto_id"])
                    pontos_falhos.append(
                        {"ponto_id": linha["ponto_id"], "erro": lacuna["erro"], "lacuna": lacuna["lacuna"]}
                    )
            if len(pontos_falhos) == len(linhas):
                # Run inteiro falhou: nenhum ponto redigiu → FAILED no executar.
                raise ValueError(
                    "nenhum ponto com relatório: "
                    + ", ".join(str(f["ponto_id"]) for f in pontos_falhos)
                )

            relatorios = []
            for linha in linhas:
                if linha["relatorio_ponto"]:
                    relatorios.append(
                        f"## {linha['ponto_id']}. {linha['enunciado']}\n\n{linha['relatorio_ponto']}"
                    )
                else:
                    falho = next(
                        f for f in pontos_falhos if f["ponto_id"] == linha["ponto_id"]
                    )
                    relatorios.append(
                        f"## {linha['ponto_id']}. {linha['enunciado']}\n\n"
                        f"Ponto incompleto: {falho['lacuna']}"
                        + (f"\n\nErro: {falho['erro']}" if falho["erro"] else "")
                    )
            lacunas = [
                {"ponto_id": linha["ponto_id"], "lacunas": linha["lacunas_ponto"]}
                for linha in linhas
                if linha["lacunas_ponto"]
            ]
            for falho in pontos_falhos:
                lacunas.append({"ponto_id": falho["ponto_id"], "lacunas": falho["lacuna"]})

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
            chaves_usadas = {chave_url(url) for url in usadas}
            nao_usadas = [url for url in lidas if chave_url(url) not in chaves_usadas]

            tokens = self._con.execute(
                "SELECT COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,"
                " COALESCE(SUM(completion_tokens), 0) AS completion_tokens,"
                " COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens,"
                " COALESCE(SUM(total_tokens), 0) AS total_tokens"
                " FROM agent_executions WHERE research_id = ?",
                (research_id,),
            ).fetchone()

            relatorio_final = "\n\n".join(relatorios)
            boletim = self._avaliacao_locked(research_id) or {}
            avaliacao = boletim.get("avaliacao_pontos", [])
            if avaliacao:
                secoes = [
                    f"- Ponto {item['ponto_id']}: {item['perguntas_true']}/"
                    f"{item['total_perguntas']} ({item['porcentagem_aprovacao']}%) — "
                    f"{'aprovado' if item['aprovado'] else 'reprovado'}"
                    for item in avaliacao
                ]
                relatorio_final += "\n\n## Avaliação de veracidade\n\n" + "\n".join(secoes)
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
            "avaliacao_pontos": boletim,
            "pontos_falhos": pontos_falhos,
            "metricas_tokens": {
                "prompt_tokens": int(tokens["prompt_tokens"]),
                "completion_tokens": int(tokens["completion_tokens"]),
                "reasoning_tokens": int(tokens["reasoning_tokens"]),
                "total_tokens": int(tokens["total_tokens"]),
            },
        }

    def _lacuna_ponto(self, research_id: str, ponto_id: int) -> dict[str, str | None]:
        """Descreve o ponto sem relatório: perguntas não concluídas + erro de coleta."""
        ponto = self._con.execute(
            "SELECT perguntas_auditoria, ultimo_resultado_auditor FROM research_points"
            " WHERE research_id = ? AND ponto_id = ?",
            (research_id, ponto_id),
        ).fetchone()
        perguntas = _loads(ponto["perguntas_auditoria"], {}) if ponto else {}
        respostas = _loads(ponto["ultimo_resultado_auditor"], {}) if ponto else {}
        nao_concluidas = sorted(
            (chave for chave in perguntas if not respostas.get(chave, False)),
            key=lambda chave: int(chave) if chave.isdigit() else chave,
        )
        erro = None
        eventos = self._con.execute(
            "SELECT payload FROM research_events WHERE research_id = ? AND tipo = 'ponto.erro'"
            " ORDER BY id ASC",
            (research_id,),
        ).fetchall()
        for evento in eventos:
            dado = _loads(evento["payload"], {})
            if isinstance(dado, dict) and dado.get("ponto_id") == ponto_id and dado.get("erro"):
                erro = str(dado["erro"])
        if nao_concluidas:
            lacuna = (
                "perguntas não concluídas: "
                + ", ".join(f"{chave} ({perguntas.get(chave, '')})" for chave in nao_concluidas)
            )
        else:
            lacuna = "ponto sem relatório do redator"
        return {"lacuna": lacuna, "erro": erro}
