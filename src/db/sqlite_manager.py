"""SQLite local com as mesmas tabelas/colunas do schema canônico (SDD §5).

PostgreSQL é o alvo de produção (src/db/schema.sql); aqui JSONB vira TEXT e
UUID vira hex. ponytail: um só dialeto, trocar quando o DSN de produção entrar —
o ponto de troca é `Repository`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runs (
    research_id TEXT PRIMARY KEY,
    tema TEXT NOT NULL,
    profundidade INTEGER NOT NULL CHECK (profundidade BETWEEN 1 AND 10),
    veracidade_alvo REAL NOT NULL CHECK (veracidade_alvo BETWEEN 0 AND 100),
    max_rodadas_auditoria INTEGER NOT NULL,
    atualidade TEXT NOT NULL,
    callback_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PROCESSING',
    plano_inicial TEXT,
    relatorio_final_consolidado TEXT,
    lacunas_finais_consolidadas TEXT,
    urls_usadas_globais TEXT NOT NULL DEFAULT '[]',
    urls_lidas_globais TEXT NOT NULL DEFAULT '[]',
    urls_nao_usadas_globais TEXT NOT NULL DEFAULT '[]',
    total_prompt_tokens INTEGER NOT NULL DEFAULT 0,
    total_completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_reasoning_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS research_points (
    point_uuid TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    research_id TEXT NOT NULL REFERENCES research_runs(research_id) ON DELETE CASCADE,
    ponto_id INTEGER NOT NULL,
    enunciado TEXT NOT NULL,
    subperguntas TEXT NOT NULL,
    hipoteses TEXT NOT NULL,
    lacunas_iniciais TEXT NOT NULL,
    perguntas_auditoria TEXT NOT NULL,
    ultimo_resultado_auditor TEXT,
    porcentagem_aprovacao REAL NOT NULL DEFAULT 0,
    rodada_atual INTEGER NOT NULL DEFAULT 1,
    aprovado INTEGER NOT NULL DEFAULT 0,
    relatorio_ponto TEXT,
    lacunas_ponto TEXT,
    UNIQUE (research_id, ponto_id)
);

CREATE TABLE IF NOT EXISTS agent_executions (
    execution_id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    research_id TEXT NOT NULL REFERENCES research_runs(research_id) ON DELETE CASCADE,
    ponto_id INTEGER,
    rodada INTEGER NOT NULL DEFAULT 1,
    agent_role TEXT NOT NULL,
    input_prompt_payload TEXT NOT NULL,
    raw_output_payload TEXT NOT NULL,
    informacao_coletada TEXT,
    reasoning_trace TEXT,
    tool_calls TEXT NOT NULL DEFAULT '[]',
    urls_usadas TEXT NOT NULL DEFAULT '[]',
    urls_lidas TEXT NOT NULL DEFAULT '[]',
    urls_lidas_nao_usadas TEXT NOT NULL DEFAULT '[]',
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    reasoning_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_executions_lookup
    ON agent_executions (research_id, ponto_id, rodada, agent_role);
"""


def conectar(caminho: str | Path) -> sqlite3.Connection:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho, check_same_thread=False, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    con.commit()
    return con
