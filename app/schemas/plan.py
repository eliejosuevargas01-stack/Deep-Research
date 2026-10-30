"""Esquemas Pydantic v2 para o endpoint de planejamento (/api/v1/plan).

Derivado de:
- SDD: endpoint-plano-de-investigacao.md (RF-01, RF-02, RF-05, RF-06, EC-01, Seção 9)
- PRD: prd.md (RF-001, RF-002, Seção 8)
- DR-006, DR-014, DR-015: Plano estruturado com perguntas, hipóteses e investigabilidade
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.schemas.execution import ExecutionMode


class PlanoEixo(BaseModel):
    """Eixo investigativo estruturado e pesquisável (DR-006)."""

    pergunta_principal: str = Field(
        ...,
        min_length=5,
        description="Questão investigativa central a ser demonstrada por evidências",
    )
    subperguntas: List[str] = Field(
        ...,
        min_length=1,
        description="Perguntas secundárias operacionais para aprofundamento (obrigatório)",
    )
    hipoteses: List[str] = Field(
        ...,
        min_length=1,
        description="Hipóteses falseáveis a testar no Search (obrigatório, lista não vazia)",
    )
    consultas_iniciais: List[str] = Field(
        ...,
        min_length=1,
        description="Consultas preliminares sugeridas para as ferramentas de busca (obrigatório, lista não vazia)",
    )
    fontes_primarias_desejadas: List[str] = Field(
        ...,
        min_length=1,
        description="Tipologia de fontes canônicas prioritárias (obrigatório, lista não vazia)",
    )
    riscos_de_vies: List[str] = Field(
        ...,
        min_length=1,
        description="Vieses potenciais na interpretação ou cobertura do tema (obrigatório, lista não vazia)",
    )
    evidencias_que_refutariam: List[str] = Field(
        ...,
        min_length=1,
        description="Fatos ou evidências que derrubariam as hipóteses iniciais (obrigatório, lista não vazia)",
    )
    criterio_de_conclusao: str = Field(
        ...,
        min_length=5,
        description="Condição observável para considerar a investigação do eixo encerrada",
    )
    investigabilidade: str = Field(
        ...,
        min_length=5,
        description="Justificativa de como obter evidências públicas e verificáveis",
    )
    eixo_essencial: bool = Field(
        ...,
        description="Indica se o eixo é nuclear para a pergunta ou contextual/secundário",
    )

    @field_validator("pergunta_principal", mode="before")
    @classmethod
    def validate_pergunta_principal(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("pergunta_principal deve ser uma string.")
        s = v.strip()
        if len(s) < 5:
            raise ValueError("pergunta_principal deve ter pelo menos 5 caracteres.")
        if re.match(r"^\d+$", s):
            raise ValueError("pergunta_principal não pode ser composta exclusivamente por dígitos numéricos.")
        return s

    @field_validator("criterio_de_conclusao", "investigabilidade", mode="before")
    @classmethod
    def validate_mandatory_strings(cls, v: Any, info: ValidationInfo) -> str:
        if not isinstance(v, str):
            raise ValueError(f"{info.field_name} deve ser uma string.")
        s = v.strip()
        if len(s) < 5:
            raise ValueError(f"{info.field_name} deve ter pelo menos 5 caracteres.")
        return s

    @field_validator("eixo_essencial", mode="before")
    @classmethod
    def validate_eixo_essencial(cls, v: Any) -> bool:
        if type(v) is not bool:
            raise ValueError("eixo_essencial deve ser estritamente um valor booleano (True ou False).")
        return v

    @field_validator(
        "subperguntas",
        "hipoteses",
        "consultas_iniciais",
        "fontes_primarias_desejadas",
        "riscos_de_vies",
        "evidencias_que_refutariam",
        mode="before",
    )
    @classmethod
    def validate_string_list(cls, v: Any, info: ValidationInfo) -> List[str]:
        if not isinstance(v, list):
            raise ValueError(f"{info.field_name} deve ser uma lista de strings, não {type(v).__name__}.")
        result: List[str] = []
        for idx, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Item {idx} de {info.field_name} deve ser uma string não vazia.")
            result.append(item.strip())
        if info.field_name in (
            "hipoteses",
            "consultas_iniciais",
            "fontes_primarias_desejadas",
            "evidencias_que_refutariam",
            "subperguntas",
            "riscos_de_vies",
        ):
            if len(result) == 0:
                raise ValueError(f"{info.field_name} é um campo investigativo essencial e não pode ser uma lista vazia.")
        return result


class PlanoInvestigacao(BaseModel):
    """Contrato completo do plano investigativo estruturado (DR-006)."""

    pedido_original: str = Field(
        ...,
        min_length=3,
        description="Texto integral do pedido formulado pelo usuário",
    )
    pedido_normalizado: str = Field(
        ...,
        min_length=3,
        description="Interpretação operacional do escopo da investigação",
    )
    publico: str = Field(
        ...,
        min_length=2,
        description="Público-alvo explicitado no pedido (ex: criança de 5 anos, leigo, técnico)",
    )
    formato_entrega: str = Field(
        ...,
        min_length=3,
        description="Formato de entrega compatível com o público e intenção",
    )
    recorte_temporal: Optional[str] = Field(
        default=None,
        description="Delimitação temporal aplicável ao escopo da investigação",
    )
    data_referencia: Optional[str] = Field(
        default=None,
        description="Data de referência canônica da pesquisa no formato YYYY-MM-DD",
    )
    politica_recencia: Optional[str] = Field(
        default=None,
        description="Política temporal aplicada: recente | 24h | 7d | 30d | 12m | historico",
    )
    pressupostos: List[str] = Field(
        default_factory=list,
        description="Premissas assumidas antes da busca de evidências (opcional, lista de strings)",
    )
    ambiguidades: List[str] = Field(
        default_factory=list,
        description="Ambiguidades toleradas ou mapeadas (opcional, lista de strings)",
    )
    pergunta_de_esclarecimento: Optional[str] = Field(
        default=None,
        description="Pergunta de esclarecimento caso haja ambiguidade bloqueante",
    )
    eixos: List[PlanoEixo] = Field(
        ...,
        min_length=1,
        description="Coleção de eixos investigativos complementares e não redundantes",
    )

    @field_validator("pressupostos", "ambiguidades", mode="before")
    @classmethod
    def validate_optional_string_list(cls, v: Any, info: ValidationInfo) -> List[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError(f"{info.field_name} deve ser uma lista de strings.")
        result: List[str] = []
        for idx, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Item {idx} de {info.field_name} deve ser uma string não vazia.")
            result.append(item.strip())
        return result


class PlanPontoItem(BaseModel):
    """Ponto focal de investigação formulado pelo planejador (compatibilidade e projeção)."""

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
    eixo_estruturado: Optional[PlanoEixo] = Field(
        default=None,
        description="Dados estruturados completos do eixo investigativo (DR-006)",
    )


PlanItem = PlanPontoItem

ALLOWED_SEARCH_PERSONAS_SET = {"historiador", "visionario", "cetico", "futurista"}


class PlanPreferencias(BaseModel):
    """Snapshot de preferências efetivas aplicadas à pesquisa."""

    n_pontos: int = Field(..., ge=1, description="Quantidade de pontos investigativos selecionada")
    personas: List[str] = Field(..., min_length=1, description="Subconjunto de personas analíticas de busca")
    recencia: Optional[str] = Field(
        default=None,
        description="Política de recência solicitada (auto | recente | 24h | 7d | 30d | 12m | historico)",
    )
    data_referencia: Optional[str] = Field(
        default=None,
        description="Data de referência em que a pesquisa foi planejada (YYYY-MM-DD)",
    )
    execution_mode: ExecutionMode = Field(
        default="parallel",
        description="Modo de execução dos pontos de pesquisa propagado ao pipeline (parallel | sequential)",
    )


class PlanRequest(BaseModel):
    """Contrato de entrada para solicitação de plano investigativo (RF-01, EC-01)."""

    tema: str = Field(
        ...,
        min_length=5,
        description=(
            "Tema central ou briefing para investigação (mínimo 5 caracteres). "
            "Sem limite máximo: a entrada do plano não pode ser truncada nem rejeitada "
            "por tamanho (PRD v2, invariante I-2)."
        ),
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
    n_pontos: Optional[int] = Field(
        default=None,
        description="Quantidade estrita de pontos investigativos (inteiro positivo >= 1)",
    )
    personas: Optional[List[str]] = Field(
        default=None,
        description="Subconjunto não vazio e único de personas de busca permitidas",
    )
    execution_mode: ExecutionMode = Field(
        default="parallel",
        description=(
            "Modo de execução dos pontos de pesquisa (parallel | sequential). "
            "Governa o pipeline assíncrono quando async_execute=true (PRD v2, I-3)."
        ),
    )
    recencia: Optional[str] = Field(
        default=None,
        description=(
            "Política de recência da pesquisa. 'auto' (default) usa o estado mais recente "
            "quando o tema não fixa recorte histórico; 'recente' força o estado atual; "
            "24h/7d/30d/12m impõem janela; 'historico' preserva o recorte do pedido."
        ),
    )

    @field_validator("recencia", mode="before")
    @classmethod
    def validate_recencia(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str) or not v.strip():
            raise ValueError("recencia deve ser uma string não vazia.")
        allowed = {"auto", "recente", "24h", "7d", "30d", "12m", "historico", "histórico"}
        normalized = v.strip().lower()
        if normalized not in allowed:
            raise ValueError(
                f"recencia inválida: '{v}'. Permitidas: {sorted(allowed)}."
            )
        return "historico" if normalized == "histórico" else normalized

    @field_validator("n_pontos", mode="before")
    @classmethod
    def validate_strict_n_pontos(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if type(v) is bool:
            raise ValueError("n_pontos não pode ser booleano; deve ser um número inteiro positivo.")
        if isinstance(v, float):
            raise ValueError("n_pontos não pode ser float; deve ser um número inteiro positivo.")
        if not isinstance(v, int):
            raise ValueError("n_pontos deve ser um número inteiro estrito.")
        if v < 1:
            raise ValueError("n_pontos deve ser um número inteiro estritamente positivo (>= 1).")
        return v

    @field_validator("personas", mode="before")
    @classmethod
    def validate_search_personas(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("personas deve ser uma lista de strings.")
        if len(v) == 0:
            raise ValueError("personas não pode ser uma lista vazia quando informada.")
        cleaned = []
        for idx, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Item {idx} de personas deve ser uma string não vazia.")
            p = item.strip().lower()
            if p not in ALLOWED_SEARCH_PERSONAS_SET:
                raise ValueError(
                    f"Persona inválida: '{p}'. Permitidas exclusivamente: {sorted(list(ALLOWED_SEARCH_PERSONAS_SET))}."
                )
            cleaned.append(p)
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Personas duplicadas não são permitidas. Cada persona deve ser única.")
        return cleaned


class PlanResponse(BaseModel):
    """Contrato de saída com o plano gerado e lista estruturada de pontos (RF-01, RF-06, DR-015)."""

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
    plano_estruturado: Optional[PlanoInvestigacao] = Field(
        default=None,
        description="Plano investigativo detalhado em conformidade com DR-006",
    )
    metadados_modelo: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Métricas observáveis da geração (modelo, tokens, latência, finish_reason)",
    )
    preferencias: Optional[PlanPreferencias] = Field(
        default=None,
        description="Snapshot das preferências aplicadas à pesquisa (n_pontos e personas)",
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
    plano_estruturado: Optional[PlanoInvestigacao] = None
    metadados_modelo: Optional[Dict[str, Any]] = None
    preferencias: Optional[PlanPreferencias] = None
