"""Endpoint para hidratação completa de pesquisa por ID.

Permite reidratar o frontend sem histórico local (deep link).
"""
from __future__ import annotations

import json
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


def _build_auditoria(pesquisa: Any, pontos: List[Any]) -> Optional[Dict[str, Any]]:
    auditorias = []
    aprovados = 0
    reprovados = 0
    total_pontos = len(pontos) if pontos is not None else 0
    for p in pontos or []:
        status_p = getattr(p, "status", None) if not isinstance(p, dict) else p.get("status")
        ponto_id = getattr(p, "ponto_id", None) if not isinstance(p, dict) else p.get("ponto_id")
        ponto_n = getattr(p, "ponto_n", None) if not isinstance(p, dict) else p.get("ponto_n")
        pontos_fracos = getattr(p, "pontos_fracos", None) if not isinstance(p, dict) else p.get("pontos_fracos")
        reasoning_auditoria = (
            getattr(p, "reasoning_auditoria", None)
            if not isinstance(p, dict)
            else p.get("reasoning_auditoria")
        )

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
        "tokens_prompt": int(getattr(pesquisa, "tokens_prompt", 0) or 0),
        "tokens_completion": int(getattr(pesquisa, "tokens_completion", 0) or 0),
        "tokens_total": int(getattr(pesquisa, "tokens_total", 0) or 0),
    }
    return result
