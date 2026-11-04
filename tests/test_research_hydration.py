"""Hidratação da pesquisa concluída: critérios reais e SSE sem JSON bruto."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.api.v1.endpoints.research import _build_auditoria
from app.core import hermes_stream

CRITERIOS = [
    {"id": i, "nome": f"Critério {i}", "aprovado": True, "justificativa": f"ok {i}"} for i in range(1, 13)
]


def _rodada(veredito: str = "APROVADO", nota: int = 12) -> dict:
    return {"rodada": 2, "veredito": veredito, "nota": nota, "criterios": CRITERIOS, "lacunas": None}


def test_get_research_concluida_retorna_criterios_reais_e_dossie_completo():
    pesquisa = SimpleNamespace(
        id_pesquisa="plan-1-aaaaaaaa",
        status_pipeline="concluido",
        dossier_final="# Dossiê\n\nConteúdo final.",
    )
    ponto = SimpleNamespace(
        ponto_id="plan-1-aaaaaaaa-p1",
        ponto_n=1,
        status="aprovado",
        pontos_fracos=None,
        reasoning_auditoria=json.dumps(_rodada()),
    )

    auditoria = _build_auditoria(pesquisa, [ponto])

    assert auditoria is not None
    item = auditoria["auditorias"][0]
    assert item["criterios_aprovados"] == 12
    assert item["criterios_minimos"] == 11
    assert item["criterios"] is not None and len(item["criterios"]) == 12
    assert item["status"] == "aprovado"
    assert "12/12" in item["resumo_auditoria"]
    assert item["reasoning_auditoria"]


def test_get_research_reprovada_nao_finge_aprovacao():
    pesquisa = SimpleNamespace(id_pesquisa="plan-1-bbbbbbbb", status_pipeline="reprovado")
    ponto = SimpleNamespace(
        ponto_id="p1",
        ponto_n=1,
        status="reprovado",
        pontos_fracos="faltou fonte primária",
        reasoning_auditoria=json.dumps(_rodada("REPROVADO", 9)),
    )
    item = _build_auditoria(pesquisa, [ponto])["auditorias"][0]
    assert item["status"] == "reprovado"
    assert item["criterios_aprovados"] == 12  # o dado persistido manda, não o status do ponto
    assert item["valido"] is False


def test_stream_nao_emite_chaves_json_brutas_no_reasoning(tmp_path):
    (tmp_path / "AUDITORIA.json").write_text(json.dumps({"rodadas": [_rodada()]}), encoding="utf-8")
    watcher = hermes_stream.WatchHermes("plan-1-cccccccc", tmp_path)
    eventos: list[tuple[str, dict]] = []
    watcher._pub = lambda evento, **dados: eventos.append((evento, dados))  # type: ignore[assignment]

    watcher._tick()

    textos = [json.dumps(dados, ensure_ascii=False) for _, dados in eventos]
    assert textos, "nenhum evento publicado"
    for texto in textos:
        assert '{"rodada"' not in texto
        assert '"paginas_lidas":' not in texto
        assert '"criterios": [' not in texto
    assert any("Rodada 2" in t for t in textos)
