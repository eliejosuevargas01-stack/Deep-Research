"""Contratos canônicos (PRD §3 / SDD §3-4). Nomes em português são os oficiais."""

from __future__ import annotations

from typing import Any, Iterable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

PERSONAS: tuple[str, ...] = ("historiador", "cetico", "visionario", "futurista")
PERGUNTAS: tuple[str, ...] = tuple(str(i) for i in range(1, 13))


def normalizar_urls(urls: Iterable[Any]) -> list[str]:
    """Deduplica preservando a ordem de chegada."""
    vistas: dict[str, None] = {}
    for url in urls:
        if isinstance(url, str) and (limpa := url.strip()):
            vistas[limpa] = None
    return list(vistas)


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tema: str = Field(min_length=3)
    profundidade: int = Field(ge=1, le=10)
    veracidade_alvo: float = Field(ge=0, le=100)
    max_rodadas_auditoria: int = Field(default=4, ge=1, le=10)
    atualidade: str = Field(default="ALL", pattern=r"^(ALL|\d{1,3}[HDMY])$")
    callback_url: HttpUrl

    @field_validator("tema")
    @classmethod
    def _tema_obrigatorio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("tema não pode ser vazio")
        return valor


class PontoPlano(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ponto_id: int = Field(ge=1)
    enunciado: str = Field(min_length=1)
    subperguntas: list[str] = Field(min_length=3)
    hipoteses: list[str] = Field(min_length=3)
    lacunas_iniciais: list[str] = Field(min_length=3)
    perguntas_auditoria: dict[str, str]

    @field_validator("enunciado")
    @classmethod
    def _enunciado_limpo(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("enunciado não pode ser vazio")
        return valor

    @field_validator("subperguntas", "hipoteses", "lacunas_iniciais")
    @classmethod
    def _minimo_tres(cls, itens: list[str]) -> list[str]:
        limpos = [item.strip() for item in itens if isinstance(item, str) and item.strip()]
        if len(limpos) < 3:
            raise ValueError("mínimo de 3 itens não vazios")
        return limpos

    @field_validator("perguntas_auditoria", mode="before")
    @classmethod
    def _chaves_texto(cls, valor: Any) -> Any:
        if not isinstance(valor, dict):
            return valor
        return {
            str(chave).strip(): str(pergunta).strip()
            for chave, pergunta in valor.items()
            if str(pergunta).strip()
        }

    @model_validator(mode="after")
    def _exatamente_doze(self) -> "PontoPlano":
        if set(self.perguntas_auditoria) != set(PERGUNTAS):
            faltando = sorted(set(PERGUNTAS) - set(self.perguntas_auditoria), key=int)
            raise ValueError(f"perguntas_auditoria deve ter as 12 chaves \"1\"..\"12\"; faltam {faltando}")
        return self


class PlanoLLM(BaseModel):
    """Saída bruta esperada do planner: só os pontos; o resto vem da requisição."""

    model_config = ConfigDict(extra="ignore")

    pontos: list[PontoPlano]

    def validar_para(self, profundidade: int) -> "PlanoLLM":
        if len(self.pontos) != profundidade:
            raise ValueError(f"plano deve ter exatamente {profundidade} pontos, veio com {len(self.pontos)}")
        ids = sorted(ponto.ponto_id for ponto in self.pontos)
        if ids != list(range(1, profundidade + 1)):
            raise ValueError(f"ponto_id deve ser sequencial de 1 a {profundidade}; veio {ids}")
        self.pontos.sort(key=lambda ponto: ponto.ponto_id)
        return self


class BuscadorSaida(BaseModel):
    model_config = ConfigDict(extra="ignore")

    informacao_coletada: str
    urls_usadas: list[str] = Field(default_factory=list)
    urls_lidas: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalizar(self) -> "BuscadorSaida":
        self.informacao_coletada = self.informacao_coletada.strip()
        if not self.informacao_coletada:
            raise ValueError("informacao_coletada não pode ser vazia")
        self.urls_usadas = normalizar_urls(self.urls_usadas)
        # URL usada foi necessariamente lida; normaliza em vez de perder a citação.
        self.urls_lidas = normalizar_urls([*self.urls_lidas, *self.urls_usadas])
        return self

    @property
    def urls_lidas_nao_usadas(self) -> list[str]:
        usadas = set(self.urls_usadas)
        return [url for url in self.urls_lidas if url not in usadas]


class AuditorSaida(BaseModel):
    model_config = ConfigDict(extra="ignore")

    perguntas_respondidas: dict[str, bool]

    @field_validator("perguntas_respondidas", mode="before")
    @classmethod
    def _coerir_booleanos(cls, valor: Any) -> Any:
        if not isinstance(valor, dict):
            return valor
        coerido: dict[str, bool] = {}
        for chave, bruto in valor.items():
            chave = str(chave).strip()
            if isinstance(bruto, bool):
                coerido[chave] = bruto
            elif isinstance(bruto, str) and bruto.strip().lower() in {"true", "false"}:
                coerido[chave] = bruto.strip().lower() == "true"
            else:
                raise ValueError(f"pergunta {chave}: valor não booleano ({bruto!r})")
        return coerido

    @model_validator(mode="after")
    def _exatamente_doze(self) -> "AuditorSaida":
        if set(self.perguntas_respondidas) != set(PERGUNTAS):
            faltando = sorted(set(PERGUNTAS) - set(self.perguntas_respondidas), key=int)
            raise ValueError(f"perguntas_respondidas deve ter as 12 chaves \"1\"..\"12\"; faltam {faltando}")
        return self


class RedatorSaida(BaseModel):
    model_config = ConfigDict(extra="ignore")

    relatorio_ponto: str
    lacunas_identificadas: str = ""
    urls_citadas: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalizar(self) -> "RedatorSaida":
        self.relatorio_ponto = self.relatorio_ponto.strip()
        if not self.relatorio_ponto:
            raise ValueError("relatorio_ponto não pode ser vazio")
        self.lacunas_identificadas = self.lacunas_identificadas.strip()
        self.urls_citadas = normalizar_urls(self.urls_citadas)
        return self
