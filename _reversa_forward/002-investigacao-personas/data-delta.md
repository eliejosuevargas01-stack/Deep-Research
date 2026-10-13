# Data Delta: Investigação Paralela por Personas (Workers)

> Feature: `002-investigacao-personas`  
> Data: `2026-10-13`
> Referência de Domínio: `app/models/domain_models.py` e `alembic/versions/0006_briefing_storage.py`

---

## 1. Visão Geral das Alterações de Banco

> Este é delta documental do modelo pretendido; não afirma que migração ou dados legados foram executados nesta rodada.

Esta feature introduz a persistência dos resultados analíticos produzidos pelas 4 personas nos passos de investigação e harmoniza o ciclo de vida dos status de pesquisa e passos com os requisitos acordados.

1. **Nova Tabela**: `research_step_results` (append-only de resultados das personas).
2. **Novo Enum em `Research.status`**: Substitui o enum legado pelo conjunto canônico simplificado (`PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`).
3. **Novos Status em `ResearchPoint.status`**: `SCRAPER_PENDING`, `SCRAPER_IN_PROGRESS`, `SCRAPER_FAILED`, `AUDIT_PENDING`, `AUDIT_IN_PROGRESS`, `AUDIT_FAILED`, `WRITE_PENDING`, `WRITE_IN_PROGRESS`, `WRITE_FAILED`. O status legado `SEARCH_SUCCESS` é expurgado do enum e migrado explicitamente para `AUDIT_PENDING`.
4. **Sem criação de `sources_read`**: A coluna `sources_read` em `research_points` foi explicitamente descartada pelo operador, centralizando as URLs lidas em `research_step_results.read_urls`.
5. **Backfill de Dados**: Migração retroativa que cria registros em `research` para briefings legados da Feature 001 e popula `research_points` para briefings aprovados.

---

## 2. Nova Entidade: `research_step_results`

Tabela append-only que registra o resultado de cada worker/persona para cada passo da pesquisa. Não possui restrição de unicidade por (step, worker) para suportar futuras repesquisas ou auditorias.

Criada via Alembic (`sa.Uuid`, `sa.JSON`, `sa.DateTime(timezone=True)`), tipos portáteis como na `0006` (testes rodam em sqlite, produção em Postgres). Sem `JSONB` nem `gen_random_uuid()`; UUID gerado no ORM (`default=uuid.uuid4`).

```python
op.create_table(
    "research_step_results",
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("research_id", sa.Uuid, sa.ForeignKey("research.id", ondelete="CASCADE"), nullable=False),
    sa.Column("step_id", sa.Uuid, sa.ForeignKey("research_points.id", ondelete="CASCADE"), nullable=False),
    sa.Column("step_title", sa.Text, nullable=False),  # Q11: sem teto de 500
    sa.Column("result", sa.Text, nullable=False),
    sa.Column("used_urls", sa.JSON, nullable=False),
    sa.Column("read_urls", sa.JSON, nullable=False),
    sa.Column("worker", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
op.create_index("ix_research_step_results_research_id", "research_step_results", ["research_id"])
op.create_index("ix_research_step_results_step_id", "research_step_results", ["step_id"])
```

Em sucesso, `result` guarda a análise final, sem limite de 500 caracteres para essa análise. Em falha definitiva (`FAILED`), guarda somente erro sanitizado (máx 500 caracteres, coluna `NOT NULL`); em exaustão de correções de JSON (Q7), `result` é exatamente "Invalid JSON response after 3 corrections" e `used_urls` é `[]`; `read_urls` guarda as URLs retornadas pela Jina (não comprova leitura íntegra/verbatim).

### Atributos

