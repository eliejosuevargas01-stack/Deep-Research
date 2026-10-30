"""Tipos e estruturas de dados para o envelope imutável do cliente LLM.

Atende a DR-005, DR-013, DR-014 e DT-11:
- Envelope por chamada isolado e imutável (sem estado global compartilhado).
- Registro de content_final, reasoning_content, finish_reason real e métricas.
- Tabela de preços configurada explicitamente (sem preços presumidos hardcoded e sem substring aliases).
- Sem preço configurado ou sem contagem de tokens = custo honestamente None.
- Sanitização recursiva e remoção de segredos/chaves de API em logs e mensagens.
- Indicação expressa de que transformações posteriores do roteador/proxy são não observadas.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ModelPriceConfig:
    """Configuração explícita de preço operacional por token para um modelo exato."""

    model_exact: str
    prompt_price_per_token: float
    completion_price_per_token: float
    currency: str = "USD"
    source: str = "configured"

    def __post_init__(self) -> None:
        if not self.model_exact or not str(self.model_exact).strip():
            raise ValueError("model_exact não pode ser vazio.")
        if self.prompt_price_per_token < 0 or self.completion_price_per_token < 0:
            raise ValueError("Preço por token não pode ser negativo.")


class PricingRegistry:
    """Registro de tabelas de preços operacionais explicitamente configuradas.
    
    Por padrão inicia VAZIO (sem preços presumidos hardcoded).
    Exige correspondência exata de modelo (case-insensitive, sem substring alias).
    """

    def __init__(self, table: Optional[Dict[str, ModelPriceConfig]] = None) -> None:
        self._table: Dict[str, ModelPriceConfig] = {}
        if table:
            for k, v in table.items():
                self.register(v)

    def register(self, config: ModelPriceConfig) -> None:
        """Registra uma configuração de preço para um modelo exato."""
        key = config.model_exact.strip().lower()
        self._table[key] = config

    def estimate_cost(
        self,
        model_name: Optional[str],
        usage: Optional[Dict[str, Any]],
    ) -> Optional[float]:
        """Calcula custo se o modelo exato estiver configurado e usage contiver contagem válida de tokens."""
        if not model_name or not usage or not isinstance(usage, dict):
            return None

        # Exige correspondência exata, sem substring matching / alias presumido
        key = model_name.strip().lower()
        config = self._table.get(key)
        if not config:
            return None

        prompt_tokens = usage.get("prompt_tokens")
        if prompt_tokens is None:
            prompt_tokens = usage.get("input_tokens")

        completion_tokens = usage.get("completion_tokens")
        if completion_tokens is None:
            completion_tokens = usage.get("output_tokens")

        if prompt_tokens is None or completion_tokens is None:
            return None

        try:
            p_tokens = int(prompt_tokens)
            c_tokens = int(completion_tokens)
            if p_tokens < 0 or c_tokens < 0:
                return None
        except (ValueError, TypeError):
            return None

        cost = (p_tokens * config.prompt_price_per_token) + (c_tokens * config.completion_price_per_token)
        return round(cost, 8)

    def estimate_cost_detailed(
        self,
        model_name: Optional[str],
        usage: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        """Calcula custo estimado, moeda e fonte se o modelo e tokens estiverem configurados."""
        if not isinstance(usage, dict):
            return None, None, None
        cost = self.estimate_cost(model_name, usage)
        if cost is None or not model_name:
            return None, None, None
        key = model_name.strip().lower()
        config = self._table.get(key)
        if not config:
            return None, None, None
        return cost, config.currency, config.source


# Registro padrão vazio: sem preços presumidos hardcoded
_DEFAULT_PRICING_REGISTRY = PricingRegistry()


def get_default_pricing_registry() -> PricingRegistry:
    """Retorna o registro de preços padrão."""
    return _DEFAULT_PRICING_REGISTRY


def estimate_cost(
    model_name: Optional[str],
    usage: Optional[Dict[str, Any]],
    pricing_registry: Optional[PricingRegistry] = None,
) -> Optional[float]:
    """Calcula custo estimado usando o registro de preços fornecido ou o registro padrão configurado.
    
    Retorna None se o modelo não tiver preço configurado ou se os tokens forem ausentes/inválidos.
    """
    registry = pricing_registry or _DEFAULT_PRICING_REGISTRY
    return registry.estimate_cost(model_name, usage)


def estimate_cost_detailed(
    model_name: Optional[str],
    usage: Optional[Dict[str, Any]],
    pricing_registry: Optional[PricingRegistry] = None,
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """Calcula custo estimado, moeda e fonte usando o registro de preços fornecido ou o padrão."""
    registry = pricing_registry or _DEFAULT_PRICING_REGISTRY
    return registry.estimate_cost_detailed(model_name, usage)


_CREDENTIAL_PATTERN = re.compile(
    r"(?:"
    r"bearer\s+[a-zA-Z0-9_\-\.]{8,}|"
    r"sk-(?:proj-|or-v1-)?[a-zA-Z0-9_\-]{16,}|"
    r"AIza[a-zA-Z0-9_\-]{30,}|"
    r"(?:(?:x-)?api[_-]?key|token|secret)[\s:=]+[a-zA-Z0-9_\-]{8,}|"
    r"key=[a-zA-Z0-9_\-]{8,}"
    r")",
    re.IGNORECASE,
)
_URL_CREDENTIAL_PATTERN = re.compile(
    r"(https?://)([^:/?#\s\"'\\\[\]]+):([^@/?#\s\"'\\\[\]]+)@",
    re.IGNORECASE,
)


def redact_sensitive_string(text: str, client_api_key: Optional[str] = None) -> str:
    """Substitui padrões comuns de tokens, chaves e credenciais em URLs por marcador [REDACTED]."""
    if not text:
        return text

    redacted = text
    # 1. Redige chave de cliente explícita se fornecida
    if client_api_key and len(client_api_key.strip()) >= 4:
        redacted = redacted.replace(client_api_key.strip(), "[REDACTED_API_KEY]")

    # 2. Redige credenciais embutidas em URLs (ex: https://user:pass@host)
    redacted = _URL_CREDENTIAL_PATTERN.sub(r"\1[REDACTED_USER]:[REDACTED_PASS]@", redacted)

    # 3. Redige Bearer tokens e chaves sk-
    redacted = _CREDENTIAL_PATTERN.sub("[REDACTED]", redacted)
    return redacted


def is_secret_field_name(field_name: Any) -> bool:
    """Identifica se o nome de um campo ou chave contém segredos a serem redigidos (R2-F09).
    
    Não redige métricas e parâmetros legítimos como max_tokens, completion_tokens,
    prompt_tokens, total_tokens ou token_count.
    """
    k_lower = str(field_name).strip().lower()
    # Métricas e contadores de tokens NÃO são segredos
    if any(k_lower.endswith(suf) for suf in ("_tokens", "_token_count", "token_count", "tokens")):
        if k_lower not in ("auth_tokens", "access_tokens", "session_tokens", "refresh_tokens"):
            return False

    # Nomes exatos ou sufixos comuns de segredos
    exact_secrets = {
        "authorization", "api_key", "api-key", "apikey", "x-api-key", "x_api_key",
        "secret", "client_secret", "password", "passwd", "pwd", "credential",
        "credentials", "private_key", "auth_token", "access_token", "refresh_token",
        "session_token", "bearer_token", "token",
    }
    if k_lower in exact_secrets:
        return True

    for sec in ("authorization", "api_key", "api-key", "x-api-key", "secret", "password", "credential"):
        if sec in k_lower:
            return True
    return False


def sanitize_recursively(data: Any, client_api_key: Optional[str] = None) -> Any:
    """Higieniza recursivamente dicts, lists, strings e tuplas removendo segredos (R2-F09)."""
    if isinstance(data, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in data.items():
            if is_secret_field_name(k):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_recursively(v, client_api_key=client_api_key)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_recursively(item, client_api_key=client_api_key) for item in data]
    elif isinstance(data, tuple):
        return tuple(sanitize_recursively(item, client_api_key=client_api_key) for item in data)
    elif isinstance(data, str):
        return redact_sensitive_string(data, client_api_key=client_api_key)
    return data


def sanitize_messages_for_audit(
    messages: List[Dict[str, Any]],
    client_api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Copia e higieniza recursivamente a lista de mensagens enviadas para histórico e logs."""
    return sanitize_recursively(messages, client_api_key=client_api_key)  # type: ignore[return-value]


