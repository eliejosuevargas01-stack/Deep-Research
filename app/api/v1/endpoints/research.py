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


def _build_auditoria(pesquisa_id: str, pontos: List[Ponto]) -> Optional[Dict[str, Any]]:
    auditorias = []
    aprovados = 0
    reprovados = 0
    for p in pontos:
        # Considerar aprovado/reprovado com base no status do ponto
        status_p = getattr(p, "status", None)
        if status_p == "aprovado":
            aprovados += 1
            auditorias.append(
                {
                    "ponto_id": p.ponto_id,
                    "ponto_n": p.ponto_n,
                    "status": "aprovado",
                    "pontuacao_percentual": 100,
                    "criterios_aprovados": 0,
                    "criterios_minimos": 0,
                    "valido": True,
                    "criterios": None,
                    "pontos_fracos": getattr(p, "pontos_fracos", None),
                    "diagnostico": None,
                    "resumo_auditoria": None,
                    "reasoning_auditoria": getattr(p, "reasoning_auditoria", None),
                }
            )
        elif status_p == "reprovado":
            reprovados += 1
            auditorias.append(
                {
                    "ponto_id": p.ponto_id,
                    "ponto_n": p.ponto_n,
                    "status": "reprovado",
                    "pontuacao_percentual": 0,
                    "criterios_aprovados": 0,
                    "criterios_minimos": 0,
                    "valido": False,
                    "criterios": None,
                    "pontos_fracos": getattr(p, "pontos_fracos", None),
                    "diagnostico": None,
                    "resumo_auditoria": None,
                    "reasoning_auditoria": getattr(p, "reasoning_auditoria", None),
                }
            )
    if not auditorias:
        return None
    total = len(auditorias)
    status_geral = "aprovado" if aprovados == total else ("reprovado" if reprovados > 0 and aprovados == 0 else "parcial")
    return {
        "id_pesquisa": pesquisa_id,
        "total_pontos": total,
        "aprovados": aprovados,
        "reprovados": reprovados,
        "status_geral": status_geral,
        "status_pesquisa": getattr(pesquisa_id, "status_pesquisa", None),
        "pronto_para_writer": aprovados == total and total > 0,
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

    auditoria = _build_auditoria(id_pesquisa, pontos)

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
