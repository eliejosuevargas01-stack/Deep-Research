"""Hidratação do 1º prompt (SDD §2 e §4.3-4.7).

O backend é o único que lê o banco: cada payload abaixo é o que entra no
primeiro prompt do agente, montado a partir das linhas persistidas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contracts import PERSONAS

import evidencias

PROMPTS = Path(__file__).with_name("prompts")

SOULS: dict[str, str] = {
    "planner": (
        "Você é o planner. Faça a varredura exploratória na web para levantar o estado atual do "
        "tema e então decomponha o tema em pontos independentes e auditáveis."
    ),
    "historiador": "Você é o historiador. Traga origem, evolução, marcos e definições canônicas do ponto.",
    "cetico": "Você é o cético. Valide cruzado, priorize fontes primárias, exponha contradições e viés.",
    "visionario": "Você é o visionário. Identifique padrões, tendências emergentes e implicações estratégicas.",
    "futurista": "Você é o futurista. Construa cenários prospectivos, riscos futuros e impactos sistêmicos.",
    "auditor": (
        "Você é o auditor. Avalie rigorosamente todas as informações coletadas em todas as rodadas "
        "e responda somente com true ou false para cada uma das 12 perguntas."
    ),
    "redator": (
        "Você é o redator-chefe. Redija o relatório definitivo com alta densidade analítica e concisão, "
        "sintetizando os dados essenciais apurados, citando as urls_usadas e documentando as lacunas remanescentes."
    ),
}


def montar(papel: str, payload: dict[str, Any]) -> tuple[str, str]:
    """Retorna (system, user) prontos para o engine."""
    template = "buscador" if papel in PERSONAS else papel
    sistema = (PROMPTS / f"{template}.md").read_text(encoding="utf-8")
    prompt = (
        "## Payload da execução\n\n```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\n\nResponda apenas com o objeto JSON, sem texto fora dele."
    )
    return sistema, prompt


def payload_buscador(
    *,
    research_id: str,
    tema: str,
    atualidade: str,
    ponto: dict[str, Any],
    persona: str,
    rodada: int,
    perguntas_pendentes: dict[str, str],
    urls_ignoradas: list[str],
    max_queries: int,
) -> dict[str, Any]:
    return {
        "research_id": research_id,
        "ponto_id": ponto["ponto_id"],
        "rodada": rodada,
        "persona": persona,
        "soul": SOULS[persona],
        "tema": tema,
        "atualidade": atualidade,
        "ponto_enunciado": ponto["enunciado"],
        "subperguntas": ponto["subperguntas"],
        "hipoteses": ponto["hipoteses"],
        "lacunas_iniciais": ponto["lacunas_iniciais"],
        "perguntas_auditoria_pendentes": perguntas_pendentes,
        "urls_lidas_ignoradas": urls_ignoradas,
        "max_queries": max_queries,
    }


def payload_auditor(
    *,
    research_id: str,
    atualidade: str,
    ponto: dict[str, Any],
    tentativa_atual: int,
    max_rodadas_auditoria: int,
    acumulado: list[dict[str, Any]],
) -> dict[str, Any]:
    compactado, estatisticas = evidencias.compactar_acumulado(acumulado)
    return {
        "research_id": research_id,
        "ponto_id": ponto["ponto_id"],
        "persona": "auditor",
        "soul": SOULS["auditor"],
        "atualidade": atualidade,
        "tentativa_atual": tentativa_atual,
        "max_rodadas_auditoria": max_rodadas_auditoria,
        "perguntas_auditoria": ponto["perguntas_auditoria"],
        "informacao_coletada_acumulada": compactado,
        "compactacao": estatisticas,
    }


def payload_redator(
    *,
    research_id: str,
    ponto: dict[str, Any],
    resultado_final_auditor: dict[str, bool],
    urls_usadas_acumuladas: list[str],
    acumulado_integral: list[dict[str, Any]],
    perguntas_nao_concluidas: dict[str, str] | None = None,
    erro_coleta: str | None = None,
) -> dict[str, Any]:
    compactado, estatisticas = evidencias.compactar_acumulado(acumulado_integral)
    return {
        "research_id": research_id,
        "ponto_id": ponto["ponto_id"],
        "persona": "redator",
        "soul": SOULS["redator"],
        "ponto_enunciado": ponto["enunciado"],
        "resultado_final_auditor": resultado_final_auditor,
        "perguntas_auditoria": ponto["perguntas_auditoria"],
        "perguntas_nao_concluidas": perguntas_nao_concluidas or {},
        "erro_coleta": erro_coleta,
        "urls_usadas_acumuladas": urls_usadas_acumuladas,
        "informacao_coletada_acumulada_integral": compactado,
        "compactacao": estatisticas,
    }
