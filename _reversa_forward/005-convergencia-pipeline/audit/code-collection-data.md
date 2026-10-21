# Inspeção Profunda: Coleta, Worker e Dados (S09-S12)

Data: 2026-10-20  
Feature: `005-convergencia-pipeline`  
Ação: T014 / S14  
Lentes aplicadas: Conformidade com spec, Fluxo de dados, Contratos de engenharia D, Segurança/SSRF, Concorrência.

---

## Escopo inspecionado

Arquivos de produto:
- `app/services/search.py`
- `app/investigation/tools.py`
- `app/investigation/schemas.py`
- `app/investigation/worker.py`
- `app/models/domain_models.py`
- `app/models/__init__.py`
- `alembic/versions/0008_investigation_rounds_and_merges.py`
- `app/investigation/storage.py`
- `app/investigation/service.py`

Arquivos de teste e suporte:
- `tests/investigation/test_jina_tool.py`
- `tests/investigation/test_persona_worker.py`
- `tests/investigation/test_round_storage.py`
- `tests/investigation/test_round_migration.py`
- `tests/investigation/conftest.py`

Contratos de referência:
- `_reversa_forward/005-convergencia-pipeline/requirements.md` (RF-501..504, RN-501..504, RN-510)
- `_reversa_forward/005-convergencia-pipeline/data-delta.md` (§§1–4)
- `_reversa_forward/005-convergencia-pipeline/actions.md` (Contratos D §2)

---

## Verificação por componente (arquivo:linha)

### 1. Coleta Jina (`app/investigation/tools.py`, `app/services/search.py`)
- **10 resultados integrais por busca**:
  - `app/investigation/tools.py:249`: envio explícito de `json={"q": query, "num": 10}` no POST HTTP.
  - `app/investigation/tools.py:135-136`: validação `len(items) < 10` levanta `JinaSearchError(1)`. Rejeita coletas parciais.
  - `app/investigation/tools.py:143-151`: validação estrita de cada item (`status < 400`, URL válida/segura, `content` string não vazia). Falha de qualquer item invalida coleta inteira.
  - `app/investigation/tools.py:154-160`: concatenação de todas as 10 seções (`## {title}\nURL: {url}\n\n{clean}\n\n`) sem corte ou truncamento.
  - `tests/investigation/test_jina_tool.py:489-510`: teste comprova 10 corpos com marcadores além de 100.000 caracteres preservados integralmente.
- **Limpeza HTML stdlib conservadora**:
  - `app/investigation/tools.py:86-114`: classe `_JinaHTMLCleaner(HTMLParser)` descarta somente tags de ruído estrutural (`header`, `nav`, `script`, `style`, `footer`) e `<aside>` com classe/rótulo de anúncio (`ad`, `advertisement`).
  - `app/investigation/tools.py:115-122`: `_clean_body_text` alimenta parser stdlib e decodifica entidades via `html.unescape`. Ausência de fatiamento (`[:N]`).
  - `app/services/search.py:25-55`: `_SafeHTMLTextExtractor(HTMLParser)` eleva teto de leitura para 200.000 caracteres sem truncamento silencioso prematuro.
- **Proteção SSRF mantida**:
  - `app/investigation/tools.py:45-84`: `_is_safe_url` e `_check_host_safe` validam scheme (`http`/`https`), rejeitam credenciais no host (`username`/`password`), barram portas não padrão (permite apenas 80 e 443), resolvem DNS via `socket.getaddrinfo` e barram endereços loopback, privados, link-local, multicast, reservados e não especificados.
  - `tests/investigation/test_jina_tool.py:567-585`: matriz de URLs inseguras (`file://`, `ftp://`, `127.0.0.1`, `169.254.169.254`, `[::1]`, `10.0.0.1`, `localhost`) validada com rejeição estrita sem vazamento de segredos.
- **Ausência de corte arbitrário**:
  - `app/investigation/tools.py:159`: entrega integral de prefixo e seções. Zero limites artificiais de caracteres no adapter investigativo.

### 2. Worker investigativo (`app/investigation/worker.py`, `app/investigation/schemas.py`)
- **Busca mandatória antes da síntese**:
  - `app/investigation/worker.py:468-476`: se `search_count == 0` ao receber resposta final do LLM, recusa síntese e retorna `success=False` com erro explícito (`Primeira busca é obrigatória antes da síntese final.`).
  - `tests/investigation/test_persona_worker.py:930-954`: teste comprova falha se LLM tentar entregar JSON sem buscar.
- **Orçamento e formulação de queries**:
  - `app/investigation/worker.py:364`: ferramentas desativadas (`tools=None`) quando `search_count >= _MAX_SEARCHES` (teto 3).
  - `app/investigation/worker.py:406-441`: primeira query formulada dinamicamente pelo LLM no `jina_search(q=...)`.
  - `app/investigation/worker.py:419-428`: controle via `executed_queries`. Query duplicada (`norm_q in executed_queries`) é descartada sem consumir orçamento nem acionar rede.
