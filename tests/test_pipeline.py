from __future__ import annotations

import sqlite3

import pytest

from conftest import FakeExecutor
from contracts import PERSONAS, ResearchRequest
from orchestrator import Pipeline, PipelineError


def ponto(ponto_id: int) -> dict:
    return {
        "ponto_id": ponto_id,
        "enunciado": f"Ponto {ponto_id}",
        "subperguntas": [f"s{ponto_id}-{i}" for i in (1, 2, 3)],
        "hipoteses": [f"h{ponto_id}-{i}" for i in (1, 2, 3)],
        "lacunas_iniciais": [f"l{ponto_id}-{i}" for i in (1, 2, 3)],
    }


def responder(papel, payload):
    if papel == "planner":
        return {"pontos": [ponto(i) for i in range(1, payload["profundidade"] + 1)]}
    if papel in PERSONAS:
        rodada = payload["rodada"]
        ponto_id = payload["ponto_id"]
        return {
            "informacao_coletada": f"coleta {papel} rodada {rodada} ponto {ponto_id}",
            "urls_usadas": [f"https://fonte/{papel}/{ponto_id}/{rodada}"],
            "urls_lidas": [
                f"https://fonte/{papel}/{ponto_id}/{rodada}",
                f"https://ignorada/{papel}/{ponto_id}/{rodada}",
            ],
        }
    if papel == "auditor":
        respostas = {str(i): True for i in range(1, 13)}
        if payload["tentativa_atual"] == 1:
            respostas.update({"4": False, "8": False, "10": False})
        else:
            respostas["8"] = False
        return {"perguntas_respondidas": respostas}
    if papel == "redator":
        acumulado = payload["informacao_coletada_acumulada_integral"]
        return {
            "relatorio_ponto": f"RELATORIO ponto {payload['ponto_id']} com {len(acumulado)} rodadas",
            "lacunas_identificadas": f"faltou a pergunta 8 do ponto {payload['ponto_id']}",
            "urls_citadas": payload["urls_usadas_acumuladas"],
        }
    raise AssertionError(f"papel inesperado: {papel}")


@pytest.fixture
def pipeline(config, repositorio):
    engine = FakeExecutor(responder)
    webhooks: list[tuple[str, dict]] = []
    pipeline = Pipeline(
        repositorio,
        engine,
        config,
        notificador=lambda url, payload, timeout_s: webhooks.append((url, payload)),
    )
    pipeline.engine_fake = engine
    pipeline.webhooks = webhooks
    return pipeline


