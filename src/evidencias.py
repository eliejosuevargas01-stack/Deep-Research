"""Compactação determinística de evidências (economia de tokens, sem perda).

Usada só nos prompts de auditor/redator: o que está persistido em
`agent_executions` nunca muda. Regras:
- normaliza espaços/fim de linha;
- remove linhas exatamente duplicadas entre personas/rodadas (primeira
  ocorrência vence, ordem preservada, todas as linhas únicas ficam);
- remove ruído de navegação/boilerplate repetido por lista conservadora;
  linha com dígito, URL, data ou começo de fato nunca é removida;
- URLs, números, datas e citações preservados integralmente.
"""

from __future__ import annotations

import re
from typing import Any

_RUIDO_EXATO = frozenset(
    {
        "compartilhar",
        "leia mais",
        "leia também",
        "saiba mais",
        "clique aqui",
        "aceitar cookies",
        "aceitar todos os cookies",
        "política de privacidade",
        "politica de privacidade",
        "termos de uso",
        "todos os direitos reservados",
        "assine nossa newsletter",
        "inscreva-se",
        "menu",
        "início",
        "inicio",
        "página inicial",
        "pagina inicial",
        "voltar ao topo",
    }
)

_RUIDO_PREFIXO = (
    "home >",
    "início >",
    "inicio >",
    "você está em",
    "voce esta em",
)


def _tem_conteudo_protegido(linha: str) -> bool:
    base = linha.strip().lower()
    if re.search(r"\d", linha):
        return True
    if "http" in base or "www." in base or ".com" in base or ".org" in base or ".gov" in base:
        return True
    if re.search(
        r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b"
        r"|janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto"
        r"|setembro|outubro|novembro|dezembro",
        base,
    ):
        return True
    if base.startswith(("\"", "'", "“", "«")) or "fonte:" in base or "segundo " in base:
        return True
    return False


def _ruido(linha: str) -> bool:
    base = re.sub(r"\s+", " ", linha.strip().lower()).strip(" -–—•·|›»")
    if not base:
        return True
    if _tem_conteudo_protegido(linha):
        return False
    if base in _RUIDO_EXATO:
        return True
    return base.startswith(_RUIDO_PREFIXO)


def compactar_texto(texto: str) -> tuple[str, dict[str, int]]:
    """Compacta um bloco de coleta; devolve (texto, estatísticas)."""
    original = texto or ""
    linhas_antes = original.splitlines() or ([""] if original else [])
    vistas: set[str] = set()
    saidas: list[str] = []
    for bruta in linhas_antes:
        linha = re.sub(r"[ \t]+", " ", bruta).strip()
        if not linha or _ruido(linha):
            continue
        if linha in vistas:
            continue
        vistas.add(linha)
        saidas.append(linha)
    compacto = "\n".join(saidas)
    return compacto, {
        "linhas_antes": len(linhas_antes),
        "linhas_depois": len(saidas),
        "chars_antes": len(original),
        "chars_depois": len(compacto),
    }


def compactar_acumulado(
    acumulado: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Compacta `rodadas` do hidratar, preservando shape e chaves.

    Cada valor de persona passa por `compactar_texto`; chaves não-texto
    passam intactas. Estatísticas agregadas para log/evento.
    """
    total = {"linhas_antes": 0, "linhas_depois": 0, "chars_antes": 0, "chars_depois": 0}
    saida: list[dict[str, Any]] = []
    for bloco in acumulado:
        novo = dict(bloco)
        for chave, valor in bloco.items():
            if chave == "rodada" or not isinstance(valor, str):
                continue
            texto, est = compactar_texto(valor)
            novo[chave] = texto
            for campo in total:
                total[campo] += est[campo]
        saida.append(novo)
    return saida, total
