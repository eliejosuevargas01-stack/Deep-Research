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

def _coleta(rodada: int, *, analise: str, com_personas: bool = True):
    """Constrói uma coleta v3: catálogo de URLs + resumos, sem bruto."""
    import json

    url = f"https://exemplo.org/rodada-{rodada}"
    meta = {
        "versao": 3,
        "fontes": [
            {
                "url": url,
                "uso": "utilizada",
                "titulo": f"Fonte da rodada {rodada}",
                "status": "read_ok",
                "data_fonte": None,
            }
        ],
        "auditorias": [{"id_auditoria": f"aud_{rodada}", "status": "reprovado", "valido": True}],
    }
    if com_personas:
        meta["resultados_personas"] = {
            "historiador": {
                "analise": analise,
                "sucesso": True,
                "lacunas": [],
                "urls_lidas": [url],
                "urls_fonte": [url],
                "conclusoes": [
                    {
                        "claim_id": f"c_{rodada}",
                        "afirmacao": f"Afirmação da rodada {rodada}",
                        "tipo": "fato",
                        "confianca": "alta",
                        "evidencias": [url],
                    }
                ],
            }
        }
    return SimpleNamespace(
        id=f"coleta-{rodada}",
        rodada=rodada,
        criado_em=f"2026-10-2{rodada}T10:00:00+00:00",
        conteudo_coletado=f"Síntese integral da rodada {rodada}",
        metadados_coleta=json.dumps(meta, ensure_ascii=False),
    )


def test_auditor_historico_rodadas_preserva_todas_as_retries() -> None:
    """Ponto com 3 retries: as 4 rodadas entram no payload do auditor, sem corte."""
    from app.core.auditor import _montar_historico_rodadas

    analise_longa = "Evidência detalhada. " * 2000  # ~40.000 chars
    coletas = [
        _coleta(1, analise="análise r1", com_personas=False),
        _coleta(2, analise="análise r2"),
        _coleta(3, analise="análise r3"),
        _coleta(4, analise=analise_longa),
    ]

    historico = _montar_historico_rodadas(coletas, coleta_corrente_id="coleta-4")

    assert [r["rodada"] for r in historico] == [1, 2, 3, 4]
    assert [r["coleta_id"] for r in historico] == [f"coleta-{i}" for i in range(1, 5)]
    assert sum(1 for r in historico if r["corrente"]) == 1
    assert historico[-1]["corrente"] is True
    # Rodada corrente não truncada
    assert historico[-1]["resultados_personas"]["historiador"]["analise"] == analise_longa
    # Catálogo v3: só URL/uso/título/status, nunca corpo ou hash
    fonte = historico[-1]["fontes"][0]
    assert fonte["url"] == "https://exemplo.org/rodada-4"
    assert fonte["uso"] == "utilizada"
    assert "body" not in fonte and "body_hash" not in fonte
    # Rodada legada (sem personas) carrega o texto bruto, sem corte
    assert historico[0]["legado"] is True
    assert historico[0]["conteudo_coletado"] == "Síntese integral da rodada 1"


def test_writer_rodadas_preserva_todas_as_retries() -> None:
    """Contexto de redação carrega uma entrada por rodada, com resumo integral."""
    from app.core.writer import _montar_rodada_escrita

    analise_longa = "Conteúdo coletado relevante. " * 1500  # ~45.000 chars
    coletas = [
        _coleta(1, analise="análise r1", com_personas=False),
        _coleta(2, analise="análise r2"),
        _coleta(3, analise=analise_longa),
    ]

    rodadas = [_montar_rodada_escrita(c, corrente_id="coleta-3") for c in coletas]

    assert [r["rodada"] for r in rodadas] == [1, 2, 3]
    assert rodadas[-1]["corrente"] is True
    assert rodadas[-1]["personas"]["historiador"]["analise"] == analise_longa
    assert "trechos" not in rodadas[-1]
    assert rodadas[0]["legado"] is True
    assert rodadas[0]["conteudo_coletado"] == "Síntese integral da rodada 1"
    # Nenhuma rodada é descartada nem substituída pela última
    assert len(rodadas) == 3
    assert all(r["coleta_id"] for r in rodadas)
