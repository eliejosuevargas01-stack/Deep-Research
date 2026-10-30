"""Testes da política temporal canônica (recência por padrão, histórico explícito)."""

from datetime import date, datetime, timezone

from app.core.temporal import (
    RecencyPolicy,
    build_discovery_queries,
    build_recency_aware_query,
    build_recency_block,
    current_reference_date,
    has_explicit_past_scope,
    parse_any_date,
    rank_serp_items_by_freshness,
    reference_now,
    resolve_recency_policy,
    source_date_from_item,
)

REF = date(2026, 10, 26)


def test_sem_recorte_usa_estado_mais_recente() -> None:
    policy = resolve_recency_policy("Pesquise sobre a situação atual da Venezuela", reference=REF)
    assert policy.mode == "recente"
    assert policy.force_current_year is True
    assert policy.year == 2026
    assert policy.window_days == 365


def test_recorte_historico_explicito_e_preservado() -> None:
    policy = resolve_recency_policy("Análise histórica da Venezuela entre 2000 e 2024", reference=REF)
    assert policy.mode == "historico"
    assert policy.force_current_year is False


def test_termo_de_atualidade_vence_ano_passado_mencionado() -> None:
    policy = resolve_recency_policy(
        "Atualize a cobertura da eleição de 2024 com as notícias mais recentes",
        reference=REF,
    )
    assert policy.force_current_year is True


def test_override_historico_nao_e_sobrescrito() -> None:
    policy = resolve_recency_policy(
        "Faça uma pesquisa sobre a Venezuela",
        requested_mode="historico",
        reference=REF,
    )
    assert policy.is_historical is True


def test_consulta_recebe_ancora_do_ano_corrente_sem_reescrever_intencao() -> None:
    policy = resolve_recency_policy("situação da Venezuela", reference=REF)
    assert build_recency_aware_query("situação da Venezuela", policy) == "situação da Venezuela 2026"


def test_consulta_com_data_ou_operador_nao_e_ancorada() -> None:
    policy = resolve_recency_policy("situação da Venezuela", reference=REF)
    assert build_recency_aware_query("eleição de 2024 na Venezuela", policy) == "eleição de 2024 na Venezuela"
    assert build_recency_aware_query("site:gov.br Venezuela", policy) == "site:gov.br Venezuela"
    assert build_recency_aware_query("notícias recentes sobre a Venezuela", policy) == "notícias recentes sobre a Venezuela"


def test_descoberta_recente_inclui_consulta_ancorada() -> None:
    policy = resolve_recency_policy("situação da Venezuela", reference=REF)
    assert build_discovery_queries("situação da Venezuela", policy) == [
        "situação da Venezuela",
        "situação da Venezuela 2026",
    ]


def test_descoberta_historica_nao_acrescenta_ano() -> None:
    policy = resolve_recency_policy("Venezuela em 2024", reference=REF)
    assert build_discovery_queries("Venezuela em 2024", policy) == ["Venezuela em 2024"]


def test_bloco_historico_nao_forca_ano_corrente() -> None:
    policy = resolve_recency_policy("Venezuela em 2024", reference=REF)
    block = build_recency_block(policy, task="search")
    assert "RECORTE HISTÓRICO EXPLÍCITO" in block
    assert "PRIORIDADE DE FONTES" not in block


def test_bloco_plan_nao_trata_data_de_referencia_como_futuro() -> None:
    policy = resolve_recency_policy("situação atual da Venezuela", reference=REF)
    block = build_recency_block(policy, task="plan")
    assert "NÃO são 'futuro'" in block
    assert "Não copie para esses campos avisos metodológicos" in block


def test_parse_datas_iso_br_textual_e_epoch() -> None:
    assert parse_any_date("2026-10-25") == date(2026, 10, 25)
    assert parse_any_date("25/10/2026") == date(2026, 10, 25)
    assert parse_any_date("25 de outubro de 2026") == date(2026, 10, 25)
    assert parse_any_date("October 25, 2026") == date(2026, 10, 25)
    assert parse_any_date("Publicado em 25/10/2026 às 10h") == date(2026, 10, 25)


def test_fonte_data_prioriza_serp_depois_url_depois_corpo() -> None:
    item = {
        "url": "https://example.org/noticia/2024/05/01/materia",
        "timestamp": "2026-10-25T10:00:00Z",
    }
    when, origin = source_date_from_item(item)
    assert when == date(2026, 10, 25)
    assert origin == "serp:timestamp"

    when_url, origin_url = source_date_from_item(
        {"url": "https://example.org/noticia/2024/05/01/materia"}
    )
    assert when_url == date(2024, 5, 1)
    assert origin_url == "url"

    when_body, origin_body = source_date_from_item(
        {"url": "https://example.org/sem-data"},
        body="Publicado em 25 de outubro de 2026.",
    )
    assert when_body == date(2026, 10, 25)
    assert origin_body == "body"


def test_ranking_coloca_fonte_recente_na_frente_sem_descartar_antigas() -> None:
    policy = resolve_recency_policy("situação atual", reference=REF)
    items = [
        {"url": "https://example.org/antiga", "timestamp": "2024-01-10"},
        {"url": "https://example.org/sem-data"},
        {"url": "https://example.org/recente", "timestamp": "2026-10-25"},
    ]
    ranked = rank_serp_items_by_freshness(items, policy)
    assert [i["url"] for i in ranked] == [
        "https://example.org/recente",
        "https://example.org/antiga",
        "https://example.org/sem-data",
    ]


def test_ranking_historico_preserva_ordem_original() -> None:
    policy = resolve_recency_policy("Venezuela em 2024", reference=REF)
    items = [
        {"url": "https://example.org/a", "timestamp": "2026-10-25"},
        {"url": "https://example.org/b", "timestamp": "2024-01-10"},
    ]
    assert rank_serp_items_by_freshness(items, policy) == items


def test_data_de_referencia_configuravel_por_ambiente(monkeypatch) -> None:
    monkeypatch.setenv("RESEARCH_REFERENCE_DATE", "2024-03-01")
    assert current_reference_date() == date(2024, 3, 1)
    assert has_explicit_past_scope("eventos de 2024", reference=date(2024, 3, 1)) is False
    assert has_explicit_past_scope("eventos de 2023", reference=date(2024, 3, 1)) is True


def test_data_de_referencia_e_now_dinamico_sem_override(monkeypatch) -> None:
    monkeypatch.delenv("RESEARCH_REFERENCE_DATE", raising=False)
    before = datetime.now(timezone.utc)
    ref = reference_now()
    after = datetime.now(timezone.utc)
    instant = ref.astimezone(timezone.utc)
    assert before.timestamp() - 5 <= instant.timestamp() <= after.timestamp() + 5
    assert current_reference_date() == ref.date()


def test_writer_usa_relogio_atual_e_nao_a_data_congelada_do_plano(monkeypatch) -> None:
    from app.core.writer import _writer_recency_block

    monkeypatch.setenv("RESEARCH_REFERENCE_DATE", "2025-02-03")
    bloco = _writer_recency_block({
        "data_referencia": "2020-01-01",
        "politica_recencia": "recente",
        "pedido_original": "estado atual do setor",
    })
    assert "03/02/2025" in bloco
    assert "01/01/2020" not in bloco


def test_politica_24h_marca_janela_curta() -> None:
    policy = resolve_recency_policy("notícias", requested_mode="24h", reference=REF)
    assert isinstance(policy, RecencyPolicy)
    assert policy.mode == "24h"
    assert policy.window_days == 1
    assert policy.window_label == "últimas 24 horas"
