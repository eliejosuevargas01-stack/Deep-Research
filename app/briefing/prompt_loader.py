"""Carregamento sem cache da instrução de sistema do briefing."""

from pathlib import Path


class PromptUnavailable(RuntimeError):
    """Prompt de briefing ausente, ilegível ou vazio."""


def load_briefing_prompt(path: str | Path | None = None) -> str:
    """Lê prompt do disco em cada chamada; erro não revela detalhes locais."""
    prompt_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parent.parent / "prompts" / "briefing.md"
    )
    try:
        prompt = prompt_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PromptUnavailable("Prompt de briefing indisponível ou inválido") from exc
    if not prompt.strip():
        raise PromptUnavailable("Prompt de briefing indisponível ou inválido")
    return prompt
