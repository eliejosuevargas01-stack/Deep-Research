"""Carregamento sem cache da instrução de sistema do Agente Auditor (D-306).

Segue o padrão de ``app/briefing/prompt_loader.py``: lê o template em disco
a cada chamada; erros não revelam detalhes locais do filesystem.
"""

from pathlib import Path


class PromptUnavailable(RuntimeError):
    """Prompt de auditoria ausente, ilegível ou vazio."""


def load_auditor_prompt(path: str | Path | None = None) -> str:
    """Lê ``app/prompts/auditor.md`` do disco em cada chamada."""
    prompt_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parent.parent / "prompts" / "auditor.md"
    )
    try:
        prompt = prompt_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PromptUnavailable("Prompt de auditoria indisponível ou inválido") from exc
    if not prompt.strip():
        raise PromptUnavailable("Prompt de auditoria indisponível ou inválido")
    return prompt
