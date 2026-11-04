"""Endpoint para hidratação completa de pesquisa por ID.

Permite reidratar o frontend sem histórico local (deep link).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConteudoColetado, Ponto
from app.db.research_repository import ResearchRepository
from app.db.session import get_db
from app.schemas.sources import FontesResumo
from app.services.source_accounting_service import SourceAccountingService

router = APIRouter()


def _parse_json_maybe(val: Optional[str]) -> Any:
    if val is None:
        return None
    if isinstance(val, dict) or isinstance(val, list):
        return val
    try:
        return json.loads(val)
    except Exception:
        return None


def _extract_preferencias(pesquisa: Any) -> Any:
    meta_planej = _parse_json_maybe(getattr(pesquisa, "metadados_planejamento", None))
    if isinstance(meta_planej, dict):
        prefs = meta_planej.get("preferencias")
        if prefs is not None:
            return prefs
    plano = _parse_json_maybe(getattr(pesquisa, "plano_estruturado", None))
    if isinstance(plano, dict):
        prefs = plano.get("preferencias")
        if prefs is not None:
            return prefs
    return None


def _criterios_do_reasoning(reasoning: Any) -> Optional[Dict[str, Any]]:
    """Rodada de auditoria persistida em `reasoning_auditoria` (JSON da rodada)."""
    dados = _parse_json_maybe(reasoning)
    if not isinstance(dados, dict):
        return None
    brutos = dados.get("criterios")
    if not isinstance(brutos, list) or not brutos:
        return None
    criterios = []
    for c in brutos:
        if not isinstance(c, dict):
            continue
        criterios.append(
            {
                "id": int(c.get("id") or len(criterios) + 1),
                "nome": str(c.get("nome") or ""),
                "aprovado": bool(c.get("aprovado")),
                "justificativa": str(c.get("justificativa") or ""),
                "claim_ids": [],
                "source_ids": [],
            }
        )
    if not criterios:
        return None
    return {
        "rodada": int(dados.get("rodada") or 1),
        "criterios": criterios,
        "aprovados": sum(1 for c in criterios if c["aprovado"]),
        "veredito": str(dados.get("veredito") or "").upper(),
        "lacunas": dados.get("lacunas"),
    }


def _resumo_auditoria_markdown(veredito: str, aprovados: int, total: int, criterios, lacunas) -> str:
    linhas = [f"**Veredito:** {veredito or 'EM ANÁLISE'} — {aprovados}/{total} critérios aprovados", ""]
    for c in criterios or []:
        marca = "✓" if c["aprovado"] else "✗"
        nome = f" {c['nome']}" if c.get("nome") else ""
        linhas.append(f"- {marca} **Critério {c['id']}{nome}:** {c['justificativa']}")
    if lacunas:
        linhas += ["", f"**Lacunas:** {lacunas}"]
    return "\n".join(linhas)


_SECAO_PERSONA = re.compile(r"^##\s+(?P<persona>[a-zA-ZÀ-ÿ_ ]+)\s*$", re.M)


def _personas_do_conteudo(conteudo: str) -> List[Dict[str, Any]]:
    """Recorta `## <persona>` do conteúdo coletado para reidratar a trilha."""
    texto = conteudo or ""
    achados = list(_SECAO_PERSONA.finditer(texto))
    personas: List[Dict[str, Any]] = []
    for indice, achado in enumerate(achados):
        inicio = achado.end()
        fim = achados[indice + 1].start() if indice + 1 < len(achados) else len(texto)
        analise = texto[inicio:fim].strip()
        nome = achado.group("persona").strip().lower()
        if not analise:
            continue
        personas.append(
            {
                "persona": nome,
                "analise": analise,
                "urls_fonte": [],
                "urls_lidas": [],
                "queries_executadas": 0,
                "falha_coleta": False,
                "lacunas": None,
            }
        )
    return personas


def _busca_persistida(pesquisa_id: str, coletas: List[Any], pontos: List[Any]) -> Optional[Dict[str, Any]]:
    """SearchResponse reconstruído do banco, para a trilha sobreviver ao F5."""
    if not coletas:
        return None
    ordem = {getattr(p, "ponto_id", None): getattr(p, "ponto_n", i + 1) for i, p in enumerate(pontos or [])}
    status_ponto = {getattr(p, "ponto_id", None): getattr(p, "status", "coletado") for p in pontos or []}
    resumo = []
    for coleta in coletas:
        try:
            urls_lidas = json.loads(coleta.urls_lidas) if coleta.urls_lidas else []
        except Exception:
            urls_lidas = []
        if not isinstance(urls_lidas, list):
            urls_lidas = []
        personas = _personas_do_conteudo(coleta.conteudo_coletado or "")
        resumo.append(
            {
                "ponto_id": coleta.ponto_id,
                "ponto_n": ordem.get(coleta.ponto_id) or len(resumo) + 1,
                "status": status_ponto.get(coleta.ponto_id) or "coletado",
                "falha_coleta": False,
                "total_urls_lidas": len(urls_lidas),
                "total_urls_fonte": len(urls_lidas),
                "tamanho_conteudo_caracteres": len(coleta.conteudo_coletado or ""),
                "tentativas": getattr(coleta, "rodada", 1) or 1,
                "personas": personas,
            }
        )
    return {
        "id_pesquisa": pesquisa_id,
        "total_pontos_processados": len(resumo),
        "status_pesquisa": "coletado",
        "total_falhas_coleta": 0,
        "resumo_coletas": resumo,
    }


def _build_auditoria(pesquisa: Any, pontos: List[Any]) -> Optional[Dict[str, Any]]:
    auditorias = []
    aprovados = 0
    reprovados = 0
    total_pontos = len(pontos) if pontos is not None else 0
    for p in pontos or []:
        def campo(nome):
            return getattr(p, nome, None) if not isinstance(p, dict) else p.get(nome)

        status_p = campo("status")
        ponto_id = campo("ponto_id")
        ponto_n = campo("ponto_n")
        pontos_fracos = campo("pontos_fracos")
        reasoning_auditoria = campo("reasoning_auditoria")

        rodada = _criterios_do_reasoning(reasoning_auditoria)
        if rodada:
            total_criterios = len(rodada["criterios"])
            minimos = int(rodada.get("minimos") or 11)
            veredito = rodada["veredito"] or ("APROVADO" if rodada["aprovados"] >= minimos else "REPROVADO")
            valido = veredito == "APROVADO"
            auditorias.append(
                {
                    "ponto_id": ponto_id,
                    "ponto_n": ponto_n,
                    "status": "aprovado" if valido else "reprovado",
                    "pontuacao_percentual": round(rodada["aprovados"] / max(total_criterios, 1) * 100, 2),
                    "criterios_aprovados": rodada["aprovados"],
                    "criterios_minimos": minimos,
                    "total_criterios": total_criterios,
                    "valido": valido,
                    "criterios": rodada["criterios"],
                    "pontos_fracos": pontos_fracos or rodada.get("lacunas"),
                    "diagnostico": None if valido else rodada.get("lacunas"),
                    "resumo_auditoria": _resumo_auditoria_markdown(
                        veredito, rodada["aprovados"], total_criterios, rodada["criterios"], rodada.get("lacunas")
                    ),
                    "reasoning_auditoria": reasoning_auditoria,
                    "rodada": rodada["rodada"],
                }
            )
            if valido:
                aprovados += 1
            else:
                reprovados += 1
            continue

        if status_p == "aprovado":
            aprovados += 1
            auditorias.append(
                {
                    "ponto_id": ponto_id,
                    "ponto_n": ponto_n,
                    "status": "aprovado",
                    "pontuacao_percentual": 100.0,
                    "criterios_aprovados": 12,
                    "criterios_minimos": 11,
                    "valido": True,
                    "criterios": None,
                    "pontos_fracos": pontos_fracos,
                    "diagnostico": None,
                    "resumo_auditoria": None,
                    "reasoning_auditoria": reasoning_auditoria,
                }
            )
        elif status_p == "reprovado":
            reprovados += 1
            auditorias.append(
                {
                    "ponto_id": ponto_id,
                    "ponto_n": ponto_n,
                    "status": "reprovado",
                    "pontuacao_percentual": 0.0,
                    "criterios_aprovados": 0,
                    "criterios_minimos": 11,
                    "valido": False,
                    "criterios": None,
                    "pontos_fracos": pontos_fracos,
                    "diagnostico": None,
                    "resumo_auditoria": None,
                    "reasoning_auditoria": reasoning_auditoria,
                }
            )

    if not auditorias:
        return None

    id_pesquisa = (
        getattr(pesquisa, "id_pesquisa", None)
        or (pesquisa.get("id_pesquisa") if isinstance(pesquisa, dict) else str(pesquisa))
    )
    status_pesquisa = getattr(pesquisa, "status_pipeline", None) or getattr(pesquisa, "status", None)
    if isinstance(pesquisa, dict):
        status_pesquisa = status_pesquisa or pesquisa.get("status_pipeline") or pesquisa.get("status")

    if len(auditorias) < total_pontos:
        status_geral = "parcial"
        pronto_para_writer = False
    else:
        status_geral = (
            "aprovado"
            if aprovados == total_pontos
            else ("reprovado" if reprovados > 0 and aprovados == 0 else "parcial")
        )
        pronto_para_writer = (
            total_pontos > 0
            and len(auditorias) == total_pontos
            and aprovados == total_pontos
        )

    return {
        "id_pesquisa": id_pesquisa,
        "total_pontos": total_pontos,
        "aprovados": aprovados,
        "reprovados": reprovados,
        "status_geral": status_geral,
        "status_pesquisa": status_pesquisa,
        "pronto_para_writer": pronto_para_writer,
        "auditorias": auditorias,
    }


@router.get("/research/{id_pesquisa}", status_code=status.HTTP_200_OK)
async def get_research_detail(
    id_pesquisa: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    repo = ResearchRepository(session=db)
    pesquisa = await repo.get_research(id_pesquisa)
    if not pesquisa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pesquisa não localizada: {id_pesquisa}",
        )

    pontos = await repo.list_points(id_pesquisa)

    plano_estruturado = _parse_json_maybe(getattr(pesquisa, "plano_estruturado", None))
    preferencias = _extract_preferencias(pesquisa)
    metadados_redacao = _parse_json_maybe(getattr(pesquisa, "metadados_redacao", None))

    pontos_out: List[Dict[str, Any]] = []
    for p in pontos:
        eixo_estruturado = _parse_json_maybe(getattr(p, "eixo_estruturado", None))
        pontos_out.append(
            {
                "ponto_id": p.ponto_id,
                "ponto_n": p.ponto_n,
                "ponto": p.ponto,
                "status": p.status,
                "eixo_estruturado": eixo_estruturado,
            }
        )

    fontes: Optional[FontesResumo] = None
    try:
        service = SourceAccountingService(research_repo=repo)
        fontes_res = await service.get_source_summary(id_pesquisa)
        if fontes_res is not None:
            # Return as dict for easy JSON serialization
            fontes = fontes_res.model_dump() if hasattr(fontes_res, "model_dump") else fontes_res
    except Exception:
        fontes = None

    auditoria = _build_auditoria(pesquisa, pontos)
    try:
        coletas = await repo.get_collected_content(id_pesquisa)
    except Exception:
        coletas = []

    result: Dict[str, Any] = {
        "id": getattr(pesquisa, "id_pesquisa"),
        "id_pesquisa": getattr(pesquisa, "id_pesquisa"),
        "tema": pesquisa.tema,
        "status_pipeline": getattr(pesquisa, "status_pipeline", None),
        "criado_em": pesquisa.criado_em,
        "concluido_em": pesquisa.concluido_em,
        "plano_estruturado": plano_estruturado,
        "pontos": pontos_out,
        "preferencias": preferencias,
        "dossier_final": pesquisa.dossier_final,
        "metadados_redacao": metadados_redacao,
        "fontes": fontes,
        "auditoria": auditoria,
        "busca": _busca_persistida(id_pesquisa, coletas, pontos),
        "tokens_prompt": int(getattr(pesquisa, "tokens_prompt", 0) or 0),
        "tokens_completion": int(getattr(pesquisa, "tokens_completion", 0) or 0),
        "tokens_total": int(getattr(pesquisa, "tokens_total", 0) or 0),
    }
    return result
