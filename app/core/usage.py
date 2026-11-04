"""Contabilidade de tokens da pesquisa: agente principal + subagentes.

O Hermes escreve `usage.json` no workspace a cada turno — parcial, sobrescrito.
A soma tem que ser monotônica: nenhum turno menor pode apagar o que já foi gasto.
Quando existir `usage_<etapa>.json` (um por invocação: plan/search/audit/write),
a soma por etapa é a verdade; `usage.json` cobre o caso de um único turno
acumulado (contrato antigo).
"""

from __future__ import annotations

import json
import os
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional

ETAPAS = ("plan", "search", "audit", "write")
CAMPOS = ("input_tokens", "output_tokens", "total_tokens")
PERSONAS = ("planejador", "historiador", "pragmatico", "cetico", "visionario", "auditor", "redator")
# grafias que aparecem no título da sessão do Hermes (goal truncado)
_ALIAS_PERSONA = {
    "planejador": ("planejador",),
    "historiador": ("historiador",),
    "pragmatico": ("pragmatico",),
    "cetico": ("cetico",),
    "visionario": ("visionario", "futurista"),
    "auditor": ("auditor",),
    "redator": ("redator",),
}


def nome_arquivo_uso(etapa: Optional[str] = None, ponto: int = 1, rodada: int = 1) -> str:
    """Arquivo de uso da invocação: um por etapa (e por ponto/rodada na busca)."""
    if not etapa:
        return "usage.json"  # contrato antigo: um único turno acumulado
    if etapa == "plan":
        return "usage_plan.json"
    if etapa == "search":
        return f"usage_search_ponto_{int(ponto)}.json"
    if etapa == "audit":
        return f"usage_audit_ponto_{int(ponto)}_rodada_{int(rodada)}.json"
    if etapa == "write":
        return "usage_write.json"
    return f"usage_{etapa}.json"


def _ler(caminho: Path) -> Optional[Dict[str, Any]]:
    if not caminho.exists():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    return dados if isinstance(dados, dict) else None


def _soma(usos) -> Dict[str, int]:
    return {campo: sum(int(u.get(campo) or 0) for u in usos) for campo in CAMPOS}


def _persona(texto: str) -> Optional[str]:
    """Persona citada no texto (título de sessão ou nome do arquivo de etapa)."""
    limpo = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    for persona, chaves in _ALIAS_PERSONA.items():
        if any(chave in limpo for chave in chaves):
            return persona
    return None


def _state_db() -> Optional[Path]:
    """state.db do perfil Hermes: fonte real de tokens, inclusive de subagentes."""
    home = os.environ.get("HERMES_HOME") or ""
    perfil = os.environ.get("HERMES_PROFILE") or os.environ.get("DR_HERMES_PROFILE") or "deep-research"
    candidatos = []
    if home:
        candidatos.append(Path(home) / "profiles" / perfil / "state.db")
    candidatos.append(Path.home() / ".hermes" / "profiles" / perfil / "state.db")
    for caminho in candidatos:
        if caminho.exists():
            return caminho
    # Perfil do processo pode divergir (HERMES_PROFILE do shell/gateway): usa o
    # state.db mais recente entre os perfis em vez de fingir que não há consumo.
    base = Path(home) / "profiles" if home else None
    if base and base.is_dir():
        achados = sorted(base.glob("*/state.db"), key=lambda c: c.stat().st_mtime, reverse=True)
        if achados:
            return achados[0]
    return None


