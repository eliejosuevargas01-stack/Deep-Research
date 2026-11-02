"""Adaptador entre o pipeline da UI e o perfil Hermes `planner`.

Com `DR_PIPELINE_MODE=hermes`, as etapas /search, /audit e /writer deixam de chamar
Jina e o modelo direto: a pesquisa inteira roda uma vez no processo Hermes e as
respostas são derivadas dos documentos Markdown produzidos lá.

Contrato de arquivos (ver app/core/hermes_planner.py):
    PLAN.md, HISTORIADOR_SEARCH.md, VISIONARIO_SEARCH.md, CETICO_SEARCH.md,
    FUTURISTA_SEARCH.md, AUDITORIA.md, DOSSIE.md
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core import hermes_planner

_LOCKS: Dict[str, asyncio.Lock] = {}

PERSONA_ARQUIVOS = {
    "historiador": "HISTORIADOR_SEARCH.md",
    "visionario": "VISIONARIO_SEARCH.md",
    "cetico": "CETICO_SEARCH.md",
    "futurista": "FUTURISTA_SEARCH.md",
}

_URL_RE = re.compile(r"https?://[^\s)\]>\"]+")
_RODADA_RE = re.compile(r"^##\s+Rodada\s+(\d+)\s*[—:-]\s*(APROVADO|REPROVADO)\s*[—:-]\s*nota\s*(\d+)\s*/\s*12", re.M)
_TOTAL_RE = re.compile(r"TOTAL:\s*(\d+)\s*p[áa]ginas", re.I)


def modo_hermes() -> bool:
    """Liga o caminho Hermes no pipeline HTTP (sem Jina, sem chamada direta por etapa)."""
    return (os.environ.get("DR_PIPELINE_MODE") or "").strip().lower() == "hermes"


class JinaNulo:
    """Cliente Jina inerte: o plano não consulta SERP quando o pipeline é Hermes."""

    async def search(self, query: str, **_: Any) -> List[Dict[str, Any]]:
        return []

    async def aclose(self) -> None:
        return None


def _urls(texto: str) -> List[str]:
    vistos: List[str] = []
    for url in _URL_RE.findall(texto):
        limpa = url.rstrip(".,;)]")
        if limpa not in vistos:
            vistos.append(limpa)
    return vistos


def _paginas_lidas(texto: str) -> int:
    totais = [int(m) for m in _TOTAL_RE.findall(texto)]
    return totais[-1] if totais else 0


def _tentativas(texto: str) -> int:
    return len(re.findall(r"^tentativa\s+\d+", texto, flags=re.M | re.I)) or 1


async def garantir_pesquisa(pesquisa_id: str, tema: str) -> Path:
    """Roda o planner uma única vez por pesquisa; reusa se o dossiê já existe.

    Lock por pesquisa: dois /search concorrentes (webhook + clique repetido) não
    pagam dois ciclos completos de planner.
    """
    workspace = hermes_planner.criar_workspace(pesquisa_id, tema)
    if not (workspace / "DOSSIE.md").exists():
        lock = _LOCKS.setdefault(pesquisa_id, asyncio.Lock())
        async with lock:
            if not (workspace / "DOSSIE.md").exists():
                await hermes_planner.executar(tema, pesquisa_id)
    return workspace


def search_payload(pesquisa_id: str, workspace: Path) -> Dict[str, Any]:
    """SearchResponse a partir dos *_SEARCH.md."""
    personas: List[Dict[str, Any]] = []
    total_lidas = 0
    total_fontes = 0
    caracteres = 0
    tentativas = 1
    for persona, nome in PERSONA_ARQUIVOS.items():
        arquivo = workspace / nome
        if not arquivo.exists():
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        urls = _urls(texto)
        lidas = _paginas_lidas(texto)
        total_lidas += lidas
        total_fontes += len(urls)
        caracteres += len(texto)
        tentativas = max(tentativas, _tentativas(texto))
        personas.append(
            {
                "persona": persona,
                "analise": texto,
                "urls_fonte": urls,
                "queries_executadas": _tentativas(texto),
                "falha_coleta": not urls,
                "lacunas": None,
            }
        )
    return {
        "id_pesquisa": pesquisa_id,
        "total_pontos_processados": 1,
        "status_pesquisa": "coletado",
        "total_falhas_coleta": sum(1 for p in personas if p["falha_coleta"]),
        "resumo_coletas": [
            {
                "ponto_id": pesquisa_id,
                "ponto_n": 1,
                "status": "coletado",
                "falha_coleta": not personas,
                "total_urls_lidas": total_lidas,
                "total_urls_fonte": total_fontes,
                "tamanho_conteudo_caracteres": caracteres,
                "tentativas": tentativas,
                "personas": personas,
            }
        ],
    }


def audit_payload(pesquisa_id: str, workspace: Path, criterios_minimos: int = 11) -> Dict[str, Any]:
    """AuditResponse a partir das seções `## Rodada N — VEREDITO — nota X/12`."""
    auditoria = workspace / "AUDITORIA.md"
    texto = auditoria.read_text(encoding="utf-8", errors="replace") if auditoria.exists() else ""
    rodadas = _RODADA_RE.findall(texto)
    if not rodadas:
        return {
            "id_pesquisa": pesquisa_id,
            "total_pontos": 1,
            "aprovados": 0,
            "reprovados": 1,
            "pronto_para_writer": False,
            "auditorias": [
                {
                    "ponto_id": pesquisa_id,
                    "ponto_n": 1,
                    "status": "reprovado",
                    "pontuacao_percentual": 0.0,
                    "criterios_aprovados": 0,
                    "criterios_minimos": criterios_minimos,
                    "valido": False,
                    "diagnostico": "AUDITORIA.md ausente ou sem rodada legível",
                }
            ],
        }
    numero, veredito, nota = rodadas[-1]
    aprovado = veredito == "APROVADO" and int(nota) >= criterios_minimos
    return {
        "id_pesquisa": pesquisa_id,
        "total_pontos": 1,
        "aprovados": 1 if aprovado else 0,
        "reprovados": 0 if aprovado else 1,
        "pronto_para_writer": aprovado,
        "auditorias": [
            {
                "ponto_id": pesquisa_id,
                "ponto_n": 1,
                "status": "aprovado" if aprovado else "reprovado",
                "pontuacao_percentual": round(int(nota) / 12 * 100, 2),
                "criterios_aprovados": int(nota),
                "criterios_minimos": criterios_minimos,
                "valido": True,
                "resumo_auditoria": f"Rodada {numero}: {veredito} {nota}/12 (auditor Hermes)",
            }
        ],
    }


def writer_payload(pesquisa_id: str, tema: str, workspace: Path) -> Dict[str, Any]:
    """WriterResponse a partir do DOSSIE.md."""
    dossie = workspace / "DOSSIE.md"
    texto = dossie.read_text(encoding="utf-8", errors="replace") if dossie.exists() else ""
    return {
        "id_pesquisa": pesquisa_id,
        "tema": tema,
        "status": "concluido" if texto.strip() else "falha",
        "total_caracteres_dossier": len(texto),
        "dossier_final": texto or None,
        "diagnostico": None if texto.strip() else "DOSSIE.md ausente",
        "metadados": {"pipeline": "hermes", "diretorio": str(workspace)},
    }


def relatorio(workspace: Path) -> Dict[str, Any]:
    """Inventário simples para diagnóstico (usado pelo endpoint e por testes)."""
    return {
        "arquivos": hermes_planner._inventario(workspace),
        "rodadas_auditoria": hermes_planner._conta_rodadas_auditoria(workspace),
        "urls_fora_do_acervo": hermes_planner._urls_fora_do_acervo(workspace),
    }


_BLOCO_JSON = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)
_META_RE = re.compile(r"<!--\s*meta\s*(\{.*?\})\s*-->", re.S)

CHAVES_PLANO = ("versao", "tema", "objetivo", "escopo", "perguntas", "personas",
                "criterios_evidencia", "criterios_aprovacao")


def plan_payload(workspace: Path) -> Dict[str, Any]:
    """Plano estruturado: último bloco ```json de PLAN.md, validado contra o contrato."""
    plano_md = workspace / "PLAN.md"
    if not plano_md.exists():
        return {"valido": False, "erro": "PLAN.md ausente", "plano": None}
    blocos = _BLOCO_JSON.findall(plano_md.read_text(encoding="utf-8", errors="replace"))
    if not blocos:
        return {"valido": False, "erro": "PLAN.md sem bloco ```json de contrato", "plano": None}
    try:
        plano = json.loads(blocos[-1])
    except json.JSONDecodeError as exc:
        return {"valido": False, "erro": f"JSON inválido em PLAN.md: {exc}", "plano": None}
    faltando = [c for c in CHAVES_PLANO if c not in plano]
    if faltando:
        return {"valido": False, "erro": f"chaves ausentes: {', '.join(faltando)}", "plano": plano}
    personas = plano.get("personas") or {}
    if set(personas) != set(PERSONA_ARQUIVOS):
        return {
            "valido": False,
            "erro": f"personas deve conter exatamente {sorted(PERSONA_ARQUIVOS)}",
            "plano": plano,
        }
    return {"valido": True, "erro": None, "plano": plano}