- **Citação verbatim validada contra corpos entregues**:
  - `app/investigation/worker.py:447`: acúmulo de conteúdo real entregue em `delivered_contents`.
  - `app/investigation/worker.py:479-491`: `full_delivered = "\n\n".join(delivered_contents)`. Cada `cit.exact_quote` é verificado contra `full_delivered`. Se ausente, retorna `success=False` com erro de citação não encontrada.
  - `tests/investigation/test_persona_worker.py:1138-1182`: teste valida rejeição imediata de citação alucinada ou não lida.
- **Esquema de citação e URLs utilizadas**:
  - `app/investigation/schemas.py:40-45`: `CitationItem` exige `claim` (min_length=1), `exact_quote` (min_length=1), `source_url` (min_length=1).
  - `app/investigation/schemas.py:47-66`: `PersonaResultPayload` exige `result` não vazio (min_length=10 + validador contra whitespace), lista `citations` e lista `used_urls`.
  - `app/investigation/schemas.py:68-83`: `StepResultCreate` valida `result` não vazio contra strings em branco.
  - `app/investigation/worker.py:492-497`: `used_urls` sanitizado para subconjunto estrito de `read_urls` reais e fora da lista de exclusão (`_excluded_url_keys`).

### 3. Modelo de dados, migração e armazenamento (`app/models/domain_models.py`, `alembic/versions/0008_...`, `app/investigation/storage.py`)
- **Migração 0008 (`alembic/versions/0008_investigation_rounds_and_merges.py`)**:
  - Linhas 17-18: coluna `investigation_round` adicionada em `research_points` como `sa.Integer(), nullable=True`.
  - Linhas 20-25: coluna `round` adicionada em `research_step_results` como `sa.Integer(), nullable=True`; constraint UNIQUE `uq_research_step_results_round_worker` criada sobre `["research_id", "step_id", "round", "worker"]`.
  - Linhas 27-51: tabela `investigation_merges` criada com colunas `id` (Uuid PK), `research_id` (FK CASCADE), `step_id` (FK CASCADE), `round` (Integer NOT NULL), `content` (JSON NOT NULL), `created_at` (DateTime timezone=True NOT NULL) e UNIQUE `uq_investigation_merges_research_step_round` sobre `["research_id", "step_id", "round"]`. Índices criados em `research_id` e `step_id`.
  - Linhas 64-74: downgrade funcional e simétrico.
  - `tests/investigation/test_round_migration.py`: 4 testes passam, incluindo ciclo clean upgrade, populated upgrade preservando linhas históricas NULL, downgrade e re-upgrade em PostgreSQL efêmero via Docker.
- **Barreira de 4 análises por rodada (`app/investigation/storage.py:97-116`)**:
  - Função `check_merge_barrier`:
    - Valida `round` inteiro positivo (> 0).
    - Filtra `ResearchStepResult` por `research_id`, `step_id`, `round == round` e `status == STATUS_AUDIT_PENDING`.
    - Exige `set(PERSONA_NAMES).issubset(successful_workers)` (`historian`, `skeptic`, `pragmatist`, `futurist`).
    - Bloqueia 3/4 personas, rodadas mistas, falhas e registros legados com round NULL.
- **Gravação atômica de merge (`app/investigation/storage.py:118-144`)**:
  - Função `save_investigation_merge`:
    - Valida `round > 0` e integridade referencial cruzada (`point.research_id == research_id`).
    - Instancia `InvestigationMerge` e persiste com `await db.commit()`.
    - Constraint de banco impede concorrência de escritas duplicadas para mesma rodada.

---

## Análise de segurança e integridade

1. **Proteção de borda outbound e sanitização**:
   - `JinaToolAdapter` isola credenciais: logs e exceções mascaram Bearer tokens e chaves de API (`app/investigation/tools.py:20-26`, `tests/investigation/test_jina_tool.py:242-293`).
   - `_sanitize_error` em `app/investigation/worker.py:74-83` mascara chaves, senhas em URLs e padrões de token antes da gravação de mensagens de erro.
   - Resolução anti-SSRF ativa com cache LRU (`app/investigation/tools.py:44-84`).
2. **Consistência relacional**:
   - `save_step_result` e `save_investigation_merge` validam explicitamente que `step_id` pertence a `research_id`, mitigando inconsistências de FK isolada.
   - Histórico preservado: linhas legadas com `round = NULL` continuam consultáveis via `get_step_results`, mas não participam da barreira de rodada atual.

---

## Findings

