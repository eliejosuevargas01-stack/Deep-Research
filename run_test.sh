#!/usr/bin/env bash
# Carrega o ambiente de teste preservando valores com espaco (ex.: "redator final")
# e sobe o uvicorn. Nao use em producao.
set -a
# shellcheck disable=SC1091
. ./.env.test
set +a
exec uvicorn app.main:app --host 0.0.0.0 --port 8111 --log-level info
