# Investigation: Pesquisa Técnica e Padrões Arquiteturais MVP

> Identificador: `001-pesquisa-profunda-mvp`
> Data: `2026-10-21`
> Contexto: Cenário Greenfield — Pipeline de Pesquisa Profunda Modular
> Fontes primárias de autoridade: `_reversa_sdd/prd.md`, `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md`, `_reversa_sdd/sdd/endpoint-busca-com-personas.md`, `_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md`, `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md` e `_reversa_forward/001-pesquisa-profunda-mvp/requirements.md`.

---

## 1. Pesquisa de Fundo e Panorama do Problema

### 1.1 Contexto e Justificativa de Engenharia
Investigações manuais na web consomem múltiplos dias de analistas de inteligência de mercado, padecem de viés analítico e frequentemente produzem relatórios nos quais os links primários foram perdidos. Ferramentas comerciais existentes (tais como Perplexity Pro, OpenAI Deep Research e Gemini Deep Research) operam como "caixas-pretas" monolíticas:
- Não permitem inspecionar nem auditar os tópicos formulados antes da execução de scraping extensivo.
- Executam coletas não auditadas em lote fechado sem separação clara de hipóteses.
- Não discriminam pontos fracos, falhas de evidência ou contradições nos tópicos investigados.
- Não oferecem controle granular de custos ou desacoplamento modular de etapas.

O projeto **Deep Research MVP** estabelece um monólito modular estruturado em quatro etapas autônomas e independentes expostas por quatro endpoints HTTP REST:
1. **Plano de Investigação** (`POST /api/v1/plan`): análise rápida exclusivamente via metadados da SERP, formulando exatamente N pontos de foco.
2. **Busca com Personas** (`POST /api/v1/search`): coleta paralela para os N pontos orientada por 4 personas analíticas especializadas, com filtro de desduplicação de URLs por pesquisa e persistência integral sem truncamento.
3. **Auditoria de Qualidade** (`POST /api/v1/audit`): escrutínio crítico do material coletado por um LLM forte respondendo a um checklist de 12 perguntas formais de verificação, deliberando `aprovado` ou `reprovado` e registrando `pontos_fracos`.
4. **Redação do Dossiê** (`POST /api/v1/writer`): síntese dos pontos auditados em formato Markdown profissional com 100% de fontes canônicas rastreadas e despacho assíncrono para webhook de callback assinado criptograficamente.

---

## 2. Alternativas Avaliadas e Decisões de Arquitetura

### 2.1 Topologia do Sistema: Monólito Modular vs. Microsserviços Distribuídos

| Abordagem | Vantagens | Desvantagens | Decisão |
|-----------|-----------|--------------|---------|
| **Microsserviços com filas (RabbitMQ/Celery)** | Escalabilidade independente por etapa | Complexidade operacional severa, latência de broker, overhead de manutenção no MVP, múltiplos contêineres | **Descartada** |
| **Monólito Modular FastAPI com SQLite WAL** | Deploy em contêiner único, acoplamento fraco, simplicidade operacional, transações atômicas locais, atende meta de <10min | Concorrência limitada à máquina hospedeira | **Adotada 🟢** (`_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais`) |

**Racional:** O PRD veda expressamente complexidade arquitetural desnecessária no MVP e limita a quatro endpoints operacionais principais. O padrão de monólito modular com módulos de domínio isolados (`app/core/planner.py`, `app/core/searcher.py`, `app/core/auditor.py`, `app/core/writer.py`) e persistência relacional local atende com folga ao requisito de isolamento e independência entre as fases.

---

### 2.2 Estratégia de Persistência Relacional: SQLite em Modo WAL

| Opção | Análise Técnica | Decisão |
|-------|-----------------|---------|
| **PostgreSQL / MySQL em contêiner separado** | Alta concorrência de escrita, porém exige orquestração de banco externo, volume e rede no MVP. | **Descartada** |
| **SQLite permanente em volume com WAL (Write-Ahead Logging)** | Nativo Python/SQLAlchemy, zero dependência de processo externo, suporta múltiplos leitores simultâneos e um escritor com latência sub-milissegundo, preserva dados entre reinicializações de contêiner. | **Adotada 🟢** (`_reversa_sdd/prd.md#8-modelo-de-dados-tabelas`) |

**Padrão adotado:**
- Driver assíncrono `aiosqlite` integrado ao `SQLAlchemy 2.0`.
- Ativação obrigatória de pragmas na conexão:
  ```sql
  PRAGMA journal_mode = WAL;
  PRAGMA synchronous = NORMAL;
  PRAGMA foreign_keys = ON;
  PRAGMA busy_timeout = 30000;
  ```
- O parâmetro `busy_timeout` de 30 segundos evita erros de bloqueio de escrita (`sqlite3.OperationalError: database is locked`) durante operações concorrentes de persistência em segundo plano.

---

### 2.3 Mecanismo de Criptografia em Repouso para Credenciais Sensíveis

Conforme resolvido no alinhamento autônomo com o usuário (`requirements.md#10-lacunas`), a tabela `credenciais` exige cifra reversível, pois as chaves de API precisam ser recuperadas pelo sistema em tempo de execução para autenticar chamadas externas.

