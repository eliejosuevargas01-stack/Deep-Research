#!/usr/bin/env python3
"""Relatório/exportação das capturas de chamadas LLM.

Uso:
    python scripts/llm_capture_report.py                 # resumo do diretório padrão
    python scripts/llm_capture_report.py --dir /app/data/llm-capture --tail 50
    python scripts/llm_capture_report.py --dir ... --export tudo.jsonl
    python scripts/llm_capture_report.py --dir ... --last   # JSON completo da última chamada

Diretório padrão: $DR_LLM_CAPTURE_DIR ou ./data/llm-capture.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Relatório das capturas LLM em JSON.")
    parser.add_argument(
        "--dir",
        default=os.environ.get("DR_LLM_CAPTURE_DIR") or "./data/llm-capture",
        help="diretório de captura",
    )
    parser.add_argument("--tail", type=int, default=10, help="quantas chamadas listar no índice")
    parser.add_argument("--export", help="grava todas as capturas em um JSONL")
    parser.add_argument("--last", action="store_true", help="imprime a última captura completa")
    args = parser.parse_args()

    directory = os.path.abspath(args.dir)
    if not os.path.isdir(directory):
        print(f"diretório inexistente: {directory}", file=sys.stderr)
        return 2

    files = sorted(f for f in os.listdir(directory) if f.endswith(".json") and not f.startswith("."))
    if not files:
        print(f"nenhuma captura em {directory}")
        return 1

    if args.last:
        with open(os.path.join(directory, files[-1]), encoding="utf-8") as fh:
            print(json.dumps(json.load(fh), ensure_ascii=False, indent=2))
        return 0

    if args.export:
        with open(args.export, "w", encoding="utf-8") as out:
            for name in files:
                with open(os.path.join(directory, name), encoding="utf-8") as fh:
                    record = json.load(fh)
                record["_capture_file"] = name
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"exportado: {os.path.abspath(args.export)} ({len(files)} chamadas)")

    print(f"diretório: {directory}")
    print(f"chamadas:  {len(files)}")
    rows = []
    for name in files[-max(args.tail, 0):]:
        with open(os.path.join(directory, name), encoding="utf-8") as fh:
            data = json.load(fh)
        req = data.get("request") or {}
        resp = data.get("response") or {}
        usage = resp.get("usage") if isinstance(resp, dict) else None
        tokens = ""
        if isinstance(usage, dict):
            tokens = f"{usage.get('prompt_tokens', '?')}p/{usage.get('completion_tokens', '?')}c"
        rows.append(
            f"{name}  {data.get('status')}  {req.get('model')}  "
            f"{req.get('prompt_id') or '-'}  {tokens}"
        )
    print("\n".join(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
