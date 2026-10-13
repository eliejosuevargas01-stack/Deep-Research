import uuid
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class InvestigateResponse(BaseModel):
    research_id: uuid.UUID
    status: str = "SCRAPER"
    message: str = "Investigação iniciada em background"


class JinaSearchArgs(BaseModel):
    q: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Consulta de busca a ser executada na Jina",
    )


JINA_SEARCH_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "jina_search",
        "description": "busca na web retornando texto limpo",
        "parameters": {
            "type": "object",
            "properties": {
                "q": {
                    "type": "string",
                    "description": "Consulta de busca a ser executada na Jina",
                }
            },
            "required": ["q"],
        },
    },
}


class PersonaResultPayload(BaseModel):
    result: str = Field(
        ..., min_length=10, description="Síntese analítica do ponto investigado"
    )
    used_urls: List[str] = Field(
        default_factory=list,
        description="Lista de URLs efetivamente utilizadas e citadas na análise",
    )


class StepResultCreate(BaseModel):
    research_id: uuid.UUID
    step_id: uuid.UUID
    step_title: str
    result: str
    used_urls: List[str] = Field(default_factory=list)
    read_urls: List[str] = Field(default_factory=list)
    worker: str
    status: str = "AUDIT_PENDING"
