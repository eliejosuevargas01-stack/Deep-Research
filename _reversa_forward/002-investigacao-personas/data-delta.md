# Data Delta: Investigação Paralela por Personas (Workers)

> Feature: `002-investigacao-personas`  
> Data: `2026-10-14`
> Referência de Domínio: `app/models/domain_models.py` e `alembic/versions/0006_briefing_storage.py`

---

## 1. Visão Geral das Alterações de Banco

> Este é delta documental do modelo pretendido; não afirma que migração ou dados legados foram executados nesta rodada.

Esta feature introduz a persistência dos resultados analíticos produzidos pelas 4 personas nos passos de investigação e harmoniza o ciclo de vida dos status de pesquisa e passos com os requisitos acordados após as deliberações de 2026-10-14.

1. **Nova Tabela**: `research_step_results` (append-only de resultados analíticos das personas).
2. **Ciclo de Vida de Pontos e Extinção do `/approve`**: O endpoint `POST /briefings/{research_id}/approve` foi extinto. Os registros de pontos de pesquisa passam a existir na tabela `research_points` exclusivamente no momento da aprovação implícita (via `POST /briefings/{research_id}/investigate` sobre o primeiro briefing válido em rascunho) ou no momento da aprovação automática em background pós-revisão (via `PATCH /briefings/{research_id}`). Em ambos os caminhos, os pontos são inseridos diretamente com status inicial `SCRAPER_IN_PROGRESS` e `attempt_count = 0`.
3. **Ampliação de Títulos sem Teto de 500 (Q11)**: `research_points.title` e `research_step_results.step_title` são tipados como `sa.Text`, permitindo persistir integralmente enunciados gerados pelo Scout sem corte ou restrição de 500 caracteres.
4. **Novo Enum em `Research.status`**: Substitui o enum legado pelo conjunto canônico simplificado (`PENDING`, `BRIEFING`, `PENDING_APPROVAL`, `SCRAPER`, `AUDIT`, `WRITE`, `DONE`, `FAILED`).
5. **Novos Status em `ResearchPoint.status`**: `SCRAPER_PENDING` (reservado para backfill legado), `SCRAPER_IN_PROGRESS`, `SCRAPER_FAILED`, `AUDIT_PENDING`, `AUDIT_IN_PROGRESS`, `AUDIT_FAILED`, `WRITE_PENDING`, `WRITE_IN_PROGRESS`, `WRITE_FAILED`. O status legado `SEARCH_SUCCESS` é expurgado do enum e migrado explicitamente para `AUDIT_PENDING`.
6. **Sem criação de `sources_read`**: A coluna `sources_read` em `research_points` foi explicitamente descartada pelo operador, centralizando as URLs lidas em `research_step_results.read_urls`.
7. **Backfill de Dados**: Migração retroativa que cria registros em `research` para briefings legados da Feature 001 e popula `research_points` para briefings legados aprovados.

---

## 2. Nova Entidade: `research_step_results`

Tabela append-only que registra o resultado de cada worker/persona para cada passo da pesquisa. Não possui restrição de unicidade por (step, worker) para suportar futuras repesquisas ou auditorias.

Criada via Alembic (`sa.Uuid`, `sa.JSON`, `sa.DateTime(timezone=True)`, `sa.Text`), tipos portáteis como na `0006` (testes rodam em sqlite, produção em Postgres). Sem `JSONB` nem `gen_random_uuid()`; UUID gerado no ORM (`default=uuid.uuid4`).

