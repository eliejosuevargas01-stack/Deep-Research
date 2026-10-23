"""Esquemas Pydantic v2 para o endpoint de planejamento (/api/v1/plan).

Derivado de:
- SDD: endpoint-plano-de-investigacao.md (RF-01, RF-02, RF-05, RF-06, EC-01, Seção 9)
- PRD: prd.md (RF-001, RF-002, Seção 8)
- Interfaces: endpoint-plan.md
Atende a T021.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class PlanPontoItem(BaseModel):
    """Ponto focal de investigação formulado pelo planejador (RF-05, RF-06)."""

    ponto_id: str = Field(
        ...,
        description="Identificador exclusivo do ponto de investigação (UUID)",
    )
    ponto_n: int = Field(
        ...,
        ge=1,
        description="Número sequencial do ponto (1 até N)",
    )
    ponto: str = Field(
        ...,
        min_length=1,
        description="Descrição textual do ponto de investigação",
    )
    status: str = Field(
        default="pendente",
        description="Status do ponto (pendente | em_andamento | aprovado | reprovado)",
    )
    pontos_fracos: Optional[str] = Field(
        default=None,
        description="Lacunas ou fraquezas identificadas em etapas posteriores",
    )
    reasoning_planejamento: Optional[str] = Field(
        default=None,
        description="Raciocínio lógico do modelo ao formular o ponto",
    )
    reasoning_auditoria: Optional[str] = Field(
        default=None,
        description="Raciocínio analítico gerado na auditoria do ponto",
    )


# Alias de conveniência para importações compatíveis
PlanItem = PlanPontoItem


class PlanRequest(BaseModel):
    """Contrato de entrada para solicitação de plano investigativo (RF-01, EC-01)."""

    tema: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Tema central ou briefing para investigação (mínimo 5 e máximo 500 caracteres)",
    )
    id_pesquisa: Optional[str] = Field(
        default=None,
        description="Identificador opcional de pesquisa pré-existente (UUID)",
    )
    async_execute: bool = Field(
        default=False,
        description="Se True, dispara o pipeline contínuo assíncrono em background até o webhook de callback",
    )
    callback_url: Optional[str] = Field(
        default=None,
        description="URL de webhook de callback específica para entrega assíncrona deste relatório",
    )


class PlanResponse(BaseModel):
    """Contrato de saída com o plano gerado e lista estruturada de pontos (RF-01, RF-06)."""

    id_pesquisa: str = Field(
        ...,
        description="Identificador canônico da investigação (UUID)",
    )
    tema: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Tema investigado",
    )
    n_pontos: int = Field(
        ...,
        ge=1,
        description="Quantidade total de pontos gerados",
    )
    criado_em: str = Field(
        ...,
        description="Data e hora de registro no formato ISO 8601",
    )
    pontos: List[PlanPontoItem] = Field(
        ...,
        description="Coleção dos N pontos focais de investigação ordenados",
    )
    status_pipeline: Optional[str] = Field(
        default="planejado",
        description="Estágio atual de execução no pipeline contínuo",
    )


class PlanAsyncResponse(BaseModel):
    """Resposta imediata quando async_execute=True informando o disparo em background."""

    id_pesquisa: str
    tema: str
    status: str = "iniciado"
    status_pipeline: str = "planejado"
    mensagem: str = "Pipeline assíncrono iniciado com sucesso. O dossiê completo será entregue no webhook configurado."
    n_pontos: int
    callback_url: Optional[str] = None
    pontos: List[PlanPontoItem]

    # ponytail: validação de unicidade de ponto_n no array pode ser adicionada se o LLM gerar duplicatas
