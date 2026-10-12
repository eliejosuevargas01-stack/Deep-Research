# Relatório de Inspeção Profunda — T020-T022: Camada de Persistência Durável Briefing

- **Data da Inspeção:** 2026-10-11
- **Auditor:** Leaf Auditor Independente (`reversa-depth-inspection`)
- **Contexto:** `_reversa_forward/001-modulo-briefing` (estágio `coding`)
- **Alvo:** Sprint 6 (Sprint A de T011) — Persistência durável (`BriefingRecord`, `BriefingVersion`, migração Alembic `0006_briefing_storage.py`, conversores domain↔storage puros e storage assíncrono com Tx1/CAS Tx2).
- **Veredicto Final:** **PASS**

---

## 1. Escopo e Limites da Auditoria

### 1.1 Dentro do Escopo (Inspecionado)
- Modelos Declarative Base ORM: `BriefingRecord` e `BriefingVersion` em `app/models/domain_models.py`.
- Exportações de símbolos em `app/models/__init__.py`.
- Migração aditiva e reversível Alembic em `alembic/versions/0006_briefing_storage.py`.
- Conversores puros domain↔snapshot e rotinas assíncronas Tx1 / CAS Tx2 em `app/briefing/storage.py`.
- Suítes de testes automatizadas correspondentes:
  - `tests/test_briefing_storage_converters.py` (7 testes)
  - `tests/test_briefing_migration.py` (3 testes)
  - `tests/test_briefing_storage.py` (4 testes)
- Especificação de referência: decisões D1, D2 e D3 em `_reversa_forward/001-modulo-briefing/audit/t011-integration-decomposition.md`.

### 1.2 Fora do Escopo Declarado
- `app/briefing/service.py` e rotinas de orquestração HTTP.
- `app/briefing/llm_binding.py`, `app/services/llm.py` e bindings LiteLLM.
- Routers FastAPI (`app/routers/` e rotas HTTP de briefing).
- Execução de pipeline de pesquisa profunda, Reader e frontend (`frontend/src/`).
- Conexão e migração com banco de dados de desenvolvimento ou produção real (`.env`).
- Testes de orquestração/binding sob edição concorrente por outros workers.

---

## 2. Tabela de Hashes SHA-256 (Readset Estático Congelado)

Todos os hashes SHA-256 calculados e validados com 64 dígitos hexadecimais:

| Arquivo | Hash SHA-256 (64 hex) | Status de Acesso |
|---|---|---|
| `app/models/domain_models.py` | `4ac806852b283f0d2c6bed1622124989ce51aa0025a7db6c0bea260f97f20fa1` | Somente-leitura |
| `app/models/__init__.py` | `6cf0a07d11bf0f320d2e9c914ca6c30aa0eb4fd5af18dced373be1fb569b9e1c` | Somente-leitura |
| `alembic/versions/0006_briefing_storage.py` | `8356e2859adf03d5833e80a2110d5c24e79ea31ba7df65ba6fae98d51ee90f5d` | Somente-leitura |
| `app/briefing/storage.py` | `48f9411ababa036e00f013e8db03dc86d5ca765bde74c99cc37235802a3e1ab0` | Somente-leitura |
| `tests/test_briefing_storage_converters.py` | `1433dd34263b979e2532929b464e573e5945ed593634f55d1b5a5dc2b804a6db` | Somente-leitura |
| `tests/test_briefing_migration.py` | `1b42690c0f6f969c38965dc5ef14bba3f088968585d67bf5bef6a907ce1c6fc5` | Somente-leitura |
| `tests/test_briefing_storage.py` | `a4082c88ba74652168a16210ccc9d4da3ff3bddee97760e10442cf3e5943c174` | Somente-leitura |
| `_reversa_forward/001-modulo-briefing/audit/t011-integration-decomposition.md` | `fd679e6a53f017fbc160a0f1352b471f40c3efa971b74a4122b1f2d7423e04bf` | Somente-leitura |
| `AGENTS.md` | `9de50e39699ecac57f33b18ae5b0149186ec04bb6571cdb87218fee2607e1844` | Somente-leitura |
| `.reversa/state.json` | `27fc325d313341e303a16a4d4c2dbb03838b91f034f250fe3661a2083353b3df` | Somente-leitura |
| `.reversa/active-requirements.json` | `802efe8929aa5575e24b23947afdf2a4dff013c9d284b3f2ed7420fc246f2d45` | Somente-leitura |
| `.reversa/reversa-config.json` | `33c9ab2158530bcba7c242f15d7e2f173f346b7f9a999115231e195bd8f4c8fe` | Somente-leitura |
| `app/briefing/domain.py` | `f058679d7a1a923c337a4dc067c01cbc3d0f50d0ca126220de286ec89d557b4a` | Somente-leitura |
| `alembic/env.py` | `e3dd27422ab3eeb232610a8038cc42138bcf2f792c420521e2f09b5dc7a1f315` | Somente-leitura |

