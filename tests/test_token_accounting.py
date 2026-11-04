"""Tokens: soma monotônica do agente principal e dos subagentes delegados."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import hermes_adapter, usage


class _Repo:
    def __init__(self, prompt: int = 0, completion: int = 0, total: int = 0) -> None:
        self.prompt = prompt
        self.completion = completion
        self.total = total
        self.chamadas = []

    async def get_research(self, _id):
        return SimpleNamespace(
            tokens_prompt=self.prompt, tokens_completion=self.completion, tokens_total=self.total
        )

    async def set_research_tokens(self, _id, prompt, completion, total):
        self.prompt, self.completion, self.total = prompt, completion, total
        self.chamadas.append((prompt, completion, total))


def _uso(workspace: Path, etapa: str, entrada: int, saida: int) -> None:
    (workspace / f"usage_{etapa}.json").write_text(
        json.dumps({"input_tokens": entrada, "output_tokens": saida, "total_tokens": entrada + saida}),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_tokens_acumulam_monotonicamente_entre_planejamento_busca_auditoria_redacao(tmp_path: Path):
    _uso(tmp_path, "plan", 4000, 1000)
    _uso(tmp_path, "search", 20000, 4000)
    _uso(tmp_path, "audit", 5000, 1000)
    _uso(tmp_path, "write", 12000, 2400)

    repo = _Repo()
    await hermes_adapter._aplicar_tokens(repo, "plan-1-aaaaaaaa", tmp_path)

    assert repo.prompt == 41000
    assert repo.completion == 8400
    assert repo.total == 49400, "o total tem de somar todas as etapas, não o último turno"

    # Turno parcial menor depois não regride o número já persistido.
    _uso(tmp_path, "write", 100, 10)
    await hermes_adapter._aplicar_tokens(repo, "plan-1-aaaaaaaa", tmp_path)
    assert repo.total == 49400


@pytest.mark.asyncio
async def test_tokens_capturam_uso_dos_subagentes_delegados(tmp_path: Path):
    (tmp_path / "usage.json").write_text(
        json.dumps(
            {
                "input_tokens": 20000,
                "output_tokens": 4000,
                "total_tokens": 24000,
                "api_calls": 9,
                "model": "modelo-x",
                "agents": {
                    "historiador": {"input_tokens": 6000, "output_tokens": 1000, "total_tokens": 7000},
                    "cetico": {"input_tokens": 5000, "output_tokens": 800, "total_tokens": 5800},
                    "auditor": {"input_tokens": 3000, "output_tokens": 500, "total_tokens": 3500},
                },
            }
        ),
        encoding="utf-8",
    )
    repo = _Repo()
    await hermes_adapter._aplicar_tokens(repo, "plan-1-bbbbbbbb", tmp_path)

    assert repo.total == 24000
    resumo = json.loads((tmp_path / "USAGE_SUMMARY.json").read_text(encoding="utf-8"))
    assert set(resumo["por_agente"]) == {"historiador", "cetico", "auditor"}
    assert resumo["por_agente"]["historiador"]["total_tokens"] == 7000
    assert usage.resumo_uso(tmp_path)["total"]["total_tokens"] == 24000
