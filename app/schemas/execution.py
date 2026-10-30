"""Tipo compartilhado de modo de execução dos pontos de pesquisa.

PRD v2, invariante I-3: o endpoint HTTP de entrada escolhe explicitamente entre
processar os pontos de pesquisa em paralelo ou em sequência. Valor inválido é
rejeitado (422) — nunca há fallback silencioso para um modo diferente do pedido.
"""

from typing import Literal, get_args

#: Modos aceitos. `parallel` é o default histórico do pipeline; `sequential`
#: processa um ponto por vez, em ordem crescente de `ponto_n`.
ExecutionMode = Literal["parallel", "sequential"]

EXECUTION_MODES = get_args(ExecutionMode)


def validate_execution_mode(value: str) -> str:
    """Valida o modo de execução, levantando ValueError fora do enum.

    Usado por camadas internas (runner/controller) que não passam pelo Pydantic
    do endpoint, garantindo o mesmo contrato de rejeição explícita.
    """
    if value not in EXECUTION_MODES:
        raise ValueError(
            f"EXECUTION_MODE_INVALID: '{value}' não é um modo válido. "
            f"Valores aceitos: {', '.join(EXECUTION_MODES)}."
        )
    return value
