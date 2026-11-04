"""Consumo ao vivo: o watcher publica os tokens reais enquanto o ciclo roda."""

from __future__ import annotations

import json

from app.core import hermes_stream


def _eventos(watcher) -> list[tuple[str, dict]]:
    capturados: list[tuple[str, dict]] = []
    watcher._pub = lambda evento, **dados: capturados.append((evento, dados))  # type: ignore[assignment]
    return capturados


def _uso(ws, entrada: int, saida: int) -> None:
    (ws / "usage.json").write_text(
        json.dumps({"input_tokens": entrada, "output_tokens": saida, "total_tokens": entrada + saida}),
        encoding="utf-8",
    )


def test_usage_progress_publica_tokens_reais_durante_o_ciclo(tmp_path):
    watcher = hermes_stream.WatchHermes("plan-1-aaaaaaaa", tmp_path)
    eventos = _eventos(watcher)

    watcher._tick()
    assert not [e for e in eventos if e[0] == "usage.progress"], "sem usage.json não inventa token"

    _uso(tmp_path, 20000, 4000)
    eventos.clear()
    watcher._tick()
    uso = [e for e in eventos if e[0] == "usage.progress"]
    assert len(uso) == 1
    assert uso[0][1]["tokens_total"] == 24000
    assert uso[0][1]["tokens_prompt"] == 20000

    # Mesmo total: não repete evento.
    eventos.clear()
    watcher._tick()
    assert not [e for e in eventos if e[0] == "usage.progress"]

    # Turno seguinte maior: publica o novo total.
    _uso(tmp_path, 26000, 5000)
    eventos.clear()
    watcher._tick()
    uso = [e for e in eventos if e[0] == "usage.progress"]
    assert uso and uso[0][1]["tokens_total"] == 31000
