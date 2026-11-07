# verification — db-inventory

PRAGMA table_info do SQLite tmp gerado por Repositorio sobre SqliteManager.conectar, src/db/sqlite_manager.py:83-95, apos criar mais executar 1 pesquisa de 1 ponto. CONFIRMADO.

TABLE agent_executions
  execution_id TEXT pk=1
  research_id TEXT nn=1
  ponto_id INTEGER
  rodada INTEGER nn=1 default 1
  agent_role TEXT nn=1
  model_used TEXT
  input_prompt_payload TEXT nn=1
  raw_output_payload TEXT nn=1
  informacao_coletada TEXT
  reasoning_trace TEXT
  tool_calls TEXT nn=1 default '[]'
  urls_usadas TEXT nn=1 default '[]'
  urls_lidas TEXT nn=1 default '[]'
  urls_lidas_nao_usadas TEXT nn=1 default '[]'
  prompt_tokens INTEGER nn=1 default 0
  completion_tokens INTEGER nn=1 default 0
  reasoning_tokens INTEGER nn=1 default 0
  total_tokens INTEGER nn=1 default 0
  latency_ms INTEGER
  created_at TEXT nn=1
  rows=7

TABLE research_points
  point_uuid TEXT pk=1
  research_id TEXT nn=1
  ponto_id INTEGER nn=1
  enunciado TEXT nn=1
  subperguntas TEXT nn=1
  hipoteses TEXT nn=1
  lacunas_iniciais TEXT nn=1
  perguntas_auditoria TEXT nn=1
  ultimo_resultado_auditor TEXT
  porcentagem_aprovacao REAL nn=1 default 0
  rodada_atual INTEGER nn=1 default 1
  aprovado INTEGER nn=1 default 0
  relatorio_ponto TEXT
  lacunas_ponto TEXT
  rows=1

TABLE research_runs
  research_id TEXT pk=1
  tema TEXT nn=1
  profundidade INTEGER nn=1
  veracidade_alvo REAL nn=1
  max_rodadas_auditoria INTEGER nn=1
  atualidade TEXT nn=1
  callback_url TEXT nn=1
  status TEXT nn=1 default PROCESSING
  plano_inicial TEXT
  relatorio_final_consolidado TEXT
  lacunas_finais_consolidadas TEXT
  urls_usadas_globais TEXT nn=1 default '[]'
  urls_lidas_globais TEXT nn=1 default '[]'
  urls_nao_usadas_globais TEXT nn=1 default '[]'
  total_prompt_tokens INTEGER nn=1 default 0
  total_completion_tokens INTEGER nn=1 default 0
  total_reasoning_tokens INTEGER nn=1 default 0
  total_tokens INTEGER nn=1 default 0
  created_at TEXT nn=1
  completed_at TEXT
  rows=1

## Diff conceitual vs src/db/schema.sql

Mesmas 3 tabelas e colunas com nomes identicos. CONFIRMADO.
PG usa VARCHAR, UUID gen_random_uuid, JSONB, TIMESTAMPTZ; SQLite usa TEXT, hex randomblob, TEXT JSON, TEXT strftime. CONFIRMADO.
UNIQUE research_id mais ponto_id, REFERENCES ON DELETE CASCADE e indice idx_executions_lookup existem nos dois. CONFIRMADO.
LACUNA: PostgreSQL nunca executado neste host, so DDL lido.