```python
op.create_table(
    "research_step_results",
    sa.Column("id", sa.Uuid, primary_key=True),
    sa.Column("research_id", sa.Uuid, sa.ForeignKey("research.id", ondelete="CASCADE"), nullable=False),
    sa.Column("step_id", sa.Uuid, sa.ForeignKey("research_points.id", ondelete="CASCADE"), nullable=False),
    sa.Column("step_title", sa.Text, nullable=False),  # Q11: sem teto de 500 caracteres
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

Em sucesso, `result` guarda a análise final estruturada, sem limite de 500 caracteres para essa análise. Em falha definitiva (`FAILED`), guarda somente erro sanitizado (máx 500 caracteres, coluna `NOT NULL`); em exaustão de correções de JSON (Q7), `result` é exatamente "Invalid JSON response after 3 corrections" e `used_urls` é `[]`; `read_urls` guarda as URLs retornadas pela Jina (não comprova leitura íntegra/verbatim).

### Atributos

| Coluna | Tipo | Nulo | Default | Descrição |
|---|---|---|---|---|
| `id` | UUID | Não | `uuid4` (ORM) | Chave primária |
| `research_id` | UUID | Não | - | Chave estrangeira para `research.id` |
| `step_id` | UUID | Não | - | Chave estrangeira para `research_points.id` |
| `step_title` | Text (Q11) | Não | - | Cópia do título do ponto investigado (Q11 — sem teto de 500 caracteres). A migração 007 amplia `research_points.title` e `research_step_results.step_title` de `String(500)` para `Text` |
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
  - Ciclo de vida na Feature 002:
    - Criado com o tema em `BRIEFING` durante a geração inicial.
    - Transita para `PENDING_APPROVAL` com o briefing em `draft` aguardando ação do operador.
    - Transita para `SCRAPER` no momento da aprovação implícita (via `POST /briefings/{research_id}/investigate` sobre o draft) ou aprovação automática pós-revisão (via `PATCH /briefings/{research_id}`).
    - Transita para `AUDIT` quando todos os workers de todos os pontos encerrarem e ao menos 1 ponto obtiver sucesso.
    - Transita para `FAILED` em caso de erro terminal do Scout no POST inicial ou no PATCH (500/502/503), ou se 100% dos pontos investigados falharem definitivamente.
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

`SCRAPER_IN_PROGRESS` designa estado de `research_points.status`, nunca estado de `research.status`; a pesquisa permanece `SCRAPER` durante a investigação ativa.

- **Coluna `title`**: Alterada de `String(500)` para `sa.Text` (Q11: sem teto de 500 caracteres).
- **Coluna `status`**: String(32).
  - Valores válidos para a Feature 002: `SCRAPER_PENDING` (reservado para pontos migrados no backfill legado), `SCRAPER_IN_PROGRESS` (status inicial dos pontos criados na aprovação implícita ou automática), `SCRAPER_FAILED`, `AUDIT_PENDING`.
  - Valores futuros: `AUDIT_IN_PROGRESS`, `AUDIT_FAILED`, `WRITE_PENDING`, `WRITE_IN_PROGRESS`, `WRITE_FAILED`.
  - Migração explícita do status legado: `SEARCH_SUCCESS` é expurgado e registros existentes são convertidos para `AUDIT_PENDING`:
    ```sql
    UPDATE research_points SET status = 'AUDIT_PENDING' WHERE status = 'SEARCH_SUCCESS';
    ```
- **Coluna `attempt_count`**: Integer.
  - Inicia em 0 quando os pontos são persistidos na aprovação (implícita ou automática). Incrementa atomicamente em +1 por falha definitiva de cada worker associado ao ponto; retomada no startup reexecuta apenas personas sem linha correspondente em `research_step_results`, sem duplicar contagens.

---

## 4. Backfill Retroativo de Briefings (Migração Alembic 0007)

Para compatibilizar briefings criados pela Feature 001 antes do alinhamento de `research_id`:

```python
# Em alembic/versions/0007_investigation_step_results_and_status.py:
def upgrade():
    # 1. Criação da tabela research_step_results
    ...
    # 2. Ampliação de research_points.title para sa.Text (Q11)
    ...
    # 3. Backfill de briefings para research
    # Para cada briefing na tabela 'briefings', se não existir em 'research',
    # insere em 'research' com id=briefing.id, theme=briefing.theme, briefing_draft={}, status mapeado:
    # 'generating' -> 'BRIEFING', 'draft' -> 'PENDING_APPROVAL', 'approved' -> 'SCRAPER', 'failed' -> 'FAILED'
    ...
    # 4. Backfill de pontos para research_points
    # Para briefings com status 'approved', insere cada item de briefings.points_json em 'research_points' (position = índice + 1)
    # com status='SCRAPER_PENDING', attempt_count=0, title como Text
    # 5. Migração explícita do status legado SEARCH_SUCCESS para AUDIT_PENDING em research_points
    ...
```
