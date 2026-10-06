import re
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator

ROLES = ("scout", "historian", "skeptic", "pragmatist", "futurist", "auditor", "writer")
PROVIDERS = ("openai", "anthropic", "gemini", "litellm", "jina", "serpapi", "apify")


class LoginRequest(BaseModel):
    password: str


class ResearchCreate(BaseModel):
    model_config = {"extra": "forbid"}
    theme: str = Field(description="Tema da pesquisa")
    callback_url: str | None = Field(default=None, description="URL de callback opcional para clientes backend-to-backend")

    @field_validator("theme", mode="before")
    @classmethod
    def validate_and_normalize_theme(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("Tema deve ser uma string")
        stripped = v.strip()
        if len(stripped) < 3:
            raise ValueError("Tema deve conter no mínimo 3 caracteres válidos")
        if len(stripped) > 500:
            raise ValueError("Tema não pode exceder 500 caracteres")
        return stripped


class BriefingPoint(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    description: str = Field(min_length=3, max_length=4000)
    dependencies: list[str] = Field(default_factory=list)
    is_parallelizable: bool = True


class BriefingApproval(BaseModel):
    approved_points: list[BriefingPoint] = Field(min_length=5, max_length=5)

    @field_validator("approved_points")
    @classmethod
    def validate_five_points_and_prior_deps(cls, points: list[BriefingPoint]) -> list[BriefingPoint]:
        if len(points) != 5:
            raise ValueError("Briefing approval requires exactly 5 points")
        titles = [p.title.strip() for p in points]
        if len(set(titles)) != len(titles):
            raise ValueError("Research point titles must be unique")
        for idx, point in enumerate(points):
            for ref in point.dependencies:
                ref_str = str(ref).strip()
                m = re.match(r"^(?:point|ponto)\s*(\d+)$", ref_str, re.I)
                if ref_str.isdigit():
                    p_idx = int(ref_str) - 1
                elif m:
                    p_idx = int(m.group(1)) - 1
                elif ref_str in titles:
                    p_idx = titles.index(ref_str)
                else:
                    raise ValueError(f"Unknown point dependency: '{ref}' in point {idx + 1}")
                if p_idx >= idx:
                    raise ValueError(
                        f"Point {idx + 1} has dependency on point {p_idx + 1}; dependencies must reference earlier points only (p_idx < idx)"
                    )
                if p_idx < 0:
                    raise ValueError(f"Invalid point index: {p_idx + 1}")
        return points


class BriefingEdit(BaseModel):
    note: str = Field(min_length=3, max_length=4000)
    points: list[BriefingPoint] | None = None


class SettingsUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    provider_keys: dict[str, str | None] = Field(default_factory=dict)
    models: dict[str, str] = Field(default_factory=dict)
    callback_url: str | None = None
    openai_base_url: str | None = None
    jina_base_url: str | None = None

    @field_validator("openai_base_url", "jina_base_url")
    @classmethod
    def validate_base_urls(cls, value: str | None) -> str | None:
        if value is not None and value.strip():
            from app.services.settings import validate_base_url
            return validate_base_url(value.strip())
        return value

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url(cls, value: str | None) -> str | None:
        if value is not None and value.strip():
            from app.tools.outbound import validate_public_url
            validate_public_url(value.strip())
        return value

    @field_validator("provider_keys")
    @classmethod
    def providers_known(cls, value):
        unknown = set(value) - set(PROVIDERS)
        if unknown:
            raise ValueError(f"unknown providers: {sorted(unknown)}")
        return value

    @field_validator("models")
    @classmethod
    def models_known(cls, value):
        unknown = set(value) - set(ROLES)
        if unknown:
            raise ValueError(f"unknown roles: {sorted(unknown)}")
        if any(not model.strip() for model in value.values()):
            raise ValueError("model IDs cannot be blank")
        return value


class ProviderTestRequest(BaseModel):
    provider: Literal["openai", "anthropic", "gemini", "litellm", "jina", "serpapi", "apify"]
    api_key: str = Field(min_length=1)
    base_url: str | None = None

    @field_validator("base_url")
    @classmethod
    def validate_test_base_url(cls, value: str | None) -> str | None:
        if value:
            from app.services.settings import validate_base_url
            return validate_base_url(value)
        return value


class ProviderTestResponse(BaseModel):
    success: bool
    message: str
    models: list[str] = Field(default_factory=list)


class ModelDiscoveryRequest(BaseModel):
    provider: Literal["openai", "anthropic", "gemini", "litellm"]
    api_key: str = Field(min_length=1)
    base_url: str | None = None

    @field_validator("base_url")
    @classmethod
    def validate_discovery_base_url(cls, value: str | None) -> str | None:
        if value:
            from app.services.settings import validate_base_url
            return validate_base_url(value)
        return value


class ModelDiscoveryResponse(BaseModel):
    provider: str
    models: list[str]
