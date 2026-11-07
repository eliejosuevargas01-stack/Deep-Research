"""Cálculo de veracidade e decisão de fluxo (PRD RF05, feature 06)."""

from __future__ import annotations

from typing import Any

ACAO_NOVA_RODADA = "chamar_subagentes_buscadores_rodada_seguinte"
ACAO_REDATOR = "chamar_subagente_redator"
ACAO_REDATOR_LIMITE = "encerrar_buscas_por_limite_e_chamar_redator"


def taxa_aprovacao(perguntas_respondidas: dict[str, bool]) -> float:
    total = len(perguntas_respondidas) or 12
    aprovadas = sum(1 for aprovada in perguntas_respondidas.values() if aprovada)
    return round(aprovadas * 100 / total, 2)


def avaliar(
    *,
    perguntas_respondidas: dict[str, bool],
    veracidade_alvo: float,
    tentativa_atual: int,
    max_rodadas_auditoria: int,
) -> dict[str, Any]:
    taxa = taxa_aprovacao(perguntas_respondidas)
    aprovado = taxa >= round(float(veracidade_alvo), 2)
    if aprovado:
        proxima_acao = ACAO_REDATOR
    elif tentativa_atual >= max_rodadas_auditoria:
        proxima_acao = ACAO_REDATOR_LIMITE
    else:
        proxima_acao = ACAO_NOVA_RODADA
    return {
        "tentativa_atual": tentativa_atual,
        "perguntas_true": sum(1 for aprovada in perguntas_respondidas.values() if aprovada),
        "total_perguntas": len(perguntas_respondidas) or 12,
        "porcentagem_aprovacao": taxa,
        "meta_veracidade_alvo": float(veracidade_alvo),
        "aprovado": aprovado,
        "proxima_acao": proxima_acao,
    }


def avaliacao_pontos(
    *,
    research_id: str,
    tema: str,
    tentativa_atual: int,
    avaliacoes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Monta o objeto agregado SDD §5.7 a partir de decisões já calculadas por `avaliar`.

    Cada item de `avaliacoes` é uma decisão de `avaliar` acrescida de `ponto_id`.
    Reaproveita os números sem recalcular; descarta os campos de fluxo
    (`tentativa_atual`, `proxima_acao`), que não fazem parte do shape da spec.

    Consumida pelo fluxo via `Repositorio.obter_avaliacao` (D-08): alimenta a
    consolidação, o `GET /research/{id}` e o evento `run.concluido`.
    """
    pontos = [
        {
            "ponto_id": avaliacao["ponto_id"],
            "perguntas_true": avaliacao["perguntas_true"],
            "total_perguntas": avaliacao["total_perguntas"],
            "porcentagem_aprovacao": avaliacao["porcentagem_aprovacao"],
            "meta_veracidade_alvo": avaliacao["meta_veracidade_alvo"],
            "aprovado": avaliacao["aprovado"],
        }
        for avaliacao in avaliacoes
    ]
    return {
        "research_id": research_id,
        "tentativa_atual": tentativa_atual,
        "tema": tema,
        "avaliacao_pontos": pontos,
    }
