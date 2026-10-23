"""Esquemas Pydantic v2 para o endpoint de auditoria de qualidade (/api/v1/audit).

Derivado de:
- SDD: endpoint-auditoria-de-qualidade.md (RF-01, RF-04, RF-05, RF-06, RF-07, Seção 9)
- PRD: prd.md (RF-005)
- Interfaces: endpoint-audit.md
Atende a T023.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class AuditCriteria(BaseModel):
    """Checklist das 12 perguntas de qualidade avaliadas pelo auditor (RF-04)."""

    clareza_tematica: bool = Field(
        default=True,
        description="O conteúdo aborda objetivamente a questão formulada no ponto?",
    )
    corroboracao_canonica: bool = Field(
        default=True,
        description="Existem fontes primárias verificáveis que sustentam os dados?",
    )
    atualidade: bool = Field(
        default=True,
        description="As informações e marcos citados estão temporalmente vigentes?",
    )
    ausencia_contradicoes: bool = Field(
        default=True,
        description="Os dados internos coletados são coerentes entre si?",
    )
    embasamento_factual: bool = Field(
        default=True,
        description="Declarações estão ancoradas em evidências empíricas e não opiniões vazias?",
    )
    aderencia_escopo: bool = Field(
        default=True,
        description="O conteúdo se atém ao tema sem desvios laterais?",
    )
    profundidade_analitica: bool = Field(
        default=True,
        description="A explicação alcança complexidade suficiente para subsidiar decisão?",
    )
    precisao_numerica: bool = Field(
        default=True,
        description="Métricas, estatísticas e datas citadas possuem unidades e contexto?",
    )
    neutralidade: bool = Field(
        default=True,
        description="O texto preserva tom analítico objetivo e equilibrado?",
    )
    densidade_evidencias: bool = Field(
        default=True,
        description="Há proporção satisfatória entre afirmações e fontes citadas?",
    )
    declaracao_incertezas: bool = Field(
        default=True,
        description="Lacunas e divergências na literatura são expressamente apontadas?",
    )
    solidez_logica: bool = Field(
        default=True,
        description="As conclusões decorrem necessariamente dos fatos apresentados?",
    )


class AuditEvaluationResult(BaseModel):
    """Resposta estruturada do LLM forte para avaliação das 12 perguntas de qualidade (RF-04, RF-05)."""

    status: str = Field(
        ...,
        description="Deliberação da auditoria: aprovado ou reprovado",
    )
    pontos_fracos: Optional[str] = Field(
        default=None,
        description="Descrição detalhada das fraquezas ou lacunas identificadas",
    )
    resumo_auditoria: Optional[str] = Field(
        default=None,
        description="Resumo analítico do parecer de auditoria",
    )
    criterios: Optional[AuditCriteria] = Field(
        default=None,
        description="Avaliação detalhada dos 12 critérios de qualidade",
    )


class AuditItem(BaseModel):
    """Parecer de auditoria consolidado para um ponto individual (RF-05, RF-07)."""

    ponto_id: str = Field(
        ...,
        description="Identificador do ponto investigado (UUID)",
    )
    ponto_n: int = Field(
        ...,
        ge=1,
        description="Número de ordem do ponto investigado",
    )
    status: str = Field(
        ...,
        description="Deliberação de qualidade: aprovado ou reprovado",
    )
    pontos_fracos: Optional[str] = Field(
        default=None,
        description="Registro das fragilidades apontadas em caso de reprovação",
    )
    reasoning_auditoria: Optional[str] = Field(
        default=None,
        description="Cadeia de raciocínio analítico emitida pelo auditor durante a avaliação",
    )
    resumo_auditoria: Optional[str] = Field(
        default=None,
        description="Resumo do parecer técnico da auditoria",
    )


class AuditRequest(BaseModel):
    """Contrato de entrada para a etapa de auditoria de qualidade (RF-01)."""

    id_pesquisa: str = Field(
        ...,
        min_length=1,
        description="Identificador canônico da pesquisa (UUID)",
    )


class AuditResponse(BaseModel):
    """Contrato de saída com o parecer consolidado da auditoria (RF-07)."""

    id_pesquisa: str = Field(
        ...,
        description="Identificador canônico da pesquisa (UUID)",
    )
    total_pontos: int = Field(
        ...,
        ge=0,
        description="Total de pontos submetidos à auditoria",
    )
    aprovados: int = Field(
        ...,
        ge=0,
        description="Quantidade de pontos aprovados",
    )
    reprovados: int = Field(
        ...,
        ge=0,
        description="Quantidade de pontos reprovados",
    )
    status_geral: str = Field(
        default="auditado",
        description="Status geral da etapa de auditoria",
    )
    auditorias: List[AuditItem] = Field(
        ...,
        description="Listagem estruturada das deliberações de auditoria por ponto",
    )

    # ponytail: suporte a re-auditoria com pesos diferenciados por critério pode ser adicionado aqui
