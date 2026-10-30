"""Esquemas Pydantic v2 para o endpoint de redação do dossiê (/api/v1/writer).

Derivado de:
- SDD: endpoint-redacao-do-dossier.md (RF-01, RF-03, RF-05, RF-06, RF-07, Seção 9)
- Adendo v6: addendum-confiabilidade-20261025-v6-writer.md
- PRD: prd.md (RF-006, Seção 8)
- Interfaces: endpoint-writer.md
Atende a W06, W10, W11 e T024.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, StrictBool, StrictInt, field_validator, model_validator

from app.schemas.sources import FontesResumo


class WebhookEntregaMetadata(BaseModel):
    """Metadados de despacho e entrega do dossiê via webhook HTTP POST (RF-07, RF-10)."""

    url: Optional[str] = Field(
        default=None,
        description="URL de destino do webhook de callback cadastrada (opcional no modo síncrono)",
    )
    status: str = Field(
        default="nao_aplicavel",
        description="Status da entrega (entregue | pendente_reenvio | falha_definitiva | nao_aplicavel)",
    )
    http_status_code: Optional[int] = Field(
        default=None,
        description="Código de status HTTP retornado pelo servidor de destino do webhook",
    )
    tentativas: Optional[int] = Field(
        default=0,
        ge=0,
        description=(
            "Número de tentativas de envio executadas pelo cliente de webhook; "
            "None registra entrega NÃO observada (quantidade desconhecida, W07 callback)"
        ),
    )
    detalhes_falha: Optional[str] = Field(
        default=None,
        description="Mensagem de erro descritiva em caso de falha definitiva de despacho",
    )


class WriterRequest(BaseModel):
    """Contrato de entrada para a etapa de redação final do dossiê (RF-01)."""

    id_pesquisa: str = Field(
        ...,
        min_length=1,
        description="Identificador canônico da pesquisa (UUID)",
    )


class ArticleCriterionDetail(BaseModel):
    """Item individual do vetor tipado dos 12 critérios de qualidade do artigo (W06)."""

    id: StrictInt = Field(..., ge=1, le=12, description="ID ordinal estrito do critério (1..12)")
    aprovado: StrictBool = Field(..., description="Deliberação booleana estrita (sem defaults)")
    justificativa: str = Field(..., min_length=1, description="Justificativa analítica substantiva")
    claim_ids: List[str] = Field(..., description="IDs de alegações/claims referenciadas (obrigatório, vazio permitido apenas se não factual)")
    source_ids: List[str] = Field(..., description="IDs de fontes referenciadas (obrigatório, vazio permitido apenas se não factual)")
    correcao: Optional[str] = Field(default=None, description="Ação de correção recomendada (exigida quando reprovado)")

    @field_validator("justificativa")
    @classmethod
    def validate_justificativa_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("O campo 'justificativa' não pode ser vazio.")
        return v.strip()

    @model_validator(mode="after")
    def validate_correcao_when_reproved(self) -> "ArticleCriterionDetail":
        if self.aprovado is False:
            if not self.correcao or not str(self.correcao).strip():
                raise ValueError(
                    f"Critério {self.id} foi reprovado, logo o campo 'correcao' é estritamente obrigatório."
                )
        return self


class ArticleEvaluationResult(BaseModel):
    """Resposta estruturada do LLM forte para avaliação das 12 perguntas de qualidade do artigo (W06)."""

    criterios: List[ArticleCriterionDetail] = Field(
        ...,
        description="Vetor estruturado contendo exatamente os 12 critérios com IDs 1..12 em ordem",
    )
    resumo_avaliacao: Optional[str] = Field(
        default=None,
        description="Resumo do parecer da avaliação da redação",
    )

    @field_validator("criterios")
    @classmethod
    def validate_criterios_order_and_count(cls, v: List[ArticleCriterionDetail]) -> List[ArticleCriterionDetail]:
        if len(v) != 12:
            raise ValueError(f"O vetor de critérios deve conter exatamente 12 itens, mas recebeu {len(v)}.")
        ids = [c.id for c in v]
        if ids != list(range(1, 13)):
            raise ValueError(f"Os IDs dos critérios devem ser ordinais de 1 a 12 estritos e em ordem: {ids}")
        return v


class WriterResponse(BaseModel):
    """Contrato de saída com o dossiê analítico e metadados de despacho (RF-01, RF-06, RF-07, W11)."""

    id_pesquisa: str = Field(
        ...,
        description="Identificador canônico da pesquisa (UUID)",
    )
    tema: str = Field(
        ...,
        min_length=1,
        description="Tema investigado consolidado no dossiê",
    )
    status: str = Field(
        ...,
        description="Status da finalização da pesquisa (concluido | incompleto | falha)",
    )
    total_caracteres_dossier: int = Field(
        default=0,
        ge=0,
        description="Contagem de caracteres do dossiê analítico consolidado",
    )
    concluido_em: Optional[str] = Field(
        default=None,
        description="Data e hora de conclusão no formato ISO 8601",
    )
    webhook_entrega: Optional[WebhookEntregaMetadata] = Field(
        default=None,
        description="Metadados de entrega e resposta do webhook de callback (opcional no modo síncrono)",
    )
    dossier_final: Optional[str] = Field(
        default=None,
        description="Texto integral do dossiê analítico em Markdown com fontes canônicas conforme spec SDD",
    )
    reasoning_dossier: Optional[str] = Field(
        default=None,
        description="Raciocínio lógico analítico (nunca exposto publicamente para conformidade com W11)",
    )
    dossier_resumo: Optional[str] = Field(
        default=None,
        description="Resumo executivo do dossiê ou conteúdo compatível para interfaces e testes",
    )
    diagnostico: Optional[str] = Field(
        default=None,
        description="Diagnóstico técnico explicativo em caso de incompletude ou reparo",
    )
    qualidade_artigo: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Resultados consolidados da avaliação semântica do artigo (corte 11/12)",
    )
    metadados: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadados públicos operacionais da redação",
    )
    fontes: Optional[FontesResumo] = Field(
        default=None,
        description="Resumo analítico das fontes consultadas, utilizadas e não utilizadas",
    )
