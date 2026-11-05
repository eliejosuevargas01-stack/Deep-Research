#!/usr/bin/env python3
"""Stub do CLI `hermes` para o teste e2e do HermesRunner (não é usado em produção)."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PERSONAS = ("historiador", "cetico", "visionario", "futurista")


def extrair_payload(arquivo: Path) -> dict:
    bloco = re.search(r"```json\n(.*?)\n```", arquivo.read_text(encoding="utf-8"), re.S)
    if not bloco:
        raise SystemExit(f"prompt sem payload: {arquivo}")
    return json.loads(bloco.group(1))


def ponto(indice: int) -> dict:
    return {
        "ponto_id": indice,
        "enunciado": f"Ponto {indice} do tema",
        "subperguntas": [f"pergunta {i} do ponto {indice}" for i in range(1, 4)],
        "hipoteses": [f"hipotese {i} do ponto {indice}" for i in range(1, 4)],
        "lacunas_iniciais": [f"lacuna {i} do ponto {indice}" for i in range(1, 4)],
        "perguntas_auditoria": {str(i): f"criterio {i} do ponto {indice}" for i in range(1, 13)},
    }


def resposta(tarefa: dict, payload: dict) -> dict:
    papel = tarefa["papel"]
    if papel == "planner":
        profundidade = int(payload.get("profundidade", 1))
        return {"pontos": [ponto(i) for i in range(1, profundidade + 1)]}
    if papel in PERSONAS:
        url = f"https://exemplo.test/{payload['ponto_id']}/r{payload['rodada']}/{papel}"
        return {
            "informacao_coletada": f"{papel} rodada {payload['rodada']}: fato citado ({url})",
            "urls_usadas": [url],
            "urls_lidas": [url],
        }
    if papel == "auditor":
        return {"perguntas_respondidas": {str(i): True for i in range(1, 13)}}
    if papel == "redator":
        urls = list(payload.get("urls_usadas_acumuladas") or [])[:1]
        return {
            "relatorio_ponto": f"relatorio do ponto {payload['ponto_id']} com {len(urls)} fontes",
            "lacunas_identificadas": "nenhuma",
            "urls_citadas": urls,
        }
    raise SystemExit(f"papel inesperado: {papel}")


def main() -> int:
    argv = sys.argv[1:]
    usage = Path(argv[argv.index("--usage-file") + 1]) if "--usage-file" in argv else None
    cwd = Path.cwd()
    tarefas = json.loads((cwd / "tarefas.json").read_text(encoding="utf-8"))

    with (cwd / "chamadas.jsonl").open("a", encoding="utf-8") as registro:
        for tarefa in tarefas:
            registro.write(
                json.dumps({"id": tarefa["id"], "papel": tarefa["papel"], "cwd": str(cwd)}) + "\n"
            )

    if os.getenv("FAKE_HERMES_FALHAR"):
        print("stub: falha simulada", file=sys.stderr)
        return 3
    if os.getenv("FAKE_HERMES_SEM_SAIDA"):
        return 0

    for tarefa in tarefas:
        payload = extrair_payload(cwd / tarefa["arquivo"])
        (cwd / "saidas" / f"{tarefa['id']}.json").write_text(
            json.dumps(resposta(tarefa, payload), ensure_ascii=False), encoding="utf-8"
        )
    if usage:
        usage.write_text(
            json.dumps(
                {
                    "prompt_tokens": 1000,
                    "completion_tokens": 200,
                    "reasoning_tokens": 50,
                    "total_tokens": 1250,
                }
            ),
            encoding="utf-8",
        )
    print("CONCLUIDO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
