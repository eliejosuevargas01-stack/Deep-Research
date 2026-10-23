"""Esquemas Pydantic v2 para o endpoint de busca com personas (/api/v1/search).

Derivado de:
- SDD: endpoint-busca-com-personas.md (RF-01, RF-07, RF-08, Seção 9)
- PRD: prd.md (RF-003, RF-004)
- Interfaces: endpoint-search.md
Atende a T022.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


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
        description="Volume textual integral coletado em caracteres",
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