def meta_personas(workspace: Path) -> List[Dict[str, Any]]:
    """Linhas `<!-- meta {...} -->` de cada *_SEARCH.md (contrato por seção)."""
    itens: List[Dict[str, Any]] = []
    for persona, nome in PERSONA_ARQUIVOS.items():
        arquivo = workspace / nome
        if not arquivo.exists():
            continue
        for bruto in _META_RE.findall(arquivo.read_text(encoding="utf-8", errors="replace")):
            try:
                meta = json.loads(bruto)
            except json.JSONDecodeError:
                continue
            meta.setdefault("persona", persona)
            itens.append(meta)
    return itens


def estagio(workspace: Path) -> str:
    """Fase corrente derivada dos arquivos já gravados."""
    if (workspace / "DOSSIE.md").exists():
        return "concluido"
    if (workspace / "AUDITORIA.md").exists():
        return "auditando"
    buscas = sum(1 for nome in PERSONA_ARQUIVOS.values() if (workspace / nome).exists())
    if buscas:
        return f"buscando({buscas}/4)"
    if (workspace / "PLAN.md").exists():
        return "planejado"
    return "iniciando"


def detalhe(pesquisa_id: str, obra: Path) -> Dict[str, Any]:
    """Payload de acompanhamento para a UI (polling): fase, plano, contratos."""
    plano = plan_payload(obra)
    return {
        "pesquisa_id": pesquisa_id,
        "diretorio": str(obra),
        "estagio": estagio(obra),
        "plano_valido": plano["valido"],
        "plano_erro": plano["erro"],
        "plano": plano["plano"],
        "metas_personas": meta_personas(obra),
        "rodadas_auditoria": hermes_planner._conta_rodadas_auditoria(obra),
        "arquivos": hermes_planner._inventario(obra),
        "urls_fora_do_acervo": hermes_planner._urls_fora_do_acervo(obra),
    }
