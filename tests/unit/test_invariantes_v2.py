"""Testes dos invariantes de dados v2 (PRD v2, I-2, I-3, I-5).

Cobrem:
- `execution_mode` explícito no contrato HTTP de search e plan;
- ausência de truncamento na entrada do plan;
- histórico integral de rodadas entregue ao auditor e ao writer;
- preservação de conteúdo acima de qualquer limite suspeito (ex.: 40.000 chars).
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# I-3: execution_mode explícito na chamada HTTP
# ---------------------------------------------------------------------------

def test_search_request_execution_mode_contract() -> None:
    """SearchRequest aceita parallel/sequential, default parallel, rejeita o resto."""
    from app.schemas.search import SearchRequest

    base = {"id_pesquisa": "00000000-0000-0000-0000-000000000001"}
    assert SearchRequest(**base).execution_mode == "parallel"
    assert SearchRequest(**base, execution_mode="sequential").execution_mode == "sequential"
    with pytest.raises(ValidationError):
        SearchRequest(**base, execution_mode="paralelo")


def test_plan_request_execution_mode_contract() -> None:
    """PlanRequest aceita execution_mode e preserva o default parallel."""
    from app.schemas.plan import PlanRequest

    assert PlanRequest(tema="Tema suficientemente longo").execution_mode == "parallel"
    assert (
        PlanRequest(tema="Tema suficientemente longo", execution_mode="sequential").execution_mode
        == "sequential"
    )
    with pytest.raises(ValidationError):
        PlanRequest(tema="Tema suficientemente longo", execution_mode="concorrente")


def test_validate_execution_mode_rejects_invalid() -> None:
    """A validação interna rejeita valor fora do enum em vez de assumir default."""
    from app.schemas.execution import validate_execution_mode

    assert validate_execution_mode("parallel") == "parallel"
    assert validate_execution_mode("sequential") == "sequential"
    with pytest.raises(ValueError):
        validate_execution_mode("sequencial")


# ---------------------------------------------------------------------------
# I-2: zero truncamento na entrada do plan
# ---------------------------------------------------------------------------

def test_plan_request_nao_trunca_briefing() -> None:
    """Briefing de 8.000 caracteres atravessa a validação sem perder um caractere."""
    from app.schemas.plan import PlanRequest

    briefing = ("Briefing estratégico com detalhes operacionais. " * 200)[:8000]
    assert len(briefing) == 8000
    assert PlanRequest(tema=briefing).tema == briefing


# ---------------------------------------------------------------------------
# I-5: histórico integral de rodadas (auditor e writer)
# ---------------------------------------------------------------------------