def test_pipeline_completo_com_retentativa_e_webhook(config, repositorio, pipeline):
    requisicao = ResearchRequest(
        tema="matriz energética brasileira",
        profundidade=2,
        veracidade_alvo=90,
        max_rodadas_auditoria=4,
        atualidade="24H",
        callback_url="https://webhook.example/cb",
    )
    research_id = pipeline.criar(requisicao)
    pipeline.executar(research_id)

    run = repositorio.obter_run(research_id)
    assert run["status"] == "COMPLETED"
    assert "## 1. Ponto 1" in run["relatorio_final_consolidado"]
    assert run["relatorio_final_consolidado"].index("## 1.") < run[
        "relatorio_final_consolidado"
    ].index("## 2.")

    pontos = repositorio.obter_pontos(research_id)
    assert [ponto["aprovado"] for ponto in pontos] == [True, True]
    assert [ponto["porcentagem_aprovacao"] for ponto in pontos] == [91.67, 91.67]
    assert [ponto["rodada_atual"] for ponto in pontos] == [2, 2]
    assert pontos[0]["ultimo_resultado_auditor"]["8"] is False

    engine: FakeExecutor = pipeline.engine_fake
    auditorias = engine.payloads("auditor")
    for ponto_id in (1, 2):
        primeira = next(
            p for p in auditorias if p["ponto_id"] == ponto_id and p["tentativa_atual"] == 1
        )
        assert [bloco["rodada"] for bloco in primeira["informacao_coletada_acumulada"]] == [1]

        segunda = next(
            p for p in auditorias if p["ponto_id"] == ponto_id and p["tentativa_atual"] == 2
        )
        blocos = segunda["informacao_coletada_acumulada"]
        assert [bloco["rodada"] for bloco in blocos] == [1, 2]
        assert blocos[0]["historiador"] == f"coleta historiador rodada 1 ponto {ponto_id}"
        assert blocos[1]["futurista"] == f"coleta futurista rodada 2 ponto {ponto_id}"

    persona_rodada_2 = next(
        p for p in engine.payloads("historiador") if p["ponto_id"] == 1 and p["rodada"] == 2
    )
    assert set(persona_rodada_2["perguntas_auditoria_pendentes"]) == {"4", "8", "10"}
    from contracts import PERGUNTAS_AUDITORIA_ESTATICAS

    assert (
        persona_rodada_2["perguntas_auditoria_pendentes"]["8"]
        == PERGUNTAS_AUDITORIA_ESTATICAS["8"]
    )
    assert len(persona_rodada_2["urls_lidas_ignoradas"]) == 8  # 4 personas x 2 URLs na rodada 1
    assert all("fonte/" in url or "ignorada/" in url for url in persona_rodada_2["urls_lidas_ignoradas"])

    redator = next(p for p in engine.payloads("redator") if p["ponto_id"] == 1)
    assert redator["resultado_final_auditor"]["8"] is False
    assert len(redator["informacao_coletada_acumulada_integral"]) == 2
    assert len(redator["urls_usadas_acumuladas"]) == 8

    # 1 planner + 2 pontos x (8 personas + 2 auditorias + 1 redator)
    with sqlite3.connect(config.pipeline.db_path) as con:
        total_execucoes = con.execute("SELECT COUNT(*) FROM agent_executions").fetchone()[0]
    assert total_execucoes == 23
    assert run["total_tokens"] == 23 * 160

    assert len(pipeline.webhooks) == 1
    url, payload = pipeline.webhooks[0]
    assert url == "https://webhook.example/cb"
    assert set(payload) == {
        "research_id",
        "relatorio_final",
        "lacunas_finais",
        "urls_usadas",
        "urls_lidas",
        "urls_lidas_nao_usadas",
        "avaliacao_pontos",
        "pontos_falhos",
        "metricas_tokens",
    }
    assert payload["pontos_falhos"] == []
    assert len(payload["urls_usadas"]) == 16  # 2 pontos x 4 personas x 2 rodadas
    assert len(payload["urls_lidas"]) == 32
    assert len(payload["urls_lidas_nao_usadas"]) == 16
    assert payload["metricas_tokens"]["total_tokens"] == 23 * 160

    boletim = payload["avaliacao_pontos"]
    assert boletim["research_id"] == research_id
    assert boletim["tentativa_atual"] == 2
    assert boletim["tema"] == "matriz energética brasileira"
    assert boletim["avaliacao_pontos"] == [
        {
            "ponto_id": 1, "perguntas_true": 11, "total_perguntas": 12,
            "porcentagem_aprovacao": 91.67, "meta_veracidade_alvo": 90.0,
            "aprovado": True,
        },
        {
            "ponto_id": 2, "perguntas_true": 11, "total_perguntas": 12,
            "porcentagem_aprovacao": 91.67, "meta_veracidade_alvo": 90.0,
            "aprovado": True,
        },
    ]
    assert "## Avaliação de veracidade" in run["relatorio_final_consolidado"]
    assert "- Ponto 1: 11/12 (91.67%) — aprovado" in run["relatorio_final_consolidado"]