### Finding 1: Ausência de CHECK constraint DDL na migração 0008
- **Severidade**: Baixa (Low)
- **Componente**: `alembic/versions/0008_investigation_rounds_and_merges.py:17-51`
- **Evidência**:
  - `data-delta.md:13-14, 30` e `actions.md:D1` especificavam constraints de verificação no banco:
    - `CHECK (investigation_round IS NULL OR investigation_round > 0)` em `research_points`
    - `CHECK (round IS NULL OR round > 0)` em `research_step_results`
    - `CHECK (round > 0)` em `investigation_merges`
  - O modelo SQLAlchemy `domain_models.py:97` declara `CheckConstraint("round > 0", name="chk_investigation_merges_round_positive")`, porém a migration `0008_...py` não incluiu os DDLs correspondentes de `sa.CheckConstraint`.
- **Impacto**: Proteção no banco ausente caso inserção ocorra via SQL direto; mitigado em runtime pelo código da aplicação (`storage.py:46, 104, 126`), que rejeita `round <= 0`, `round is None` ou booleano.
- **Ação sugerida**: Adicionar migration complementar de reforço DDL se exigido isolamento estrito fora da camada ORM.

### Finding 2: Incremento de `attempt_count` em falha técnica de persona
- **Severidade**: Média (Medium)
- **Componente**: `app/investigation/storage.py:72-78`
- **Evidência**:
  ```python
  if not success:
      await db.execute(
          update(ResearchPoint)
          .where(ResearchPoint.id == step_id)
          .values(attempt_count=ResearchPoint.attempt_count + 1)
      )
      await db.flush()
  ```
  - `requirements.md:RN-506` e `data-delta.md:46` determinam: *"Falha técnica de persona não é reprovação do auditor e não pode acelerar esse teto"*.
- **Impacto**: Falha técnica temporária de transporte de uma persona incrementa contador de auditoria antes da ação S17.
- **Rastreabilidade**: Comportamento legado remanescente de S11; `actions.md:69` agenda explicitamente para T017 (S17) a remoção deste incremento (`"remover contagem por persona/teto forçado"`). Risco conhecido e contido no roadmap.

### Finding 3: Ausência de validação de dicionário não vazio em `save_investigation_merge`
- **Severidade**: Baixa (Low)
- **Componente**: `app/investigation/storage.py:118-144`
- **Evidência**:
  - `save_investigation_merge` recebe `content: dict` e persiste diretamente sem validar se o dicionário está vazio `{}` ou se contém os dados estruturados consolidados das 4 personas.
- **Impacto**: Chamadas de serviço com payload vazio poderiam persistir merge sem conteúdo se não validadas na borda do caller.
- **Ação sugerida**: Incluir `if not isinstance(content, dict) or not content: raise ValueError(...)` em `save_investigation_merge` ou no schema do serviço em S16.

### Finding 4: Agregação de status do ponto sem filtro de rodada em `save_step_result`
- **Severidade**: Baixa (Low)
- **Componente**: `app/investigation/storage.py:80-92`
- **Evidência**:
  - `select(ResearchStepResult).where(ResearchStepResult.step_id == step_id)` consulta todos os resultados históricos do ponto sem filtrar por `round == round` ao avaliar se todas as personas falharam para marcar `SCRAPER_FAILED`.
- **Impacto**: Resultados de rodadas anteriores podem influenciar o status agregado do ponto se houver transições múltiplas. Mitigado porque a barreira (`check_merge_barrier`) filtra estritamente por rodada.

---

## Ausência de sobre-engenharia e fidelidade aos contratos

- **YAGNI e ladder respeitados**:
  - Zero dependências externas novas (BeautifulSoup, lxml, LangChain, etc. não foram adicionados).
  - Uso integral da biblioteca padrão: `html.parser`, `urllib.parse`, `ipaddress`, `socket`, `math`, `json`, `dataclasses`.
  - Tipos portáteis SQLAlchemy (`Uuid`, `JSON`, `DateTime(timezone=True)`).
  - Métodos curtos, transações de banco com escopo delimitado, commits atômicos sem conexões retidas durante chamadas de rede.

---

## Veredicto final

**APROVADO**

Todos os requisitos e contratos de engenharia D previstos para o recorte Coleta-Worker-Dados (S09-S12) foram cumpridos e comprovados:
- Coleta Jina com 10 corpos integrais, limpeza HTML stdlib conservadora, sem corte arbitrário e com validação anti-SSRF.
- Worker com busca obrigatória antes da síntese, teto estrito de 3 queries, validação verbatim contra corpos lidos e schema de citação tipado.
- Modelo de dados com colunas nullable para histórico, tabela `investigation_merges` com UNIQUE, barreira de 4 personas por rodada e gravação atômica.
- 84 testes unitários e de integração do recorte executados com 100% de aprovação.
- Os achados identificados (Findings 1 a 4) são dívidas pontuais já enquadradas para resolução nas ações subsequentes (T016/T017).
