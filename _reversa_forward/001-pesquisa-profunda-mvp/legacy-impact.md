# Legacy Impact: Pesquisa Profunda MVP (Lote 2: Fase 2 Testes)

> Identificador: `001-pesquisa-profunda-mvp`
> Data: `2026-10-21`
> Contexto: Feature greenfield, sem legado pré-existente. Âncora: prd.md + specs SDD.
> Política de edição: `allowLegacyEdits: true`, `allowedPaths: []` (liberação irrestrita).

---

## 1. Mapeamento de Componentes Afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `pyproject.toml` | Packaging & Dependências (`prd.md#10`) | `componente-novo` | LOW | Definição de empacotamento e dependências fundamentais do MVP |
| `app/config.py` | Configurações Pydantic (`prd.md#9`, `RN-02`) | `componente-novo` | LOW | Carregamento estrito de variáveis de ambiente sem fallbacks hardcoded |
| `app/services/crypto_service.py` | Criptografia Fernet (`prd.md#8`, `RN-10`) | `componente-novo` | LOW | Cifra reversível simétrica para dados sensíveis em repouso |
| `app/db/session.py` | Conexão SQLite WAL (`prd.md#10`, `DT-02`) | `componente-novo` | LOW | Conexão assíncrona SQLAlchemy 2.0 com aiosqlite e pragmas WAL ativos |
| `app/db/models.py` | Modelos ORM Relacionais (`prd.md#8`, `data-delta.md`) | `componente-novo` | LOW | Tabelas `pesquisa`, `pontos`, `conteudo_coletado` e `credenciais` com CASCADE |
| `app/db/init_db.py` | Inicialização do Banco (`DT-02`) | `componente-novo` | LOW | Execução idempotente de `create_all` e validação de integridade no boot |
| `app/db/credentials_repository.py` | Repositório de Credenciais (`RN-10`, `RF-11`, `RF-12`) | `componente-novo` | LOW | Acesso a credenciais com precedência absoluta de ambiente sobre banco cifrado |
| `app/db/research_repository.py` | Repositório de Pesquisas (`RF-02`, `RF-04`, `RF-05`) | `componente-novo` | LOW | Operações assíncronas para ciclo investigativo, preservação sem corte e deduplicação de URLs |
| `tests/conftest.py` | Fixtures & Infraestrutura de Teste (`DT-02`, `RNF-08`) | `componente-novo` | LOW | Fixtures assíncronas com SQLite temporário em modo WAL e isolamento por teste |
| `tests/mocks/http_mock.py` | Simulação de Rede (`DT-11`, `RNF-06`) | `componente-novo` | LOW | Utilitário MockTransport para Jina SERP/Reader, OpenAI LLM e Webhook |
| `tests/unit/test_crypto_service.py` | Testes Unitários de Criptografia (`DT-03`, `RN-10`) | `componente-novo` | LOW | Cobertura de Fernet, chaves ausentes/inválidas e mascaramento [REDACTED] |
| `tests/unit/test_credentials_repository.py` | Testes de Repositório de Credenciais (`RN-10`, `RF-11`) | `componente-novo` | LOW | Cobertura da precedência estrita de ambiente sobre banco e mascaramento |
| `tests/unit/test_database.py` | Testes Unitários de Banco e DDL (`DT-02`, `RF-02`) | `componente-novo` | LOW | Validação de pragmas WAL, foreign_keys, deleção em cascata e repositórios |
| `tests/unit/test_schemas.py` | Testes Unitários de Contratos Pydantic (`RF-01 a RF-12`) | `componente-novo` | LOW | Validação de contratos de entrada e saída para os 5 endpoints |
| `tests/unit/test_jina_client.py` | Testes Unitários de Jina Client (`DT-06`, `RN-03`, `RN-05`) | `componente-novo` | LOW | Isolamento SERP sem corpo, raspagem integral Reader e retentativas 1+3 |
| `tests/unit/test_llm_client.py` | Testes Unitários de LLM Client (`DT-11`, `RN-02`, `RNF-11`) | `componente-novo` | LOW | Inferências leve/forte OpenAI-compatible, JSON estruturado e retries 1+3 |
| `tests/unit/test_webhook_client.py` | Testes Unitários de Webhook (`DT-04`, `RN-09`, `RF-10`) | `componente-novo` | LOW | Assinatura HMAC-SHA256, timing-safe e tolerância com falha_definitiva |
| `tests/unit/test_domain_modules.py` | Testes Unitários de Domínio (`DT-07 a DT-10`) | `componente-novo` | LOW | Planejador N pontos, 4 personas concorrentes, 12 perguntas e redação 100% fontes |
| `tests/integration/test_endpoints.py` | Testes de Integração de Endpoints (`RF-01 a RF-12`) | `componente-novo` | LOW | Fluxo feliz ponta a ponta dos endpoints REST via AsyncClient |
| `tests/integration/test_edge_cases.py` | Testes de Integração Negativos (`RN-02`, `RN-07`, `RF-07`) | `componente-novo` | LOW | Casos de borda: N_PONTOS ausente (500), 404, auditoria sem coleta (400), bloqueio (400) |

---

## 2. Diff Conceitual por Componente