def compute_prompt_hash(
    messages: List[Dict[str, Any]],
    request_params: Optional[Dict[str, Any]] = None,
) -> str:
    """Calcula hash SHA-256 canônico das mensagens e parâmetros enviados pela aplicação."""
    data_to_hash: Dict[str, Any] = {"messages": messages}
    if request_params:
        data_to_hash["request_params"] = request_params
    try:
        serialized = json.dumps(data_to_hash, sort_keys=True, ensure_ascii=False)
    except Exception:
        serialized = str(data_to_hash)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LLMEnvelope:
    """Envelope imutável e isolado contendo o resultado completo de uma chamada ao LLM.
    
    Atende a DR-005, DR-013 e DR-014.
    """

    content_final: Optional[str]
    reasoning_content: Optional[str]
    finish_reason: Optional[str]
    is_regular_finish: bool
    model_requested: str
    model_used: Optional[str]
    usage: Optional[Dict[str, Any]]
    cost_estimated: Optional[float]
    latency_seconds: float
    attempts: int
    cost_currency: Optional[str] = None
    cost_source: Optional[str] = None
    request_params: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    prompt_id: Optional[str] = None
    prompt_version: Optional[str] = None
    prompt_hash: str = ""
    system_message_sent: Optional[str] = None
    messages_sent: List[Dict[str, Any]] = field(default_factory=list)
    prior_envelopes: List[Any] = field(default_factory=list)
    downstream_router_mutations: str = "explicitly_unobserved"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Converte o envelope em dicionário serializável."""
        return asdict(self)


def project_public_envelope(envelope: Optional[LLMEnvelope]) -> Optional[Dict[str, Any]]:
    """Projeta publicamente um envelope sem expor prompts de sistema, mensagens ou raciocínio (R2-F06).
    
    Usada de forma canônica e unificada em respostas de sucesso e erro na API.
    """
    if envelope is None:
        return None

    errs_clean: List[str] = []
    if envelope.errors:
        for err in envelope.errors:
            if isinstance(err, dict):
                msg = str(err.get("message") or err.get("error") or err)
            else:
                msg = str(err)
            errs_clean.append(redact_sensitive_string(msg))

    return {
        "model_requested": envelope.model_requested,
        "model_used": envelope.model_used,
        "finish_reason": envelope.finish_reason,
        "is_regular_finish": envelope.is_regular_finish,
        "usage": envelope.usage,
        "cost_estimated": envelope.cost_estimated,
        "cost_currency": envelope.cost_currency,
        "cost_source": envelope.cost_source,
        "latency_seconds": envelope.latency_seconds,
        "attempts": envelope.attempts,
        "errors": errs_clean,
        "prompt_hash": envelope.prompt_hash,
        "downstream_router_mutations": envelope.downstream_router_mutations,
        "created_at": envelope.created_at,
    }