def test_get_inclui_avaliacao_e_secao_no_dossie(config, repositorio, pipeline):
    """Q-02: GET expõe avaliacao_pontos (SDD §5.7) e dossiê traz a seção."""
    from fastapi.testclient import TestClient

    from api import create_app

    cliente = TestClient(create_app(pipeline))
    resposta = cliente.post(
        "/research",
        json={
            "tema": "matriz energética brasileira",
            "profundidade": 2,
            "veracidade_alvo": 90,
            "max_rodadas_auditoria": 4,
            "atualidade": "24H",
            "callback_url": "https://webhook.example/cb",
        },
    )
    assert resposta.status_code == 202
    research_id = resposta.json()["research_id"]

    corpo = cliente.get(f"/research/{research_id}").json()
    boletim = corpo["avaliacao_pontos"]
    assert boletim["research_id"] == research_id
    assert boletim["tentativa_atual"] == 2
    assert boletim["tema"] == "matriz energética brasileira"
    assert [p["ponto_id"] for p in boletim["avaliacao_pontos"]] == [1, 2]
    assert [p["porcentagem_aprovacao"] for p in boletim["avaliacao_pontos"]] == [91.67, 91.67]
    assert all(p["aprovado"] for p in boletim["avaliacao_pontos"])
    assert "## Avaliação de veracidade" in corpo["relatorio_final_consolidado"]
    assert "- Ponto 1: 11/12 (91.67%) — aprovado" in corpo["relatorio_final_consolidado"]
    # Ordem dos relatórios preservada: ## 1..N antes da seção de avaliação.
    assert corpo["relatorio_final_consolidado"].index("## 2.") < corpo[
        "relatorio_final_consolidado"
    ].index("## Avaliação de veracidade")


def test_get_sem_pontos_omite_avaliacao(config, repositorio, pipeline):
    """Run recém-criado (sem pontos) não expõe avaliacao_pontos."""
    from fastapi.testclient import TestClient

    from api import create_app
    from contracts import ResearchRequest

    research_id = pipeline.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=1,
            veracidade_alvo=90,
            callback_url="https://webhook.example/cb",
        )
    )
    corpo = TestClient(create_app(pipeline)).get(f"/research/{research_id}").json()
    assert "avaliacao_pontos" not in corpo


def test_planner_invalido_retenta_e_registra_tentativa_rejeitada(config, repositorio):
    tentativas = {"planner": 0}

    def responder_com_falha(papel, payload):
        if papel == "planner":
            tentativas["planner"] += 1
            if tentativas["planner"] == 1:
                # Primeira tentativa inválida: profundidade errada (1 ponto, esperado 2).
                return {"pontos": [ponto(1)]}
        return responder(papel, payload)

    engine = FakeExecutor(responder_com_falha)
    pipeline = Pipeline(
        repositorio, engine, config, notificador=lambda *args, **kwargs: None
    )
    research_id = pipeline.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=2,
            veracidade_alvo=90,
            callback_url="https://webhook.example/cb",
        )
    )
    pipeline.executar(research_id)

    assert repositorio.obter_run(research_id)["status"] == "COMPLETED"
    assert len(engine.payloads("planner")) == 2
    with sqlite3.connect(config.pipeline.db_path) as con:
        rejeitadas = con.execute(
            "SELECT COUNT(*) FROM agent_executions WHERE agent_role = 'planner'"
        ).fetchone()[0]
    assert rejeitadas == 2


def test_falha_de_uma_persona_nao_derruba_o_ponto(config, repositorio):
    def responder_sem_cetico(papel, payload):
        if papel == "cetico":
            raise RuntimeError("provider fora do ar")
        return responder(papel, payload)

    engine = FakeExecutor(responder_sem_cetico)
    pipeline = Pipeline(repositorio, engine, config, notificador=lambda *args, **kwargs: None)
    research_id = pipeline.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=1,
            veracidade_alvo=90,
            callback_url="https://webhook.example/cb",
        )
    )
    pipeline.executar(research_id)

    assert repositorio.obter_run(research_id)["status"] == "COMPLETED"
    auditoria = engine.payloads("auditor")[0]
    personas = set(auditoria["informacao_coletada_acumulada"][0]) - {"rodada"}
    assert personas == {"historiador", "visionario", "futurista"}