---

## 3. Avaliação das Lentes de Inspeção

### 3.1 Lente 1: Conformidade de Schema e D2 (Modelos ORM e Migração)
- **Tabela `briefings`:**
  - Chave primária: `id UUID PRIMARY KEY` (`uuid.uuid4`).
  - Colunas: `theme VARCHAR(300) NOT NULL`, `status VARCHAR(20) NOT NULL`, `version INTEGER NOT NULL`, `points_json JSON NOT NULL DEFAULT '[]'`, `error TEXT NULL`, `approved_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
  - Ausência de colunas legadas: nenhuma referência a `research_id`, `briefing_draft` ou colunas de pipeline.
  - Isolamento estrito de `Research`: sem chave estrangeira para `research` ou `research_points`.
- **Tabela `briefing_versions`:**
  - Chave primária: `id UUID PRIMARY KEY`.
  - Chave estrangeira: `briefing_id UUID NOT NULL REFERENCES briefings(id) ON DELETE CASCADE`.
  - Colunas: `version INTEGER NOT NULL`, `status VARCHAR(20) NOT NULL`, `points_json JSON NOT NULL`, `error TEXT NULL`, `approved_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
  - Restrição única: `UniqueConstraint("briefing_id", "version", name="uq_briefing_version")`.
  - Índice composto: `Index("ix_briefing_versions_briefing_id_version", "briefing_id", "version")`; ASC implícito padrão SQL. A consulta usa `.order_by(BriefingVersion.version.asc())` explicitamente (`storage.py:79-86`).
  - Observação de paridade, não bloqueante: ORM usa defaults Python (`default=list`, `default=now`) enquanto migração define defaults de servidor. ORM também declara índice simples adicional em `briefing_id` (`domain_models.py:152`), ausente na migração; índice composto requerido existe em ambos.
- **Conclusão:** Conformidade estrita com D2.

### 3.2 Lente 2: Conversores Puros (T020)
- `points_to_json(points)` serializa tupla imutável de `BriefingPoint` exclusivamente para `[{"title": p.title, "description": p.description}]`.
- `json_to_points(data)` desserializa para tupla imutável `tuple[BriefingPoint, ...]`.
- Isolamento de mutabilidade verificado: mutações no payload serializado intermediário não afetam as instâncias de domínio de origem nem de destino.
- Timestamps preservados fielmente: `approved_at` preservado como `datetime` timezone-aware ou `None`.
- `record_to_briefing(record)` converte string `status` de volta para `BriefingStatus` enum e preserva `version`, `error` e `UUID`.
- `briefing_to_version_dict(briefing)` gera dicionário compatível com kwargs de `BriefingVersion`.

### 3.3 Lente 3: Transações Atômicas e Concorrência (T022, D1, D3)
- **Tx1 (`create_generating_briefing`):**
  - Executa `db.add(...)` seguido imediatamente de `await db.commit()`.
  - Transação é finalizada de pronto, liberando a conexão de volta ao pool e garantindo que I/O externo (SERP/LLM) não rode retendo lock ou transação de banco aberta.
