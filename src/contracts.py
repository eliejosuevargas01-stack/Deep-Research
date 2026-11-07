"""Contratos canônicos (PRD §3 / SDD §3-4). Nomes em português são os oficiais."""

from __future__ import annotations

import logging
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

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

# 12 perguntas de auditoria ESTÁTICAS e universais (iguais para todos os pontos).
# O planner NÃO as cria: o backend injeta esta cópia em cada ponto em `_planejar`
# antes de persistir. Texto binário (sim/não), sem menção a ponto específico.
PERGUNTAS_AUDITORIA_ESTATICAS: dict[str, str] = {
    "1": "O material coletado aborda de forma clara e objetiva o eixo do ponto e responde às suas subperguntas? (sim/não)",
    "2": "As afirmações centrais estão sustentadas por fontes primárias verificáveis, e não apenas por URLs citadas sem verificação? (sim/não)",
    "3": "Os marcos e dados apresentados estão atualizados dentro da janela de atualidade exigida? (sim/não)",
    "4": "As informações coletadas pelas 4 personas são internamente coerentes (ou têm eventuais diferenças de recorte/metodologia claramente identificadas)? (sim/não)",
    "5": "As conclusões têm ancoragem empírica no material, sem tratar ausência de evidência como falsidade nem como prova? (sim/não)",
    "6": "O material atém-se ao tema, ao enunciado e ao escopo do ponto, sem desvios relevantes? (sim/não)",
    "7": "A análise tem profundidade adequada e delimita as incertezas em vez de apenas descrever fatos? (sim/não)",
    "8": "Números, datas, unidades, métricas e identificadores estão precisos e com eventuais divergências metodológicas entre fontes devidamente delimitadas? (sim/não)",
    "9": "Fatos observados estão separados de hipóteses e interpretações, com neutralidade analítica? (sim/não)",
    "10": "A densidade de evidências é proporcional às afirmações, com respaldo em urls_usadas? (sim/não)",
    "11": "As incertezas e lacunas remanescentes estão declaradas e delimitadas explicitamente? (sim/não)",
    "12": "As conclusões decorrem logicamente das evidências apresentadas, sem saltos lógicos? (sim/não)",
}

_FIM_SUJO = ".,;)]>"

logger = logging.getLogger(__name__)

# Filtro de política: agregador/dever de casa, slide e rede social não sustentam
# evidência primária. Descarte com warning, nunca ValueError (a rodada segue válida).
DOMINIOS_BLOQUEADOS: frozenset[str] = frozenset(
    {
        "x.com",
        "twitter.com",
        "facebook.com",
        "instagram.com",
        "tiktok.com",
        "pinterest.com",
        "prezi.com",
        "slideshare.net",
        "pt.slideshare.net",
        "studocu.com",
        "brainly.com.br",
        "brainly.com",
    }
)


def _host_bloqueado(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return any(host == dominio or host.endswith("." + dominio) for dominio in DOMINIOS_BLOQUEADOS)


def _limpar_url(valor: str) -> str:
    return valor.strip().rstrip(_FIM_SUJO).strip()


def _url_valida(valor: str) -> bool:
    try:
        partes = urlsplit(valor)
    except ValueError:
        return False
    if partes.scheme not in ("http", "https") or not partes.hostname:
        return False
    try:
        partes.port
    except ValueError:
        return False
    host = partes.hostname.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    # Validação dura: rejeitar host truncado (ex.: https://www.fazenda.pt-br/composicao/,
    # onde urlsplit lê hostname "www.fazenda.pt-br"). Hífron/dígito/underscore no TLD
    # indica path colado no host, não um domínio real.
    labels = host.split(".")
    if len(labels) < 2 or any(not rotulo for rotulo in labels):
        return False
    tld = labels[-1]
    # IDN punycode (xn--p1ai) é TLD válido; hífen/dígito fora dele indica path colado no host.
    if tld.startswith("xn--"):
        if len(tld) < 6:
            return False
    elif not tld.isalpha() or any(ch.isdigit() for ch in tld):
        return False
    if "_" in tld:
        return False
    return " " not in valor


def chave_url(valor: str) -> str:
    """Chave canônica para dedupe/comparação de URLs.

    scheme e host em minúsculas, sem ``www.`` nem ponto final; porta default
    removida; path com percent-decoding; barra final removida (vazio vira "/");
    fragment descartado; query mantida. O resultado inteiro vai em minúsculas:
    dedupe de paths case-sensitive é raro na prática e o ganho de recall
    compensa (``ponytail:`` se um dia case-sensitive importar — p.ex. pastas
    distintas só por caixa —, trocar o ``.lower()`` final por lower só em
    scheme+host e cobrir com teste de colisão intencional).
    """
    partes = urlsplit(valor.strip())
    esquema = partes.scheme.lower()
    host = (partes.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    try:
        porta = partes.port
    except ValueError:
        porta = None
    padrao = {"http": 80, "https": 443}
    rede = host
    if porta and porta != padrao.get(esquema):
        rede = f"{host}:{porta}"
    caminho = unquote(partes.path or "")
    if len(caminho) > 1:
        caminho = caminho.rstrip("/")
    if not caminho:
        caminho = "/"
    chave = f"{esquema}://{rede}{caminho}"
    if partes.query:
        chave += f"?{partes.query}"
    return chave.lower()


def normalizar_urls(urls: Iterable[Any]) -> list[str]:
    """Deduplica (por ``chave_url``) preservando a primeira forma limpa; higieniza e valida.

    URL inválida falha com ValueError (nunca descartada em silêncio).
    URL de domínio bloqueado é filtro de política: descartada com
    logger.warning, sem invalidar a rodada.
    """
    vistas: dict[str, None] = {}
    saidas: list[str] = []
    for url in urls:
        if not isinstance(url, str):
            continue
        limpa = _limpar_url(url)
        if not limpa:
            continue
        if not _url_valida(limpa):
            raise ValueError(f"URL inválida: {limpa}")
        partes = urlsplit(limpa)
        if _host_bloqueado(partes.hostname or ""):
            logger.warning("URL descartada por política de domínio: %s", limpa)
            continue
        chave = chave_url(limpa)
        if chave not in vistas:
            vistas[chave] = None
            saidas.append(limpa)
    return saidas


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
    perguntas_auditoria: dict[str, str] = Field(
        default_factory=lambda: dict(PERGUNTAS_AUDITORIA_ESTATICAS)
    )

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
    """Saída bruta esperada do planner: pontos + links da varredura exploratória."""

    model_config = ConfigDict(extra="ignore")

    pontos: list[PontoPlano]
    urls_lidas: list[str] = Field(default_factory=list)
    urls_usadas: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalizar_urls(self) -> "PlanoLLM":
        self.urls_usadas = normalizar_urls(self.urls_usadas)
        # URL usada foi necessariamente lida; normaliza em vez de perder a citação.
        self.urls_lidas = normalizar_urls([*self.urls_lidas, *self.urls_usadas])
        return self

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
        for chave, bruto in valor.items():
            if not isinstance(bruto, bool):
                raise ValueError(f"pergunta {chave}: valor não booleano ({bruto!r}) — use true/false JSON")
        return valor

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
