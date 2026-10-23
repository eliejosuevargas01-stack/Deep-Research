"""Módulo central de orquestração do domínio analítico Deep Research.

Exporta os orquestradores de domínio das 4 etapas do pipeline:
Planner (planejador), Searcher (pesquisador), Auditor (auditor) e Writer (redator).
"""

from app.core.planner import Planner
from app.core.searcher import Searcher
from app.core.auditor import Auditor
from app.core.writer import Writer

__all__ = ["Planner", "Searcher", "Auditor", "Writer"]
