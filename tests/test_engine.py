from __future__ import annotations

import pytest

from engine import EngineError, extrair_json


def test_extrai_json_do_texto_com_cerca():
    assert extrair_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extrai_json_do_primeiro_objeto_com_preambulo():
    assert extrair_json('Aqui está:\n{"a": {"b": 2}}\nFim.') == {"a": {"b": 2}}


def test_rejeita_texto_sem_objeto():
    with pytest.raises(EngineError):
        extrair_json("sem json nenhum")


def test_rejeita_json_que_nao_e_objeto():
    with pytest.raises(EngineError):
        extrair_json("[1, 2, 3]")
