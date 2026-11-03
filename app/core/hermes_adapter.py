"""Adaptador entre a UI e o perfil Hermes embutido.

A pesquisa inteira roda uma vez no processo Hermes; as etapas /plan, /search,
/audit e /writer derivam suas respostas dos documentos Markdown produzidos lá —
sem Jina e sem chamada direta ao modelo por etapa.

Contrato de arquivos (ver app/core/hermes_planner.py):
    PLAN.md, HISTORIADOR_SEARCH.md, VISIONARIO_SEARCH.md, CETICO_SEARCH.md,
    FUTURISTA_SEARCH.md, AUDITORIA.md, DOSSIE.md
"""

from __future__ import annotations

import asyncio
import os
import time
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from app.core import hermes_planner

_LOCKS: Dict[str, asyncio.Lock] = {}


def registrar_pontos(id_pesquisa: str, pontos) -> None:
    """Liga a pesquisa ao primeiro ponto do plano (os eventos caem no card certo)."""
    from app.core import hermes_ids

    hermes_ids.registrar(id_pesquisa, pontos)


def _pub(id_pesquisa: str, evento: str, **dados) -> None:
    """Publica no hub SSE; observabilidade nunca derruba a resposta HTTP."""
    try:
        from app.core import hermes_ids
        from app.core.pipeline_runner import get_pipeline_event_hub

        dados.setdefault("ponto_id", hermes_ids.ponto_de(id_pesquisa))
        get_pipeline_event_hub().publish(id_pesquisa, evento, {"id_pesquisa": id_pesquisa, **dados})
    except Exception:
        pass


PERSONA_ARQUIVOS = {
    "historiador": "HISTORIADOR_SEARCH.md",
    "visionario": "VISIONARIO_SEARCH.md",
    "cetico": "CETICO_SEARCH.md",
    "futurista": "FUTURISTA_SEARCH.md",
}

_URL_RE = re.compile(r"https?://[^\s)\]>\"]+")
_RODADA_RE = re.compile(r"^##\s+Rodada\s+(\d+)\s*[—:-]\s*(APROVADO|REPROVADO)\s*[—:-]\s*nota\s*(\d+)\s*/\s*12", re.M)
_TOTAL_RE = re.compile(r"TOTAL:\s*(\d+)\s*p[áa]ginas", re.I)


def _urls(texto: str) -> List[str]:
    vistos: List[str] = []
    for url in _URL_RE.findall(texto):
        limpa = url.rstrip(".,;)]")
        if limpa not in vistos:
            vistos.append(limpa)
    return vistos


def _paginas_lidas(texto: str) -> int:
    """Soma dos ledgers `TOTAL: N páginas` de todas as rodadas do arquivo."""
    return sum(int(m) for m in _TOTAL_RE.findall(texto))


def _tentativas(texto: str) -> int:
    return len(re.findall(r"^tentativa\s+\d+", texto, flags=re.M | re.I)) or 1


async def garantir_pesquisa(pesquisa_id: str, tema: str) -> Path:
    """Garante o ciclo Hermes rodando e devolve o workspace assim que PLAN.md existe.

    O ciclo continua em background: `/search`, `/audit` e `/writer` esperam o arquivo
    que lhes interessa. Lock por pesquisa evita dois ciclos para o mesmo id.
    """
    workspace = hermes_planner.criar_workspace(pesquisa_id, tema)
    if (workspace / "PLAN.md").exists() and (workspace / "DOSSIE.md").exists():
        return workspace
    lock = _LOCKS.setdefault(pesquisa_id, asyncio.Lock())
    async with lock:
        ex = hermes_planner.execucao_existente(pesquisa_id)
        if ex is None or (ex.tarefa is not None and ex.tarefa.done()):
            ex = await hermes_planner.obter_ou_iniciar(tema, pesquisa_id)
        limite = time.monotonic() + float(os.environ.get("DR_PLAN_TIMEOUT", "180"))
        while time.monotonic() < limite:
            if plan_payload(workspace)["valido"]:
                return workspace
            if ex.tarefa is not None and ex.tarefa.done():
                break
            await asyncio.sleep(2.0)
    raise ValueError("planner não escreveu PLAN.md válido dentro do tempo esperado")