def test_falha_total_do_run_marca_failed_quando_nenhum_ponto_redigiu(config, repositorio):
    """Run inteiro falhou (único ponto sem coleta) → FAILED + evento run.falhou."""
    def responder_quebrado(papel, payload):
        if papel in PERSONAS:
            raise RuntimeError("sem engine")
        return responder(papel, payload)

    pipeline = Pipeline(
        repositorio, FakeExecutor(responder_quebrado), config, notificador=lambda *a, **k: None
    )
    research_id = pipeline.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=1,
            veracidade_alvo=90,
            callback_url="https://webhook.example/cb",
        )
    )
    with pytest.raises(ValueError, match="nenhum ponto com relatório"):
        pipeline.executar(research_id)

    assert repositorio.obter_run(research_id)["status"] == "FAILED"
    tipos = [e["tipo"] for e in repositorio.listar_eventos(research_id)]
    assert "ponto.erro" in tipos and "run.falhou" in tipos


class ExecutorLoteContado(FakeExecutor):
    """FakeExecutor que registra o tamanho de cada lote de `executar`."""

    def __init__(self, responder):
        super().__init__(responder)
        self.tamanhos_lote: list[int] = []

    def executar(self, workspace, tarefas):
        self.tamanhos_lote.append(len(tarefas))
        return super().executar(workspace, tarefas)


def test_coleta_fan_out_40_em_um_lote(config, repositorio):
    """RF02/SDD §2: 10 pontos x 4 personas = 40 tarefas num SÓ `executar`."""
    engine = ExecutorLoteContado(responder)
    pipeline = Pipeline(
        repositorio, engine, config, notificador=lambda *args, **kwargs: None
    )
    research_id = pipeline.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=10,
            veracidade_alvo=0,  # aprovado sempre: só 1 rodada de coleta
            max_rodadas_auditoria=1,
            atualidade="24H",
            callback_url="https://webhook.example/cb",
        )
    )
    pipeline.executar(research_id)

    assert engine.tamanhos_lote[0] == 40  # primeiro lote de coleta: 10 x 4
    assert max(engine.tamanhos_lote) == 40
    assert len(engine.payloads("historiador")) == 10
    assert repositorio.obter_run(research_id)["status"] == "COMPLETED"


def test_get_expõe_historico_de_auditorias_ordenado(config, repositorio, pipeline):
    """D-04: pipeline com 1 ponto e 2 rodadas → GET com 2 auditorias ordenadas."""
    from fastapi.testclient import TestClient

    from api import create_app

    cliente = TestClient(create_app(pipeline))
    resposta = cliente.post(
        "/research",
        json={
            "tema": "matriz energética brasileira",
            "profundidade": 1,
            "veracidade_alvo": 90,
            "max_rodadas_auditoria": 4,
            "atualidade": "24H",
            "callback_url": "https://webhook.example/cb",
        },
    )
    assert resposta.status_code == 202
    research_id = resposta.json()["research_id"]

    corpo = cliente.get(f"/research/{research_id}").json()
    auditorias = corpo["auditorias"]
    assert [a["rodada"] for a in auditorias] == [1, 2]
    assert all(a["ponto_id"] == 1 for a in auditorias)
    assert auditorias[0]["perguntas_respondidas"] != auditorias[1]["perguntas_respondidas"]
    # Rodada 1: 9/12 = 75% < 90 → reprovada; rodada 2: 11/12 = 91.67 ≥ 90 → aprovada.
    assert auditorias[0]["aprovado"] is False
    assert auditorias[0]["porcentagem_aprovacao"] == 75.0
    assert auditorias[0]["perguntas_true"] == 9
    assert auditorias[1]["aprovado"] is True
    assert auditorias[1]["porcentagem_aprovacao"] == 91.67
    assert auditorias[1]["perguntas_true"] == 11
    for auditoria in auditorias:
        assert auditoria["meta_veracidade_alvo"] == 90
        assert auditoria["model_used"] == "fake/auditor"