| Coluna | Tipo | Nulo | Default | Descrição |
|---|---|---|---|---|
| `id` | UUID | Não | `uuid4` (ORM) | Chave primária |
| `research_id` | UUID | Não | - | Chave estrangeira para `research.id` |
| `step_id` | UUID | Não | - | Chave estrangeira para `research_points.id` |
| `step_title` | Text (Q11) | Não | - | Cópia do título do ponto (Q11 — sem teto de 500; títulos gerados pelo Scout podem exceder 500). A migração 007 deve ampliar `research_points.title` e `research_step_results.step_title` de `String(500)` para `Text` |
| `result` | Text | Não | - | Análise final emitida pelo modelo em sucesso (sem teto) ou mensagem de erro sanitizada (máx 500 chars) em falha |
| `used_urls` | JSON | Não | `[]` (ORM) | Lista de URLs que o modelo citou no resultado |
| `read_urls` | JSON | Não | `[]` (ORM) | URLs retornadas pela Jina; não comprova leitura integral nem correspondência verbatim |
| `worker` | String(32) | Não | - | Identificador da persona (`historian`, `skeptic`, `pragmatist`, `futurist`) |
| `status` | String(32) | Não | `AUDIT_PENDING` (ORM) | Status do resultado: `AUDIT_PENDING`, `APPROVED`, `REJECTED`, `FAILED` |
| `created_at` | DateTime(tz) | Não | `now()` UTC (ORM) | Timestamp de criação |

---

## 3. Alterações em Entidades Existentes

### 3.1 Tabela `research`

- **Coluna `status`**: String(32).
  - Valores permitidos: `PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`.
  - Migração de dados legados no Postgres:
    ```sql
    UPDATE research SET status = 'BRIEFING' WHERE status IN ('scouting', 'revising');
    UPDATE research SET status = 'PENDING_APPROVAL' WHERE status = 'pending_approval';
    UPDATE research SET status = 'SCRAPER' WHERE status = 'approved';
    UPDATE research SET status = 'SCRAPER' WHERE status = 'in_progress';
    UPDATE research SET status = 'DONE' WHERE status IN ('completed', 'completed_but_callback_failed');
    UPDATE research SET status = 'FAILED' WHERE status IN ('blocked', 'failed', 'interrupted');
    ```

### 3.2 Tabela `research_points`

`SCRAPER_IN_PROGRESS` designa estado de `research_points.status`, nunca estado de `research.status`; pesquisa permanece `SCRAPER` durante a investigação.

- **Coluna `status`**: String(32).
  - Valores válidos para a Feature 002: `SCRAPER_PENDING`, `SCRAPER_IN_PROGRESS`, `SCRAPER_FAILED`, `AUDIT_PENDING`.
  - Valores futuros: `AUDIT_IN_PROGRESS`, `AUDIT_FAILED`, `WRITE_PENDING`, `WRITE_IN_PROGRESS`, `WRITE_FAILED`
  - Migração explícita do status legado: `SEARCH_SUCCESS` é expurgado e registros existentes são convertidos para `AUDIT_PENDING`:
    ```sql
    UPDATE research_points SET status = 'AUDIT_PENDING' WHERE status = 'SEARCH_SUCCESS';
    ```
- **Coluna `attempt_count`**: Integer.
  - Inicia em 0 quando os pontos são persistidos após aprovação. Incrementa atomicamente em +1 por falha definitiva de cada worker; retomada reexecuta apenas personas sem linha em `research_step_results`.

---

## 4. Backfill Retroativo de Briefings (Migração Alembic)

Para compatibilizar briefings criados pela Feature 001 antes do alinhamento de `research_id`:

```python
# Em alembic/versions/0007_investigation_step_results_and_status.py:
def upgrade():
    # 1. Criação da tabela research_step_results
    ...
    # 2. Backfill de briefings para research
    # Para cada briefing na tabela 'briefings', se não existir em 'research',
    # insere em 'research' com id=briefing.id, theme=briefing.theme, briefing_draft={}, status mapeado:
    # 'generating' -> 'BRIEFING', 'draft' -> 'PENDING_APPROVAL', 'approved' -> 'SCRAPER', 'failed' -> 'FAILED'
    ...
    # 3. Backfill de pontos para research_points
    # Para briefings com status 'approved', insere cada item de briefings.points_json em 'research_points' (position = índice + 1)
    # com status='SCRAPER_PENDING', attempt_count=0
    # 4. Migração explícita do status legado SEARCH_SUCCESS para AUDIT_PENDING em research_points
    ...
```
