"""Catálogo v3 aceita URL eleita sem leitura como snippet_only (RF-004-D)."""

from app.core.searcher import _catalogo_de_urls, _fontes_da_persona


def test_url_eleita_sem_leitura_entra_como_snippet_only():
    ponto_sources = {
        "https://lida.example/a": {"url": "https://lida.example/a", "status": "read_ok", "titulo": "A"},
        "https://serp.example/b": {"url": "https://serp.example/b", "status": "snippet_only", "titulo": "B"},
    }
    personas = [{"urls_fonte": ["https://lida.example/a", "https://serp.example/b"]}]

    catalogo = _catalogo_de_urls(ponto_sources, personas)

    assert catalogo["https://lida.example/a"]["status"] == "read_ok"
    assert catalogo["https://serp.example/b"]["status"] == "snippet_only"
    assert catalogo["https://serp.example/b"]["uso"] == "utilizada"


def test_url_eleita_fora_da_serp_ainda_entra_no_catalogo():
    catalogo = _catalogo_de_urls({}, [{"urls_fonte": ["https://citada.example/x"]}])

    assert catalogo["https://citada.example/x"]["status"] == "snippet_only"
    assert catalogo["https://citada.example/x"]["uso"] == "utilizada"


def test_fontes_da_persona_preserva_status_snippet_only():
    catalogo = {
        "https://lida.example/a": {"status": "read_ok", "titulo": "A"},
        "https://serp.example/b": {"status": "snippet_only", "titulo": "B"},
    }

    fontes = _fontes_da_persona(
        ["https://lida.example/a"],
        ["https://lida.example/a", "https://serp.example/b"],
        catalogo,
    )
    por_url = {f["url"]: f for f in fontes}

    assert por_url["https://lida.example/a"]["uso"] == "utilizada"
    assert por_url["https://serp.example/b"]["status"] == "snippet_only"
