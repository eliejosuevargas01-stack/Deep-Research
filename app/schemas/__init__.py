from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator

ROLES = ("scout", "historian", "skeptic", "pragmatist", "futurist", "auditor", "writer")
PROVIDERS = ("openai", "anthropic", "gemini", "litellm", "jina", "serpapi", "apify")


class LoginRequest(BaseModel):
    password: str


class ResearchCreate(BaseModel):
    theme: str = Field(min_length=3, max_length=500)
    callback_url: HttpUrl | None = None


class BriefingPoint(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    description: str = Field(min_length=3, max_length=4000)
    dependencies: list[str] = Field(default_factory=list)
    is_parallelizable: bool = True


class BriefingApproval(BaseModel):
    approved_points: list[BriefingPoint] = Field(min_length=1, max_length=10)


class BriefingEdit(BaseModel):
    note: str = Field(min_length=3, max_length=4000)
    points: list[BriefingPoint] | None = None


class SettingsUpdate(BaseModel):
    provider_keys: dict[str, str | None] = Field(default_factory=dict)
    models: dict[str, str] = Field(default_factory=dict)

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
