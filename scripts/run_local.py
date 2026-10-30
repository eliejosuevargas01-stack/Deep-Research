#!/usr/bin/env python3
"""Sobe a API localmente carregando o `.env` também para `os.environ`.

Motivo: o `pydantic-settings` lê o `.env` para dentro do objeto `Settings`, mas
parte do código consulta `os.environ` diretamente (`credentials_repository`,
`llm_client`, `crypto_service`, `session`). Sem exportar o `.env`, esses pontos
não enxergam PERSONAS_CONFIG / OPENAI_API_KEY / CREDENTIALS_MASTER_KEY e a API
responde 400 "persona 'planejador' não encontrada".

Uso:
    ./.venv/bin/python scripts/run_local.py [--port 8010] [--reload]

Regras de precedência: variáveis já presentes no ambiente vencem o `.env`
(mesmo comportamento do pydantic-settings).
"""

from __future__ import annotations

import argparse
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_env(path: pathlib.Path = ROOT / ".env", respect_ambient: bool = False) -> list[str]:
    """Exporta o .env para os.environ.

    Por padrão o `.env` do projeto vence o ambiente do shell: shells que
    exportam OPENAI_API_KEY/DATABASE_URL (por exemplo via ~/.bashrc) apontariam
    a API para um provedor errado. Use `--respect-ambient` para inverter.
    """
    if not path.exists():
        print(f"[run_local] .env ausente em {path}; seguindo só com o ambiente")
        return []
    loaded: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if respect_ambient and key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa a API em modo local")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument(
        "--respect-ambient",
        action="store_true",
        help="mantém variáveis já exportadas no shell em vez de usar o .env",
    )
    args = parser.parse_args()

    loaded = load_env(respect_ambient=args.respect_ambient)
    print(f"[run_local] {len(loaded)} chaves do .env exportadas: {', '.join(sorted(loaded))}")
    print(
        f"[run_local] OPENAI_API_KEY: {'definida' if os.environ.get('OPENAI_API_KEY') else 'AUSENTE'}"
        f" | LLM_BASE_URL: {os.environ.get('LLM_BASE_URL')}"
        f" | DATABASE_URL: {str(os.environ.get('DATABASE_URL')).split('@')[-1]}"
    )
    (ROOT / "data").mkdir(exist_ok=True)
    os.chdir(ROOT)

    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
