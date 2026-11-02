"""Esquemas Pydantic v2 para o endpoint de busca com personas (/api/v1/search).

Derivado de:
- SDD: endpoint-busca-com-personas.md (RF-01, RF-07, RF-08, Seção 9)
- PRD: prd.md (RF-003, RF-004)
- Interfaces: endpoint-search.md
Atende a T022.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.execution import ExecutionMode


class FonteColetaItem(BaseModel):
    """URL do catálogo de coleta com uso e metadados públicos (PRD v3)."""

    url: str = Field(..., description="URL canônica da fonte")
    uso: Literal["utilizada", "lida_nao_utilizada"] = Field(
        ...,
        description="utilizada: eleita como referência pela persona; lida_nao_utilizada: apenas lida",
    )
    titulo: Optional[str] = Field(default=None, description="Título público da página quando disponível")
    data_fonte: Optional[str] = Field(default=None, description="Data de publicação observada na fonte")
    status: Literal["read_ok", "snippet_only"] = Field(
        default="read_ok",
        description=(
            "read_ok: página lida integralmente; snippet_only: URL eleita vista apenas no resultado "
            "de busca (PRD v3, RF-004-D)"
        ),
    )


class PersonaColetaItem(BaseModel):
    """Conteúdo analítico e fontes de uma persona investigativa."""

    persona: str = Field(
        ...,
        description="Nome da persona analítica (historiador, visionario, cetico, futurista)",
    )
    analise: str = Field(
        ...,
        description="Síntese analítica detalhada produzida pela persona",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Cadeia de raciocínio lógico gerada pelo modelo durante a busca da persona",
    )
    urls_fonte: List[str] = Field(
        default_factory=list,
        description="Lista de URLs canônicas selecionadas como referência pela persona",
    )
    urls_lidas: List[str] = Field(
        default_factory=list,
        description="Lista de URLs efetivamente lidas pela persona (status read_ok)",
    )
    fontes: List[FonteColetaItem] = Field(
        default_factory=list,
        description="Fontes da persona com uso classificado já na fase de busca",
    )
    queries_executadas: int = Field(
        default=0,
        ge=0,
        description="Quantidade de queries agênticas realizadas pela persona",
    )
    falha_coleta: bool = Field(
        default=False,
        description="True quando a persona não obteve nenhuma evidência web (RF-03)",
    )
    diagnostico: Optional[str] = Field(
        default=None,
        description="Diagnóstico da falha de coleta com categoria e ação corretiva (RF-04)",
    )
    conclusoes: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Conclusões estruturadas com IDs de evidência canônica (DR-009)",
    )
    lacunas: Optional[List[str]] = Field(
        default=None,
        description="Lacunas de informação explicitadas pela persona",
    )
    diario_acoes: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Diário operacional de ações backend executadas",
    )
    motivo_parada: Optional[str] = Field(
        default=None,
        description="Motivo explícito de encerramento da busca",
    )
    envelopes: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Metadados públicos higienizados dos envelopes das chamadas LLM da persona",
    )


class SearchColetaResumo(BaseModel):
    """Resumo detalhado da coleta web de um ponto investigativo com conteúdo por persona (RF-08)."""

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
        default="coletado",
        description="Status do ponto após a varredura (coletado ou falha_coleta)",
    )
    falha_coleta: bool = Field(
        default=False,
        description="True quando nenhuma URL foi efetivamente lida no ponto (RF-03)",
    )
    diagnostico: Optional[str] = Field(
        default=None,
        description="Diagnóstico acionável da falha de coleta do ponto (RF-04)",
    )
    total_urls_lidas: int = Field(
        ...,
        ge=0,
        description="Total de URLs consultadas durante o processo de busca",
    )
    total_urls_fonte: int = Field(
        ...,
        ge=0,
        description="Total de URLs canônicas selecionadas como referência",
    )
    tamanho_conteudo_caracteres: int = Field(
        ...,
        ge=0,
        description="Volume textual dos resumos acumulados em caracteres",
    )
    tentativas: int = Field(
        default=1,
        ge=0,
        description="Quantidade de passagens do ponto pelo endpoint de busca (1 inicial + até 3 retries)",
    )
    personas: List[PersonaColetaItem] = Field(
        default_factory=list,
        description="Conteúdo analítico e fontes estruturadas por persona",
    )
    conteudo_relevante: Optional[str] = Field(
        default=None,
        description="Conteúdo analítico consolidado das 4 personas",
    )
    fontes: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Catálogo de URLs do ponto com uso classificado (sem corpo bruto)",
    )
    recencia: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Resumo da política de recência, data de referência e data da fonte mais recente",
    )


# Aliases de conveniência para importações compatíveis
SearchItemSummary = SearchColetaResumo
SearchPontoSummary = SearchColetaResumo


class SearchRequest(BaseModel):
    """Contrato de entrada para a etapa de busca paralela com personas (RF-01)."""

    id_pesquisa: str = Field(
        ...,
        min_length=1,
        description="Identificador canônico da pesquisa (UUID)",
    )
    ponto_id: Optional[str] = Field(
        default=None,
        description="Filtro opcional para reprocessamento exclusivo de um ponto (UUID)",
    )
    personas: Optional[List[str]] = Field(
        default=None,
        description="Filtro opcional de personas para re-tentativas focadas",
    )
    execution_mode: ExecutionMode = Field(
        default="parallel",
        description=(
            "Modo de execução dos pontos de pesquisa: 'parallel' processa os N pontos "
            "concorrentemente; 'sequential' processa um ponto por vez, em ordem de ponto_n "
            "(PRD v2, invariante I-3). Valor inválido é rejeitado com 422."
        ),
    )


class SearchResponse(BaseModel):
    """Contrato de saída com o sumário de processamento da busca (RF-08)."""

    id_pesquisa: str = Field(
        ...,
        description="Identificador canônico da pesquisa (UUID)",
    )
    total_pontos_processados: int = Field(
        ...,
        ge=0,
        description="Total de pontos processados pelos trabalhadores em paralelo",
    )
    status_pesquisa: str = Field(
        default="coletado",
        description="Status resultante da pesquisa (coletado)",
    )
    total_falhas_coleta: int = Field(
        default=0,
        ge=0,
        description="Total de pontos sem nenhuma evidência web coletada (RF-03)",
    )
    resumo_coletas: List[SearchColetaResumo] = Field(
        ...,
        description="Sumário detalhado das fontes e conteúdo por ponto",
    )

    # ponytail: métricas de custo de tokens e tempo por persona podem ser adicionadas para telemetria
