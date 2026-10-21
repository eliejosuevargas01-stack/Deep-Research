"""Teste de reprodução e regressão para BUG-20261019-1 (false positive de citação em negrito)."""
import pytest
from app.services.pipeline.writer import _is_factual_list_or_table


def test_is_factual_list_or_table_negrito_false_positive():
    """Valida que **Proposta didática:** não é classificado como lista factual."""
    line_negrito = "**Proposta didática:** desenhe dois cartões, 0 e 1; use moeda parada."
    assert not _is_factual_list_or_table(line_negrito), "Negrito markdown não deve ser classificado como lista/tabela"


def test_is_factual_list_or_table_lista_real():
    """Valida que listas factuais reais continuam detectadas."""
    line_lista_hifen = "- O resultado medido foi de 42% nos testes clínicos"
    line_lista_asterisco = "* O resultado medido foi de 42% nos testes clínicos"
    line_lista_numerada = "1. O resultado medido foi de 42% nos testes clínicos"

    assert _is_factual_list_or_table(line_lista_hifen)
    assert _is_factual_list_or_table(line_lista_asterisco)
    assert _is_factual_list_or_table(line_lista_numerada)


def test_is_factual_list_or_table_tabela():
    """Valida que tabelas markdown continuam detectadas."""
    line_tabela = "| Ponto | Status | Métrica |"
    assert _is_factual_list_or_table(line_tabela)


def test_is_factual_list_or_table_negrito_duplo_underline():
    """Valida que __Proposta didática:__ em underline também é ignorado."""
    line_underline = "__Proposta didática:__ desenhe dois cartões"
    assert not _is_factual_list_or_table(line_underline)