def test_planner_registra_urls_lidas_e_usadas(config, repositorio):
    """D-07: planner devolve 2 lidas/1 usada → linha do planner e consolidação global."""
    from conftest import FakeExecutor

    def responder_com_urls(papel, payload):
        if papel == "planner":
            saida = responder(papel, payload)
            saida["urls_lidas"] = ["https://varredura/a", "https://varredura/b"]
            saida["urls_usadas"] = ["https://varredura/a"]
            return saida
        return responder(papel, payload)

    engine = FakeExecutor(responder_com_urls)
    condutor = Pipeline(
        repositorio, engine, config, notificador=lambda *a, **k: None
    )
    research_id = condutor.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=1,
            veracidade_alvo=0,  # aprovado sempre: só 1 rodada
            max_rodadas_auditoria=1,
            atualidade="24H",
            callback_url="https://webhook.example/cb",
        )
    )
    condutor.executar(research_id)

    linhas = [
        e
        for e in repositorio.obter_execucoes(research_id)
        if e["agent_role"] == "planner"
    ]
    assert len(linhas) == 1
    assert linhas[0]["urls_usadas"] == ["https://varredura/a"]
    assert linhas[0]["urls_lidas"] == ["https://varredura/a", "https://varredura/b"]

    run = repositorio.obter_run(research_id)
    assert "https://varredura/a" in run["urls_usadas_globais"]
    assert "https://varredura/b" in run["urls_lidas_globais"]
    assert "https://varredura/b" in run["urls_nao_usadas_globais"]


def test_planner_com_url_invalida_retenta_ou_falha(config, repositorio):
    """D-07: URL inválida do planner → retentativa (2ª válida vence)."""
    from conftest import FakeExecutor

    chamadas = {"planner": 0}

    def responder_invalida_primeiro(papel, payload):
        if papel == "planner":
            chamadas["planner"] += 1
            saida = responder(papel, payload)
            if chamadas["planner"] == 1:
                saida["urls_usadas"] = ["ftp://invalida/x"]
            return saida
        return responder(papel, payload)

    engine = FakeExecutor(responder_invalida_primeiro)
    condutor = Pipeline(
        repositorio, engine, config, notificador=lambda *a, **k: None
    )
    research_id = condutor.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=1,
            veracidade_alvo=0,
            max_rodadas_auditoria=1,
            atualidade="24H",
            callback_url="https://webhook.example/cb",
        )
    )
    condutor.executar(research_id)

    assert chamadas["planner"] == 2
    assert repositorio.obter_run(research_id)["status"] == "COMPLETED"


def test_planner_sem_perguntas_plano_tem_estaticas_identicas(config, repositorio):
    """Planner omite perguntas_auditoria → backend injeta as 12 estáticas iguais."""
    from contracts import PERGUNTAS_AUDITORIA_ESTATICAS

    engine = FakeExecutor(responder)
    condutor = Pipeline(
        repositorio, engine, config, notificador=lambda *a, **k: None
    )
    research_id = condutor.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=2,
            veracidade_alvo=0,
            max_rodadas_auditoria=1,
            callback_url="https://webhook.example/cb",
        )
    )
    condutor.executar(research_id)

    pontos = repositorio.obter_pontos(research_id)
    assert len(pontos) == 2
    for ponto_db in pontos:
        assert ponto_db["perguntas_auditoria"] == PERGUNTAS_AUDITORIA_ESTATICAS
    assert pontos[0]["perguntas_auditoria"] == pontos[1]["perguntas_auditoria"]
    auditor = next(p for p in engine.payloads("auditor") if p["ponto_id"] == 1)
    assert auditor["perguntas_auditoria"] == PERGUNTAS_AUDITORIA_ESTATICAS


