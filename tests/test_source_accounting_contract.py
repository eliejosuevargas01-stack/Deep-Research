"""Contabilidade de fontes: URL sanitizada e `urls_lidas` distinto de `urls_fonte`."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import hermes_adapter
from app.core.urls import sanitizar_url_fonte


class _Repo:
    def __init__(self) -> None:
        self.salvos = []
        self.status = []
        self.tokens = None

    async def get_collected_content(self, _id):
        return None

    async def list_points(self, _id):
        return [SimpleNamespace(ponto_id="p1", ponto_n=1, ponto="Q1")]

    async def save_collected_content(self, **kwargs):
        self.salvos.append(kwargs)

    async def update_pipeline_status(self, _id, status):
        self.status.append(status)

    async def get_research(self, _id):
        return SimpleNamespace(tokens_prompt=0, tokens_completion=0, tokens_total=0)

    async def set_research_tokens(self, _id, prompt, completion, total):
        self.tokens = (prompt, completion, total)


def test_sanitizar_url_rejeita_lixo_e_remove_escape_literal_n():
    assert sanitizar_url_fonte("https://^") is None
    assert sanitizar_url_fonte("https:///;") is None
    assert sanitizar_url_fonte("https://{host}/w/api.php?") is None
    assert sanitizar_url_fonte("https://epe.gov.br/relatorio\\nAirbnb") == "https://epe.gov.br/relatorio"
    # pontuação final de frase não faz parte da URL
    assert sanitizar_url_fonte("(https://www.epe.gov.br/dados).") == "https://www.epe.gov.br/dados"
    # motores de busca não são fonte
    assert sanitizar_url_fonte("https://duckduckgo.com/html/?q=x") is None


@pytest.mark.asyncio
async def test_persistir_busca_preserva_urls_lidas_distintas_de_urls_fonte(tmp_path: Path, monkeypatch):
    workspace = tmp_path
    (workspace / "HISTORIADOR_SEARCH.json").write_text(
        json.dumps(
            {
                "persona": "historiador",
                "tentativas": [
                    {
                        "rodada": 1,
                        "consultas": ["matriz energetica brasil"],
                        "analise": "Achados com fontes.",
                        "urls_fonte": ["https://epe.gov.br/relatorio\\nAirbnb", "https://^"],
                        "urls_lidas": [
                            "https://epe.gov.br/relatorio\\nAirbnb",
                            "https://exemplo.com/leitura",
                            "https://duckduckgo.com/html/?q=matriz",
                        ],
                        "paginas_lidas": 3,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    repo = _Repo()
    pesquisa = SimpleNamespace(id_pesquisa="plan-1-aaaaaaaa", tema="Matriz energetica")

    await hermes_adapter.persistir_busca(repo, pesquisa, workspace)

    salvo = repo.salvos[0]
    assert salvo["urls_fonte"] == ["https://epe.gov.br/relatorio"]
    assert set(salvo["urls_lidas"]) == {"https://epe.gov.br/relatorio", "https://exemplo.com/leitura"}
    assert set(salvo["urls_fonte"]).issubset(set(salvo["urls_lidas"]))
    assert salvo["urls_lidas"] != salvo["urls_fonte"]
    assert repo.status == ["coletado"]
