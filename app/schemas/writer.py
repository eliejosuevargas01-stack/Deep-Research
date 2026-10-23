"""Esquemas Pydantic v2 para o endpoint de redação do dossiê (/api/v1/writer).

Derivado de:
- SDD: endpoint-redacao-do-dossier.md (RF-01, RF-03, RF-05, RF-06, RF-07, Seção 9)
- PRD: prd.md (RF-006, Seção 8)
- Interfaces: endpoint-writer.md
Atende a T024.
"""

from typing import Optional
from pydantic import BaseModel, Field


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
    tentativas: int = Field(
        default=0,
        ge=0,
        description="Número de tentativas de envio executadas pelo cliente de webhook",
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


class WriterResponse(BaseModel):
    """Contrato de saída com o dossiê analítico e metadados de despacho (RF-01, RF-06, RF-07)."""

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
        default="concluido",
        description="Status da finalização da pesquisa (concluido)",
    )
    total_caracteres_dossier: int = Field(
        ...,
        ge=0,
        description="Contagem de caracteres do dossiê analítico consolidado",
    )
    concluido_em: str = Field(
        ...,
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
        description="Raciocínio lógico analítico gerado pelo modelo durante a redação do dossiê",
    )
    dossier_resumo: Optional[str] = Field(
        default=None,
        description="Resumo executivo do dossiê ou conteúdo compatível para interfaces e testes",
    )
