"""Identificadores de ponto usados nos eventos e respostas por ponto.

O perfil Hermes pesquisa o tema em um ciclo (4 personas), enquanto a UI acompanha
um card por ponto do plano. Este registro liga a pesquisa à lista ordenada de pontos
criados no `/plan` para que eventos e respostas caiam nos cards certos.
"""

from __future__ import annotations

from typing import Dict, Iterable, List

_PONTOS_POR_PESQUISA: Dict[str, List[str]] = {}


def registrar(pesquisa_id: str, pontos: Iterable[str]) -> None:
    ids = [str(p) for p in pontos if str(p)]
    if ids:
        _PONTOS_POR_PESQUISA[pesquisa_id] = ids


def pontos_de(pesquisa_id: str) -> List[str]:
    return _PONTOS_POR_PESQUISA.get(pesquisa_id) or [pesquisa_id]


def ponto_de(pesquisa_id: str) -> str:
    return pontos_de(pesquisa_id)[0]


def limpar(pesquisa_id: str) -> None:
    _PONTOS_POR_PESQUISA.pop(pesquisa_id, None)