def _raiz_para(pesquisa_id: str) -> List[Path]:
    """Workspaces existentes para o id (o slug do tema varia)."""
    base = hermes_planner._raiz_pesquisas()
    sufixo = f"-{pesquisa_id[:8]}"
    if not base.exists():
        return []
    return sorted(d for d in base.iterdir() if d.is_dir() and d.name.endswith(sufixo))


async def aguardar_coletas(pesquisa_id: str, timeout: float = 3600.0) -> None:
    """Espera os quatro *_SEARCH.md existirem e pararem de crescer."""
    ex = hermes_planner.execucao_existente(pesquisa_id)
    if ex is None:
        return
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        tamanhos = {}
        for nome in PERSONA_ARQUIVOS.values():
            alvo = ex.workspace / nome
            tamanhos[nome] = alvo.stat().st_size if alvo.exists() else 0
        if all(tamanhos.values()):
            await asyncio.sleep(4.0)
            estaveis = all(
                (ex.workspace / nome).stat().st_size == tamanho
                for nome, tamanho in tamanhos.items()
                if (ex.workspace / nome).exists()
            )
            if estaveis:
                return
        if ex.tarefa is not None and ex.tarefa.done():
            return
        await asyncio.sleep(3.0)


async def aguardar_arquivo(pesquisa_id: str, nome: str, timeout: float = 3600.0) -> Path:
    """Espera (sem reiniciar o ciclo) o arquivo aparecer; devolve o workspace."""
    ex = hermes_planner.execucao_existente(pesquisa_id)
    if ex is not None:
        await ex.aguardar_arquivo(nome, timeout=timeout)
        return ex.workspace
    for workspace in _raiz_para(pesquisa_id):
        if (workspace / nome).exists():
            return workspace
    raise ValueError(f"pesquisa sem ciclo ativo e sem {nome}")


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
    for p in personas:
        _pub(
            pesquisa_id,
            "search.progress",
            ponto_id=pesquisa_id,
            persona=p["persona"],
            queries_executadas=p["queries_executadas"],
            urls_lidas=_paginas_lidas(p["analise"]),
            falha_coleta=p["falha_coleta"],
            reasoning_coleta=p["analise"][-12000:],
        )
    _pub(pesquisa_id, "point.status", ponto_id=pesquisa_id, ponto_n=1, status="coletado", tentativas=tentativas)
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
    _pub(
        pesquisa_id,
        "audit.result",
        ponto_id=pesquisa_id,
        ponto_n=1,
        status="aprovado" if aprovado else "reprovado",
        pontuacao_percentual=round(int(nota) / 12 * 100, 2),
        criterios_aprovados=int(nota),
        reasoning_auditoria=texto[-12000:],
        pontos_fracos=None,
    )
    _pub(
        pesquisa_id,
        "point.status",
        ponto_id=pesquisa_id,
        ponto_n=1,
        status="aprovado" if aprovado else "reprovado",
        tentativas=int(numero),
    )
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
    if texto.strip():
        _pub(pesquisa_id, "writer.progress", status="concluido", total_caracteres=len(texto))
        _pub(pesquisa_id, "pipeline.status", status_pipeline="concluido")
        _pub(
            pesquisa_id,
            "report.final",
            status="concluido",
            dossier_final=texto,
            total_caracteres=len(texto),
            concluido_em=None,
        )
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


def pontos_do_plano(plano: Dict[str, Any]) -> List[str]:
    """Um único ponto: o perfil Hermes pesquisa o tema inteiro em um bloco.

    As `perguntas` do plano são sub-perguntas do mesmo ponto — virar cada uma em um
    ponto duplicaria os cards na UI sem que exista coleta separada por pergunta.
    """
    return [str(plano.get("tema") or plano.get("objetivo") or "Investigação")]


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
