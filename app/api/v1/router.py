"""Roteador unificado da API v1 agregando endpoints operacionais e administrativos.

Atende a T038 e DT-01.
"""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import admin, audit, pipeline, plan, search, writer
from app.core.security import verify_api_key

api_router = APIRouter(dependencies=[Depends(verify_api_key)])

# Endpoints operacionais, administrativos e de continuidade do pipeline
api_router.include_router(plan.router, tags=["plan"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(audit.router, tags=["audit"])
api_router.include_router(writer.router, tags=["writer"])
api_router.include_router(pipeline.router, tags=["pipeline"])
api_router.include_router(admin.router, tags=["admin"])
