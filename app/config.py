"""Módulo de configuração da aplicação via Pydantic Settings.

Carrega configurações estritamente de variáveis de ambiente ou arquivo .env
sem fallbacks hardcoded, atendendo a RN-02 e DT-01.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações operacionais da aplicação sem valores padrão hardcoded."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Configurações do Pipeline de Pesquisa
    n_pontos: Optional[int] = None
    personas_config: Optional[str] = None

    # Segurança e Criptografia
    credentials_master_key: Optional[str] = None
    webhook_hmac_secret: Optional[str] = None
    callback_webhook_url: Optional[str] = None
    api_secret_key: Optional[str] = None

    # Provedores Externos (LLM e Jina)
    openai_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model_light: Optional[str] = None
    llm_model_strong: Optional[str] = None
    jina_api_key: Optional[str] = None
    jina_base_url: Optional[str] = None

    # Persistência do Banco de Dados
    database_url: Optional[str] = None

    def require_n_pontos(self) -> int:
        """Obtém N_PONTOS ou lança erro explícito sem fallback hardcoded."""
        if self.n_pontos is None:
            raise ValueError("Configuração ausente: N_PONTOS deve ser definida via ambiente ou banco.")
        return self.n_pontos

    def require_master_key(self) -> str:
        """Obtém CREDENTIALS_MASTER_KEY ou lança erro explícito."""
        if not self.credentials_master_key:
            raise ValueError("Configuração ausente: CREDENTIALS_MASTER_KEY não informada no ambiente.")
        return self.credentials_master_key


# ponytail: cache global simples de settings; limpe o cache com get_settings.cache_clear() em testes
@lru_cache()
def get_settings() -> Settings:
    """Retorna instância singleton de configurações."""
    return Settings()