- **Tx2 CAS (`save_briefing_transition`):**
  - Executa `UPDATE briefings ... WHERE id == new_briefing.id AND version == previous_briefing.version`.
  - Valida `rowcount == 1`.
  - Em caso de versão divergente (`rowcount != 1`), invoca `await db.rollback()` e dispara `BriefingVersionConflictError`.
  - Em caso de sucesso, na mesma transação adiciona `BriefingVersion` com o snapshot do estado novo e executa `await db.commit()`.
  - Atomicidade comprovada via probe: falha durante a persistência da versão histórica dispara rollback completo do update do registro pai.
- **Idempotência e Segurança de Concorrência:** Verificada rejeição de escritas obsoletas (stale CAS).

### 3.4 Lente 4: Migração Alembic (T021)
- Identificador de revisão: `0006`.
- Revisão ancestral: `down_revision = "0005"`.
- Cadeia linear contínua sem quebras ou bifurcações (`0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006`).
- Operações de `upgrade()` criam tabelas `briefings` e `briefing_versions` com colunas, tipos e constraints requeridos por D2. Diferenças de defaults e índice simples adicional do ORM registradas acima.
- Operações de `downgrade()` removem índices e tabelas na ordem reversa sem deixar resíduos.
- Reversibilidade total validada em SQLite temporário sem dependência de banco de dados real.

---

## 4. Evidências de Execução de Testes e Linters

### 4.1 Execução de Testes Unitários Isolados
Comando executado:
```bash
python3 -B -m unittest tests.test_briefing_storage_converters tests.test_briefing_migration tests.test_briefing_storage -v
```

Saída:
```text
test_round_trip_all_states (tests.test_briefing_storage_converters.TestBriefingConverters.test_round_trip_all_states) ... ok
test_timestamps (tests.test_briefing_storage_converters.TestBriefingConverters.test_timestamps) ... ok
test_version_dict (tests.test_briefing_storage_converters.TestBriefingConverters.test_version_dict) ... ok
test_tables_and_columns (tests.test_briefing_storage_converters.TestOrmMapping.test_tables_and_columns) ... ok
test_version_constraints_and_isolation (tests.test_briefing_storage_converters.TestOrmMapping.test_version_constraints_and_isolation) ... ok
test_round_trip (tests.test_briefing_storage_converters.TestPointsConverters.test_round_trip) ... ok
test_tuple_isolation (tests.test_briefing_storage_converters.TestPointsConverters.test_tuple_isolation) ... ok
test_tables_absent_after_downgrade (tests.test_briefing_migration.BriefingMigrationTests.test_tables_absent_after_downgrade) ... ok
test_tables_present_after_upgrade (tests.test_briefing_migration.BriefingMigrationTests.test_tables_present_after_upgrade) ... ok
test_upgrade_and_downgrade_reversible (tests.test_briefing_migration.BriefingMigrationTests.test_upgrade_and_downgrade_reversible) ... ok
test_full_cycle_generating_draft_edit_approved (tests.test_briefing_storage.TestStorageCycle.test_full_cycle_generating_draft_edit_approved) ... ok
test_get_missing_returns_none_and_history_empty (tests.test_briefing_storage.TestStorageCycle.test_get_missing_returns_none_and_history_empty) ... ok
test_points_json_only_clean_points_and_uuid_preserved (tests.test_briefing_storage.TestStorageCycle.test_points_json_only_clean_points_and_uuid_preserved) ... ok
test_stale_cas_raises_and_preserves_state (tests.test_briefing_storage.TestStorageCycle.test_stale_cas_raises_and_preserves_state) ... ok

----------------------------------------------------------------------
Ran 14 tests in 0.875s

OK
```

Total de testes executados: 14/14 passaram com sucesso.

### 4.2 Verificação de Whitespace e Diff (`git diff --check`)
Comando executado:
```bash
git diff --check
```
Resultado: retorno vazio com código de saída 0 (sem conflitos, espaços em branco espúrios ou corrupção de quebras de linha).

---

## 5. Achados e Observações

- **Bugs Confirmados:** 0
- **Divergências de Requisitos:** 0
- **Observações Técnicas:**
  - `BriefingRecord` e `BriefingVersion` utilizam `JSON` genérico do SQLAlchemy, o que garante portabilidade perfeita entre SQLite em memória para suítes de teste e PostgreSQL para ambientes produtivos.
  - A migração `0006_briefing_storage.py` preserva integridade referencial com `ON DELETE CASCADE`.
  - O isolamento completo contra tabelas legadas (`research`, `research_points`) foi comprovado estaticamente e em runtime.

