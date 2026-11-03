"""Identificadores de ponto usados nos eventos SSE.

O perfil Hermes trata a pesquisa como um bloco único, mas a UI organiza a execução
por ponto. Este registro liga a pesquisa ao primeiro ponto criado no plano para que
os eventos de agente/stage caiam no card certo.
"""

from __future__ import annotations

from typing import Dict, Iterable

_PONTO_POR_PESQUISA: Dict[str, str] = {}


def registrar(pesquisa_id: str, pontos: Iterable[str]) -> None:
    for ponto_id in pontos:
        _PONTO_POR_PESQUISA[pesquisa_id] = str(ponto_id)
        return


def ponto_de(pesquisa_id: str) -> str:
    return _PONTO_POR_PESQUISA.get(pesquisa_id, pesquisa_id)


def limpar(pesquisa_id: str) -> None:
    _PONTO_POR_PESQUISA.pop(pesquisa_id, None)
