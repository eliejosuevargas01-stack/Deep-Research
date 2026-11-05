from __future__ import annotations

from conftest import FakeExecutor
from fastapi.testclient import TestClient

from api import create_app
from orchestrator import Pipeline

PONTO = {
    "ponto_id": 1,
    "enunciado": "Ponto único",
    "subperguntas": ["a", "b", "c"],
    "hipoteses": ["a", "b", "c"],
    "lacunas_iniciais": ["a", "b", "c"],
    "perguntas_auditoria": {str(i): f"Pergunta {i}" for i in range(1, 13)},
}


def responder(papel, payload):
    if papel == "planner":
        return {"pontos": [PONTO]}
    if papel in ("historiador", "cetico", "visionario", "futurista"):
        return {
            "informacao_coletada": f"{papel} coletou",
            "urls_usadas": [f"https://fonte/{papel}"],
            "urls_lidas": [f"https://fonte/{papel}"],
        }
    if papel == "auditor":
        return {"perguntas_respondidas": {str(i): True for i in range(1, 13)}}
    return {"relatorio_ponto": "RELATORIO", "lacunas_identificadas": "nenhuma"}


def test_api_cria_e_consulta_pesquisa(config, repositorio):
    pipeline = Pipeline(
        repositorio, FakeExecutor(responder), config, notificador=lambda *a, **k: None
    )
    cliente = TestClient(create_app(pipeline))

    assert cliente.get("/health").json() == {"status": "ok"}

    resposta = cliente.post(
        "/research",
        json={
            "tema": "matriz energética",
            "profundidade": 1,
            "veracidade_alvo": 90,
            "max_rodadas_auditoria": 4,
            "atualidade": "24H",
            "callback_url": "https://webhook.example/cb",
        },
    )
    assert resposta.status_code == 202
    research_id = resposta.json()["research_id"]

    consulta = cliente.get(f"/research/{research_id}")
    assert consulta.status_code == 200
    corpo = consulta.json()
    assert corpo["status"] == "COMPLETED"
    assert corpo["relatorio_final_consolidado"] == "## 1. Ponto único\n\nRELATORIO"
    assert corpo["pontos"][0]["aprovado"] is True


def test_api_rejeita_payload_invalido(config, repositorio):
    cliente = TestClient(create_app(Pipeline(repositorio, FakeExecutor(responder), config)))
    resposta = cliente.post("/research", json={"tema": "x", "profundidade": 11})
    assert resposta.status_code == 422

    assert cliente.get("/research/NAOEXISTE").status_code == 404
