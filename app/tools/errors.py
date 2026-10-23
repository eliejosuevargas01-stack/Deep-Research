"""Erros tipados e classificação de falhas de provedores externos.

Centraliza a tradução de respostas HTTP falhas em categorias acionáveis, para que
nenhuma falha de provedor seja convertida em resultado vazio indistinguível de
"nenhuma fonte encontrada". Atende RF-01 e RF-02 do ciclo forward 004.
"""

from typing import Any, Optional

# Categorias de falha com ação corretiva associada
CATEGORIA_ACAO_CORRETIVA = {
    "billing": (
        "O provedor recusou a chamada por saldo insuficiente. "
        "Recarregue o saldo da conta ou informe outra chave com saldo."
    ),
    "autenticacao": (
        "O provedor recusou a credencial (não autorizada ou proibida). "
        "Verifique a chave configurada e o escopo de acesso."
    ),
    "rate_limit": (
        "O provedor limitou a taxa de chamadas. "
        "Reintente em alguns minutos ou reduza a concorrência de personas."
    ),
    "indisponibilidade": (
        "O provedor está indisponível ou instável. "
        "Reintente mais tarde; a falha é temporária."
    ),
    "desconhecido": (
        "O provedor respondeu com um erro não classificado. "
        "Inspecione o detalhe bruto e ajuste a chamada."
    ),
}

CATEGORIA_POR_STATUS = {
    401: "autenticacao",
    403: "autenticacao",
    402: "billing",
    429: "rate_limit",
    500: "indisponibilidade",
    502: "indisponibilidade",
    503: "indisponibilidade",
    504: "indisponibilidade",
}

TERMINAIS = frozenset({"billing", "autenticacao"})


class JinaError(RuntimeError):
    """Falha classificada de uma chamada ao provedor Jina.

    Carrega o código HTTP, a categoria da falha e a ação corretiva, de modo que
    o orquestrador possa decidir entre reprovar o ponto e repetir a operação sem
    interpretar strings de erro.
    """

    def __init__(
        self,
        message: str,
        *,
        http_status: Optional[int] = None,
        categoria: str = "desconhecido",
        erro_original: Any = None,
    ) -> None:
        self.http_status = http_status
        self.categoria = categoria if categoria in CATEGORIA_ACAO_CORRETIVA else "desconhecido"
        self.acao_corretiva = CATEGORIA_ACAO_CORRETIVA[self.categoria]
        self.erro_original = erro_original
        detalhe = str(message).strip() or f"HTTP {http_status}"
        super().__init__(
            f"Falha na chamada do Jina [{self.categoria}] (HTTP {http_status}): "
            f"{detalhe}. {self.acao_corretiva}"
        )

    @property
    def terminal(self) -> bool:
        """Falhas de billing e autenticação não melhoram com retry."""
        return self.categoria in TERMINAIS


def classify_status(http_status: int) -> str:
    """Mapeia código HTTP para categoria de falha (RF-01)."""
    if http_status in CATEGORIA_POR_STATUS:
        return CATEGORIA_POR_STATUS[http_status]
    if 500 <= http_status <= 599:
        return "indisponibilidade"
    return "desconhecido"


def extract_message(body: Any, http_status: int) -> str:
    """Extrai mensagem legível do corpo de erro sem jamais expor segredos."""
    if isinstance(body, dict):
        for key in ("message", "error", "detail"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:300]
            if isinstance(value, dict):
                inner = value.get("message")
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()[:300]
        data = body.get("data")
        if isinstance(data, dict):
            for key in ("message", "error"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:300]
    if isinstance(body, str) and body.strip():
        return body.strip()[:300]
    return f"HTTP {http_status} sem corpo explicativo"


def classify_failure(
    http_status: int,
    body: Any = None,
    *,
    erro_original: Any = None,
) -> JinaError:
    """Constrói a `JinaError` categorizada para uma resposta falha."""
    return JinaError(
        extract_message(body, http_status),
        http_status=http_status,
        categoria=classify_status(http_status),
        erro_original=erro_original,
    )
