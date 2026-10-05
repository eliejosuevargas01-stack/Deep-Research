"""Base classes and data contracts for Deep Research Engine Workers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain_models import Evidence, ResearchPoint
from app.services.search import Source, search_read


@dataclass
class WorkerResult:
    point_id: str
    persona: str
    evidences: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    raw_response: dict[str, Any] | None = None


class BaseWorker(ABC):
    """Abstract base worker enforcing prompt-driven research, verbatim citations and structured outputs."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Any,
        model_name: str | None = None,
        prompt_path: Path | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.model_name = model_name
        self.prompt_path = prompt_path or self._default_prompt_path()

    @classmethod
    @abstractmethod
    def persona_name(cls) -> str:
        """Unique identifier of the persona."""
        ...

    def _default_prompt_path(self) -> Path:
        base_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
        return base_dir / f"{self.persona_name()}.md"

    def load_prompt_template(self) -> str:
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Prompt template missing for {self.persona_name()}: {self.prompt_path}")

    @abstractmethod
    async def execute(
        self,
        point: ResearchPoint,
        context: dict[str, Any] | None = None,
    ) -> WorkerResult:
        """Execute the worker's research round on the given research point."""
        ...

    async def _search_and_read(
        self,
        query: str,
        limit: int = 5,
        keys: dict[str, str] | None = None,
    ) -> list[Source]:
        """Protected helper to invoke the unified search & source extraction pipeline."""
        search_keys = keys or self.settings.search_keys()
        return await search_read(query=query, limit=limit, keys=search_keys)
