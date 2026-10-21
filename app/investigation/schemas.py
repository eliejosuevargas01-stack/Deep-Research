import uuid
from typing import Any, Dict, List
from pydantic import BaseModel, Field, field_validator


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


class CitationItem(BaseModel):
    claim: str = Field(..., min_length=1, description="Afirmação ou fato sustentado")
    exact_quote: str = Field(..., min_length=1, description="Citação verbatim exata do corpo entregue")
    source_url: str = Field(..., min_length=1, description="URL pública da fonte")
    source_title: str = Field(default="", description="Título da fonte")


class PersonaResultPayload(BaseModel):
    result: str = Field(
        ..., min_length=10, description="Síntese analítica do ponto investigado"
    )
    citations: List[CitationItem] = Field(
        default_factory=list,
        description="Lista de citações estruturadas verificadas",
    )
    used_urls: List[str] = Field(
        default_factory=list,
        description="Lista de URLs efetivamente utilizadas e citadas na análise",
    )

    @field_validator("result")
    @classmethod
    def validate_non_whitespace_result(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("result não pode ser vazio ou espaço em branco")
        return v


class StepResultCreate(BaseModel):
    research_id: uuid.UUID
    step_id: uuid.UUID
    step_title: str
    result: str = Field(..., min_length=1)
    used_urls: List[str] = Field(default_factory=list)
    read_urls: List[str] = Field(default_factory=list)
    worker: str
    status: str = "AUDIT_PENDING"

    @field_validator("result")
    @classmethod
    def validate_non_whitespace_result(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("result não pode ser vazio ou espaço em branco")
        return v