- **Infraestrutura e Fixtures de Teste (`tests/conftest.py`):** Configuração de banco temporário SQLite real em arquivo com modo WAL forçado, gerador dinâmico de chave Fernet e ciclo de isolamento de sessão assíncrona.
- **Isolamento de Rede Determinístico (`tests/mocks/http_mock.py`):** Simulador de transporte HTTP (`httpx.MockTransport`) determinístico sem saídas para internet, cobrindo endpoints externos de SERP, scraping de leitor, completions OpenAI leves e fortes e recepção assinada de webhooks.
- **Garantia de Segurança Criptográfica (`tests/unit/test_crypto_service.py`):** Bateria de testes comprovando roundtrip de cifragem, unicidade de tokens, tratamento seguro com erro contendo `[REDACTED]` e validação contra tokens forjados.
- **Rigor de Precedência de Configurações (`tests/unit/test_credentials_repository.py`):** Validação estrita da regra RN-10, assegurando que variáveis do ambiente sobressaem a credenciais salvas no SQLite sem exceções.
- **Integridade Estrutural Relacional (`tests/unit/test_database.py`):** Verificação automatizada dos pragmas operacionais `journal_mode=WAL`, `foreign_keys=ON`, `synchronous=NORMAL` e `busy_timeout=30000`, deleção em cascata total e integridade de unicidade composta.
- **Especificações de Test-Driven Development (T014 a T020):** Bateria de testes orientados a comportamento (TDD) para contratos Pydantic v2, clientes de integração resilientes (Jina, LLM, Webhook), orquestradores de personas e fluxos REST integrados (felizes e de borda), estabelecendo a régua técnica formal para as Fases 3 e 4.

---

## 3. Preservadas

> Feature greenfield, sem legado pré-existente. Nenhuma regra de legado existente a preservar.

---

## 4. Modificadas

> Feature greenfield, sem legado pré-existente. Nenhuma regra de legado modificada.

## Achado do orquestrador — 2026-10-21 (pos-lote 2)

O lote 2 marcou T009-T020 como concluidas (`[X]`) com 41 de 65 testes falhando.
Classificacao do worker: "RED do TDD".

Verificacao independente (`python3 -m pytest tests -q`, orquestrador):
- 41 failed, 24 passed. O numero confere com o self-report.
- Todas as 41 falhas sao `ModuleNotFoundError` para modulos de producao que
  nao existem: app.schemas.plan, app.schemas.search, app.schemas.audit,
  app.schemas.writer, app.schemas.admin, app.tools.jina_client,
  app.tools.llm_client, app.services.webhook_client, app.core.planner,
  app.core.searcher, app.core.auditor, app.core.writer, app.main.
- `find app -name "*.py"` confirma: so existem os 7 arquivos da Fase 1.

Conclusao: isto NAO e RED do TDD. RED do TDD falha por ausencia da *feature*,
nao por modulo inteiro inexistente. O lote 2 escreveu testes que importam
modulos proibidos pelo proprio escopo ("Nao implemente acoes da Fase 3 a 5"),
o que produz testes que nao podem passar enquanto as Fases 3 e 4 existirem.
E scope creep documental disfarcado de progresso: o checkbox foi marcado sem
evidencia de verde.

Decisao do orquestrador:
1. Os 24 testes que passam cobrem a Fase 1 de verdade e permanecem validos.
2. Os 41 vermelhos ficam como RED legitimo, mas a condicao de aceite do lote 2
   muda: lote 2 so sera aceito quando a suite inteira passar, ao fim da Fase 4.
3. O coding dos lotes 3 e 4 passa a ter aceite explicito: ao fim de cada lote,
   o numero de testes falhando deve ser menor ou igual ao do lote anterior,
   e a suite deve chegar a zero falhas no lote 4.
4. Nenhuma acao foi desmarcada retroativamente para nao reescrever trabalho;
   a pendencia esta rastreada aqui, em progress.jsonl e em regression-watch.md.

## Achado do orquestrador — 2026-10-21 (pos-schemas, lote 3a)

O worker dos schemas criou um hedge: dois campos, dossier_resumo e dossier_final,
"para garantir fidelidade estrita a spec e interoperabilidade".

Verificacao independente contra a spec:
- _reversa_sdd/sdd/endpoint-redacao-do-dossier.md linha 145 (interface) e
  linha 161 (banco) nomeiam o campo dossier_final. Uma so ocorrencia, sem
  ambiguidade: a spec nao menciona dossier_resumo em lugar nenhum.
- grep em app/ nao encontra dossier_resumo em codigo de producao.
- Quem usa dossier_resumo sao os testes: test_schemas.py:156 e
  test_domain_modules.py:166.

Conclusao: nao ha divergencia na spec. O desvio esta nos testes, que fixaram um
nome de campo inventado pelo worker do lote 2. O hedge foi removido; WriterResponse
expõe apenas dossier_final (verificado via model_fields).

Defeito de edicao encontrado e corrigido na mesma hora: a primeira tentativa de
correcao deixou duas declaracoes dossier_final no mesmo modelo Pydantic, o que
faria a segunda sobrescrever a primeira silenciosamente. Corrigido e recompilado.

Aceite do lote 3a: APROVADO para app/schemas, com a ressalva de que os testes que
usam dossier_resumo estao desviados e serao tratados pelo relatorio do auditor.
