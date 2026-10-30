"""Regressão da execução fa4257da: corpus não pode oferecer trecho de fonte não lida."""

from app.core.auditor import _trechos_entregues
from app.core.searcher import _promovivel_para_trecho


def test_snippet_nao_vira_trecho():
    assert not _promovivel_para_trecho({"status": "snippet_only", "body": "descrição"})
    assert not _promovivel_para_trecho({"status": "read_ok", "body": "   "})
    assert _promovivel_para_trecho({"status": "read_ok", "body": "texto real"})


def test_auditoria_so_cobra_evidencia_entregue():
    trechos = {"chk_1": {"text": "a"}, "chk_2": {"text": "b"}, "chk_3": {"text": "c"}}
    selecao = {"historiador": {"selected_chunk_ids": ["chk_1", "chk_2"]}}
    assert set(_trechos_entregues(trechos, selecao)) == {"chk_1", "chk_2"}
    # Sem seleção registrada não há como filtrar: mantém o corpus.
    assert set(_trechos_entregues(trechos, {})) == {"chk_1", "chk_2", "chk_3"}