---

## 6. Integridade, limites e observações não promovidas

- Preflight: branch `main`; worktree já continha modificações e arquivos não rastreados. Status inicial e final coincidem nas entradas exibidas. Nenhuma limpeza ou edição desses arquivos realizada.
- Configuração efetiva lida em `.reversa/active-requirements.json` e `.reversa/reversa-config.json`; nomes equivalentes na raiz não existem. Feature ativa `001-modulo-briefing`, estágio `coding`. `.reversa/state.json` contém fase global anterior `forward-complete`; não altera recorte delegado.
- Oito arquivos do readset principal tiveram hashes calculados antes e após testes/probe: valores idênticos. Todos os 14 hashes da tabela passaram validação `[0-9a-f]{64}`. Arquivos auxiliares `domain.py` (linhas 1–145) e `alembic/env.py` lidos somente para imutabilidade e segurança de execução; não constituem auditoria de outros marcos.
- Única escrita: este relatório. Sem mudanças em código, testes, migrações, actions, progress ou configuração. Sem `todo_list`, descoberta glob ou conexão a DB real. Testes usam SQLite temporário no scratch configurado; probe usa SQLite em memória.
- Expressamente fora do escopo: `service.py`, `llm_binding.py`, router, endpoints HTTP, binding real e QA de integração/orquestração. Não há parecer sobre essas camadas.
- Probe adicional sem arquivo: asserts verificaram lista exata de colunas; DDL PostgreSQL compilado sem conexão; Tx1 e Tx2 bem-sucedidas terminam sem `db.in_transaction()`; stale CAS executa rollback e termina sem transação ativa. Saída: `PROBE PASS: exact columns, Tx1/Tx2 transaction closed, failed history INSERT rolls back UPDATE, stale CAS rollback`.
- Precisão sobre falha no histórico: exceção `RuntimeError` injetada em `before_insert` durante `commit()`; SQLAlchemy reverteu UPDATE e INSERT atomicamente. Probe chamou `await db.rollback()` explicitamente para recuperar sessão antes de conferir pai versão 1/status generating e zero históricos. Storage não oferece rollback explícito genérico para falhas de execute/commit; CAS divergente tem rollback explícito. Recuperação de sessão após erro de infraestrutura depende do chamador; observação, não desvio comprovado do contrato inspecionado.
- Timestamp do domínio é `approved_at`; preservado nos conversores. `created_at` e `updated_at` são metadados de persistência, não campos de `Briefing`. SQLite não comprova preservação de timezone no round-trip real de PostgreSQL; tipos TIMESTAMPTZ verificados estaticamente/por compilação.
- Aviso não bloqueante de Alembic: `DeprecationWarning: No path_separator found in configuration`. Não houve erro de migração ou colisão de revisão.
- Defaults Python versus servidor e índice simples adicional são observações de paridade (`promoted_to: null`); não impedem schema migrado requerido. Índice ASC é implícito no DDL, não expressão `.asc()` no modelo.
- Cobertura: suítes não simulam duas conexões concorrentes, interrupção/crash, nem PostgreSQL real. CAS obsoleto testado; atomicidade de falha no INSERT ampliada pelo probe. Não se afirma cobertura desses cenários não executados.
- Lentes aplicadas: conformidade, fluxo de dados, contratos internos, estados de erro, cobertura e concorrência/consistência; configuração/migração ativada. Segurança HTTP e desempenho externo não aplicáveis ao recorte. Nenhum bug registrado, nenhum cluster confirmado; registro/views/skills não escritos por exclusividade do caminho autorizado.

## 7. Veredicto Final

**PASS** — A persistência durável entregue nos marcos T020, T021 e T022 cumpre integralmente os requisitos de schema D2, isolamento de conversores T020, migração Alembic reversível T021 e transações atômicas com controle de concorrência CAS T022/D1/D3.