def test_planner_com_perguntas_custom_sao_sobrescritas(config, repositorio):
    """Planner mandando perguntas próprias → backend sobrescreve com estáticas."""
    from contracts import PERGUNTAS_AUDITORIA_ESTATICAS

    def responder_custom(papel, payload):
        if papel == "planner":
            return {
                "pontos": [
                    {
                        "ponto_id": 1,
                        "enunciado": "P1",
                        "subperguntas": ["a", "b", "c"],
                        "hipoteses": ["h1", "h2", "h3"],
                        "lacunas_iniciais": ["l1", "l2", "l3"],
                        "perguntas_auditoria": {
                            str(i): f"custom {i}" for i in range(1, 13)
                        },
                    }
                ]
            }
        return responder(papel, payload)

    condutor = Pipeline(
        repositorio, FakeExecutor(responder_custom), config,
        notificador=lambda *a, **k: None,
    )
    research_id = condutor.criar(
        ResearchRequest(
            tema="matriz energética",
            profundidade=1,
            veracidade_alvo=0,
            max_rodadas_auditoria=1,
            callback_url="https://webhook.example/cb",
        )
    )
    condutor.executar(research_id)

    pontos = repositorio.obter_pontos(research_id)
    assert pontos[0]["perguntas_auditoria"] == PERGUNTAS_AUDITORIA_ESTATICAS


def test_boletim_exclui_ponto_nao_auditado(config, repositorio):
    """2 pontos, 1 auditado → avaliacao_pontos só com o auditado."""
    from contracts import PERGUNTAS_AUDITORIA_ESTATICAS, PontoPlano

    requisicao = ResearchRequest(
        tema="matriz energética",
        profundidade=2,
        veracidade_alvo=90,
        callback_url="https://webhook.example/cb",
    )
    repositorio.criar_run("R-PARCIAL", requisicao)
    pontos = [
        PontoPlano(
            ponto_id=1, enunciado="P1",
            subperguntas=["a", "b", "c"], hipoteses=["a", "b", "c"],
            lacunas_iniciais=["a", "b", "c"],
            perguntas_auditoria=dict(PERGUNTAS_AUDITORIA_ESTATICAS),
        ),
        PontoPlano(
            ponto_id=2, enunciado="P2",
            subperguntas=["a", "b", "c"], hipoteses=["a", "b", "c"],
            lacunas_iniciais=["a", "b", "c"],
            perguntas_auditoria=dict(PERGUNTAS_AUDITORIA_ESTATICAS),
        ),
    ]
    repositorio.salvar_plano("R-PARCIAL", {"pontos": []}, pontos)
    repositorio.salvar_auditoria(
        research_id="R-PARCIAL",
        ponto_id=1,
        rodada=1,
        perguntas_respondidas={str(i): True for i in range(1, 13)},
        decisao={
            "porcentagem_aprovacao": 100.0,
            "aprovado": True,
        },
    )

    boletim = repositorio.obter_avaliacao("R-PARCIAL")
    assert boletim is not None
    assert [item["ponto_id"] for item in boletim["avaliacao_pontos"]] == [1]

    sem_nada = ResearchRequest(
        tema="matriz energética",
        profundidade=1,
        veracidade_alvo=90,
        callback_url="https://webhook.example/cb",
    )
    repositorio.criar_run("R-VAZIO", sem_nada)
    repositorio.salvar_plano(
        "R-VAZIO",
        {"pontos": []},
        [PontoPlano(
            ponto_id=1, enunciado="P1",
            subperguntas=["a", "b", "c"], hipoteses=["a", "b", "c"],
            lacunas_iniciais=["a", "b", "c"],
        )],
    )
    assert repositorio.obter_avaliacao("R-VAZIO") is None