| Alternativa | Criptografia / Algoritmo | Viabilidade Técnica | Decisão |
|-------------|--------------------------|---------------------|---------|
| **HMAC-SHA256 em repouso** | Digest unidirecional (não-cifra) | Inviável: digest não pode ser decifrado; sistema não recuperaria as chaves de API. | **Descartada (Tecnicamente Incorreta)** |
| **AES-GCM customizado** | Cifra simétrica autenticada | Exige gestão manual de IV/nonce e authentication tag; risco de reuso de nonce se mal implementado. | **Descartada** |
| **Fernet (`cryptography.fernet`)** | Cifra simétrica autenticada baseada em AES-128-CBC + HMAC-SHA256, com timestamp e rotação de chaves suportada. Chave de 32 bytes base64 via `CREDENTIALS_MASTER_KEY`. | Perfeito: pacote padrão da indústria (`cryptography`), API à prova de erros, determinística e segura. | **Adotada 🟡** (`requirements.md#10-lacunas`) |

**Precedência de Variáveis de Ambiente:**
Conforme regra RN-10 (`requirements.md#4-regras-de-negocio-novas-ou-alteradas`), variáveis de ambiente configuradas no contêiner têm precedência absoluta sobre registros salvos no banco de dados. O fluxo de leitura é:
1. `os.environ.get(KEY)` → se presente e não-vazio, utiliza imediatamente.
2. Caso ausente no ambiente → consulta tabela `credenciais`, recupera o valor cifrado e aplica `fernet.decrypt()`.
3. Caso ausente em ambos → lança exceção explícita de configuração (sem fallback hardcoded).

---

### 2.4 Padrão de Assinatura e Autenticação do Webhook de Callback

O endpoint `POST /api/v1/writer` despacha o dossiê consolidado para a URL cadastrada via variável `CALLBACK_WEBHOOK_URL` ou registro de configuração.

| Mecanismo | Funcionamento | Segurança e Compatibilidade | Decisão |
|-----------|---------------|------------------------------|---------|
| **Sem autenticação (payload puro)** | POST simples | Vulnerável a spoofing e injeção de resultados falsos no receptor. | **Descartada** |
| **Bearer Token no header Authorization** | Token estático | Não garante a integridade do corpo da mensagem transmitida. | **Descartada** |
| **HMAC-SHA256 no cabeçalho `X-Signature`** | Assinatura HMAC calculada sobre os bytes brutos do corpo HTTP com `WEBHOOK_HMAC_SECRET`: `X-Signature: sha256=<hex_digest>`. Receptor valida com `hmac.compare_digest`. | Padrão GitHub/Stripe, integridade e autenticidade criptográfica garantidas sem timing attacks. | **Adotada 🟡** (`requirements.md#10-lacunas`) |

---

### 2.5 Resiliência e Políticas de Retentativas de Integrações Externas

O PRD impõe restrição estrita de 1 tentativa inicial mais 3 retentativas automáticas (`1 + 3 retries`) e timeout de 600 segundos para todas as chamadas externas (`_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais`).

**Implementação Técnica:**
- Biblioteca `tenacity` com decorators assíncronos nos clientes HTTP (`httpx.AsyncClient`):
  - Tentativas máximas: 4 (`stop=stop_after_attempt(4)`).
  - Backoff exponencial com jitter: `wait=wait_exponential_jitter(initial=1, max=30, jitter=1)`.
  - Condições de retentativa: erros de conexão (`httpx.ConnectError`, `httpx.ConnectTimeout`), timeout (`httpx.ReadTimeout`) e códigos de status HTTP 429 (Rate Limit) e 5xx (500, 502, 503, 504).
  - Códigos 4xx (exceto 429) são terminais e lançam erro imediato sem retry.
  - Timeout por chamada configurado em 600 segundos (`httpx.Timeout(600.0, connect=30.0)`).

---

## 3. Padrões de Integração Externa

### 3.1 Jina SERP e Jina Scrapper (`s.jina.ai`)
1. **Etapa 1 (Plano):** Chamada restrita a metadados da SERP (`https://s.jina.ai/<query>` ou endpoint REST de busca Jina com headers `X-No-Cache: true`, `Accept: application/json`). Proibido download do corpo integral de páginas nesta fase.
2. **Etapa 2 (Busca):**
   - Extração dos links retornados pela consulta da persona.
   - Deduplicação contra histórico da pesquisa (`SELECT urls_lidas FROM conteudo_coletado WHERE id_pesquisa = :id_pesquisa`).
   - Requisição de conteúdo completo ao scraper Jina (`https://r.jina.ai/<url>`) para cada URL inédita.
   - Preservação integral do Markdown retornado sem cortes de texto.

### 3.2 Modelos de Linguagem OpenAI-Compatible
- **Modelo Leve (Busca paralela):** Focado em velocidade e formatação de queries/análise sob as personas (`historiador`, `visionario`, `cetico`, `futurista`).
- **Modelo Forte (Auditoria e Redação):** Focado em raciocínio crítico rigoroso (avaliação das 12 perguntas de qualidade) e síntese narrativa estruturada com ancoragem canônica.
- Chamadas HTTP padronizadas no formato `/v1/chat/completions` com schema Pydantic serializado via `response_format={"type": "json_object"}` para as etapas analíticas que exigem parsing determinístico.

---

## 4. Conclusão da Investigação Técnica

A pilha tecnológica mínima e estritamente aderente ao PRD e aos princípios Reversa é:
- **Linguagem:** Python 3.11+
- **Framework Web:** FastAPI + Uvicorn (ASGI assíncrono)
- **Persistência:** SQLAlchemy 2.0 assíncrono + SQLite permanente (modo WAL via `aiosqlite`)
- **Segurança:** `cryptography.fernet` (tabela de credenciais) e `hashlib`/`hmac` stdlib (assinatura de webhook)
- **Cliente HTTP e Resiliência:** `httpx` + `tenacity`
- **Validação de Contratos:** Pydantic v2
- **Testabilidade:** Pytest com mocks de transporte HTTP (`httpx.MockTransport`) para isolamento total de rede nos testes de unidade e integração.