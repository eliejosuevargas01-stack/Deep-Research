# Regression Watch: Pesquisa Profunda MVP (Lote 1: Fase 1 Preparação)

> Identificador: `001-pesquisa-profunda-mvp`
> Data: `2026-10-21`
> Contexto: Cenário greenfield — sem regras 🟢 pré-existentes extraídas de código anterior.

---

## 1. Watch Principal de Regressão

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| - | - | *(Nenhum item no watch principal: cenário greenfield sem regras 🟢 extraídas previamente)* | - | - |

---

## 2. Observações (Requisitos Funcionais e Arquiteturais Implementados)

Regras e requisitos implementados nesta fase de preparação (lote 1: T001 a T008) a partir das specs SDD, sem peso de regressão imediato. Ganharão status 🟢 em futuras extrações `/reversa` sobre o código consolidado:

| ID | Origem (arquivo, seção) | Requisito / Regra Implementada | Tipo de Verificação | Sinal de Violação |
|---|---|---|---|---|
| W001 | `prd.md#9`, `RN-02` | Carregamento de configurações exclusivamente via ambiente/banco sem valores padrão rígidos | Presença | Presença de fallback default estático como `n_pontos = 5` no código |
| W002 | `prd.md#8`, `RN-10` | Precedência estrita de variáveis de ambiente (`os.environ`) sobre chaves cifradas na tabela `credenciais` | Presença | Sobrescrita de valor de variável de ambiente por registro recuperado do banco |
| W003 | `prd.md#8`, `DT-03` | Criptografia simétrica em repouso das credenciais através de Fernet (`cryptography`) | Presença | Gravação de tokens ou chaves de API em texto claro na tabela `credenciais` |
| W004 | `prd.md#10`, `DT-02` | Persistência relacional SQLite assíncrona com pragmas `journal_mode=WAL`, `foreign_keys=ON`, `synchronous=NORMAL` e `busy_timeout=30000` | Presença | Ausência de execução de pragmas ou falha de integridade em chaves estrangeiras |
| W005 | `prd.md#8`, `RF-02` | Chave estrangeira com exclusão em cascata (`CASCADE`) de `pesquisa` para `pontos` e `conteudo_coletado` | Presença | Registros órfãos permanecendo após deleção da pesquisa raiz |
| W006 | `data-delta.md#2.2`, `RF-02` | Unicidade sequencial por pesquisa (`UNIQUE(id_pesquisa, ponto_n)`) | Presença | Duplicação permitida do mesmo ordinal `ponto_n` em uma mesma pesquisa |
| W007 | `prd.md#8`, `RF-05`, `RN-05`| Preservação de texto coletado sem truncamento ou supressão de URLs de origem | Presença | Cortes sintáticos ou truncamento intencional de conteúdo textual na persistência |
| W008 | `prd.md#7`, `RF-04`, `RN-04`| Deduplicação de URLs consultadas por `id_pesquisa` a partir de coletas anteriores | Presença | Repetição de URLs já lidas sendo reenviadas para extração na mesma pesquisa |
| W009 | `conftest.py`, `DT-02`, `RNF-08` | Isolamento de testes com SQLite temporário permanente em arquivo em modo WAL | Presença | Testes executando sobre base em memória sem validação de concorrência WAL |
| W010 | `http_mock.py`, `DT-11`, `RNF-06` | Simulação determinística de rede via httpx.MockTransport cobrindo Jina, LLM e Webhook | Presença | Testes realizando saídas de rede externas não simuladas |
| W011 | `test_crypto_service.py`, `DT-03` | Cifragem Fernet, unicidade de tokens e redação segura com [REDACTED] | Presença | Vazamento de chave mestra ou tokens decifrados em mensagens de erro |
| W012 | `test_credentials_repository.py`, `RN-10` | Precedência obrigatória de variáveis de ambiente sobre credenciais salvas no banco | Presença | Banco de dados sobrescrevendo configurações ativas de ambiente |
| W013 | `test_database.py`, `DT-02`, `RF-02` | Integridade relacional DDL, pragmas WAL, deleção em cascata e unicidade uq_pesquisa_ponto_n | Presença | Falha de pragmas ou persistência de registros órfãos após exclusão |
| W014 | `test_schemas.py`, `RF-01 a RF-12` | Contratos estritos Pydantic v2 com validação de limites de caracteres e campos obrigatórios | Presença | Aceitação de payloads malformatados ou temas fora do intervalo 5..500 |
| W015 | `test_jina_client.py`, `RN-03`, `RN-05` | Acesso estrito a metadados na SERP e preservação integral sem truncamento no Reader | Presença | Download de corpo na SERP ou truncamento artificial de texto coletado |
| W016 | `test_llm_client.py`, `RN-02`, `RNF-11` | Inferência OpenAI-compatible com modelos leve/forte, parsing JSON e retries 1+3 | Presença | Fallback para modelo não configurado ou ausência de retentativa com backoff |
| W017 | `test_webhook_client.py`, `DT-04`, `RN-09` | Assinatura HMAC-SHA256 timing-safe sobre raw bytes e tolerância a falhas com falha_definitiva | Presença | Comparação timing-unsafe de assinatura ou perda de dossiê em erro de entrega |
| W018 | `test_domain_modules.py`, `DT-07 a DT-10` | Orquestração de planejador (N pontos), 4 personas concorrentes, 12 perguntas e redação 100% fontes | Presença | Redação gerada com pontos pendentes ou omissão de fontes canônicas |
| W019 | `test_endpoints.py`, `RF-01 a RF-12` | Integração dos endpoints operacionais e administrativos com respostas estruturadas | Presença | Quebra de contrato REST ou dessincronização de identificadores de pesquisa |
| W020 | `test_edge_cases.py`, `RN-02`, `RN-07` | Respostas de erro canônicas (500 ausência N_PONTOS, 404 inexistente, 400 bloqueios) | Presença | Degradação graciosa silenciosa ou assunção de fallbacks arbitrários |

---

## 3. Histórico de Re-Extrações

*(Vazio no cenário greenfield inicial; será preenchido pelo agente reverso em futuras extrações `/reversa`)*

---

## 4. Arquivadas

*(Nenhum item arquivado)*
