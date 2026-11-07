from __future__ import annotations

from conftest import FakeExecutor
from fastapi.testclient import TestClient

from api import create_app
from orchestrator import Pipeline


def _cliente(config, repositorio, responder):
    pipeline = Pipeline(repositorio, FakeExecutor(responder), config, notificador=lambda *a, **k: None)
    return TestClient(create_app(pipeline))


def _responder(papel, payload):
    if papel == "planner":
        return {"pontos": [{
            "ponto_id": 1,
            "enunciado": "Ponto único",
            "subperguntas": ["a", "b", "c"],
            "hipoteses": ["a", "b", "c"],
            "lacunas_iniciais": ["a", "b", "c"],
        }]}
    if papel in ("historiador", "cetico", "visionario", "futurista"):
        return {"informacao_coletada": "x", "urls_usadas": [], "urls_lidas": []}
    if papel == "auditor":
        return {"perguntas_respondidas": {str(i): True for i in range(1, 13)}}
    return {"relatorio_ponto": "R", "lacunas_identificadas": "nenhuma"}


def test_sem_chave_aberto(config, repositorio, monkeypatch):
    monkeypatch.delenv("DR_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    cliente = _cliente(config, repositorio, _responder)
    assert cliente.get("/health").status_code == 200
    assert cliente.get("/config").status_code == 200


def test_com_chave_exige_e_aceita_formas(config, repositorio, monkeypatch):
    monkeypatch.setenv("DR_API_KEY", "segredo")
    cliente = _cliente(config, repositorio, _responder)

    # Saúde sempre aberta, mesmo com chave configurada.
    assert cliente.get("/health").status_code == 200
    assert cliente.get("/health", headers={"X-API-Key": "errada"}).status_code == 200

    negada = cliente.post(
        "/research",
        json={"tema": "x" * 10, "profundidade": 1, "veracidade_alvo": 90,
              "max_rodadas_auditoria": 1, "atualidade": "24H",
              "callback_url": "https://webhook.example/cb"},
    )
    assert negada.status_code == 401
    assert negada.json() == {"detail": "API key inválida"}

    corpo = {"tema": "x" * 10, "profundidade": 1, "veracidade_alvo": 90,
             "max_rodadas_auditoria": 1, "atualidade": "24H",
             "callback_url": "https://webhook.example/cb"}
    assert cliente.post("/research", json=corpo, headers={"X-API-Key": "segredo"}).status_code == 202
    assert cliente.post("/research", json=corpo,
                        headers={"Authorization": "Bearer segredo"}).status_code == 202
    assert cliente.get("/research/NOPE", headers={"X-API-Key": "segredo"}).status_code == 404


def test_sse_aceita_query_api_key(config, repositorio, monkeypatch):
    from test_eventos import requisicao, responder

    monkeypatch.setenv("DR_API_KEY", "segredo")
    pipeline = Pipeline(repositorio, FakeExecutor(responder), config, notificador=lambda *a, **k: None)
    cliente = TestClient(create_app(pipeline))
    rid = pipeline.criar(requisicao(profundidade=1, veracidade_alvo=0, max_rodadas_auditoria=1))

    assert cliente.get(f"/research/{rid}/eventos").status_code == 401
    blocos: list[str] = []
    atual: list[str] = []
    with cliente.stream("GET", f"/research/{rid}/eventos", params={"api_key": "segredo"}) as resposta:
        assert resposta.status_code == 200
        for linha in resposta.iter_lines():
            if linha == "":
                if atual:
                    blocos.append("\n".join(atual))
                    atual = []
                    break
            elif not linha.startswith(":"):
                atual.append(linha)
    assert blocos and "event: snapshot" in blocos[0]