def _do_state_db(workspace: Path) -> Optional[Dict[str, Any]]:
    """Soma tokens das sessões (principal + subagentes) daquele workspace.

    O `--usage-file` do CLI cobre um turno e não vê delegados; a sessão do Hermes
    vê. As duas fontes são monotônicas entre si: vale a maior.
    """
    caminho = _state_db()
    if caminho is None:
        return None
    raiz = str(workspace)
    try:
        conexao = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return None
    try:
        linhas = conexao.execute(
            "select coalesce(model,''), coalesce(title, display_name, ''),"
            " sum(coalesce(input_tokens,0)), sum(coalesce(output_tokens,0))"
            " from sessions where cwd = ? or cwd like ? group by 1,2",
            (raiz, raiz + "/%"),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conexao.close()
    if not linhas:
        return None
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    por_agente: Dict[str, Dict[str, int]] = {}
    for modelo, titulo, entrada, saida in linhas:
        entrada, saida = int(entrada or 0), int(saida or 0)
        total["input_tokens"] += entrada
        total["output_tokens"] += saida
        total["total_tokens"] += entrada + saida
        rotulo = (titulo or modelo or "agente").strip()
        # Persona reconhecida agrupa; título livre continua como veio (nada inventado).
        rotulo = _persona(rotulo) or rotulo[:60]
        alvo = por_agente.setdefault(
            rotulo, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        )
        alvo["input_tokens"] += entrada
        alvo["output_tokens"] += saida
        alvo["total_tokens"] += entrada + saida
    return {"total": total, "por_agente": por_agente, "modelo": linhas[0][0] or None}


def _do_arquivos(workspace: Path) -> Dict[str, Dict[str, int]]:
    """Consumo de cada `usage_*.json` do workspace (uma invocação por arquivo)."""
    achados: Dict[str, Dict[str, int]] = {}
    for caminho in sorted(workspace.glob("usage_*.json")):
        uso = _ler(caminho)
        if uso:
            achados[caminho.stem[len("usage_") :]] = {
                campo: int(uso.get(campo) or 0) for campo in CAMPOS
            }
    return achados


def _piso(workspace: Path) -> Dict[str, Dict[str, int]]:
    """Estado já apurado: nenhuma etapa pode encolher entre leituras.

    ponytail: o piso vive no `USAGE_SUMMARY.json` do workspace; apagar o arquivo
    zera o histórico local (o banco ainda guarda o maior total já persistido).
    """
    anterior = _ler(workspace / "USAGE_SUMMARY.json") or {}
    guardado = anterior.get("por_etapa")
    piso: Dict[str, Dict[str, int]] = {}
    if isinstance(guardado, dict):
        for nome, uso in guardado.items():
            if isinstance(uso, dict):
                piso[str(nome)] = {campo: int(uso.get(campo) or 0) for campo in CAMPOS}
    return piso


def resumo_uso(workspace: Path) -> Dict[str, Any]:
    """Totais e quebra por etapa/agente da pesquisa."""
    por_etapa = _do_arquivos(workspace)
    for nome, uso in _piso(workspace).items():
        atual = por_etapa.get(nome) or {}
        por_etapa[nome] = {
            campo: max(int(atual.get(campo) or 0), uso.get(campo, 0)) for campo in CAMPOS
        }
    cumulativo = _ler(workspace / "usage.json")
    if por_etapa:
        total = _soma(por_etapa.values())
    elif cumulativo:
        total = {campo: int(cumulativo.get(campo) or 0) for campo in CAMPOS}
    else:
        total = {campo: 0 for campo in CAMPOS}

    estado = _do_state_db(workspace)
    if estado:
        total = {
            campo: max(int(total.get(campo) or 0), int(estado["total"].get(campo) or 0))
            for campo in CAMPOS
        }

    por_agente: Dict[str, Dict[str, int]] = {}
    if estado:
        por_agente.update(estado["por_agente"])
    agentes = (cumulativo or {}).get("agents")
    if isinstance(agentes, dict):
        for agente, uso in agentes.items():
            if isinstance(uso, dict):
                por_agente[str(agente)] = {campo: int(uso.get(campo) or 0) for campo in CAMPOS}
    # Sem sessão por persona, o arquivo da etapa é o que atribui o gasto ao dono.
    dono_etapa = {"plan": "planejador", "write": "redator"}
    for etapa, uso in por_etapa.items():
        por_agente.setdefault(_persona(etapa) or dono_etapa.get(etapa, etapa), uso)
    return {
        "total": total,
        "por_etapa": por_etapa,
        "por_agente": por_agente,
        "modelo": (cumulativo or {}).get("model") or (estado or {}).get("modelo"),
        "api_calls": int((cumulativo or {}).get("api_calls") or 0)
        + sum(
            int((_ler(workspace / f"usage_{e}.json") or {}).get("api_calls") or 0)
            for e in por_etapa
        ),
    }


def gravar_resumo(workspace: Path) -> Dict[str, Any]:
    """Persiste `USAGE_SUMMARY.json` com o detalhamento por agente e o total."""
    resumo = resumo_uso(workspace)
    try:
        (workspace / "USAGE_SUMMARY.json").write_text(
            json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
    return resumo
