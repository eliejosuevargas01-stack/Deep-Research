# Modelo de Domínio e Banco de Dados: Deep Research Engine

> Gerado por Reversa SDD Engine  
> Data: 2026-10-04  
> Projeto: Deep Research Engine

## 1. Entidades de Domínio

### 1.1 `Research` (Raiz de Agregação)
Representa uma sessão de pesquisa profunda solicitada por um operador ou cliente backend.
- `id` (UUID): Identificador único global.
- `theme` (String 500): Assunto de pesquisa submetido pelo usuário.
- `callback_url` (String 2048, nullable): URL de webhook para despacho do relatório final.
- `status` (Enum): `scouting`, `pending_approval`, `revising`, `approved`, `in_progress`, `completed`, `completed_but_callback_failed`, `blocked`, `failed`, `interrupted`.
- `briefing_draft` (JSON): Rascunho de 5 pontos gerado pelo Scout com notas de revisão.
- `error` (Text, nullable): Mensagem de erro higienizada.
- `approved_at` (DateTime, nullable): Timestamp de aprovação única do briefing.
- `created_at` / `updated_at` (DateTime): Timestamps com timezone UTC.

### 1.2 `ResearchPoint` (Ponto de Investigação)
Representa um dos tópicos do briefing a ser pesquisado pelas 4 personas.
- `id` (UUID): Identificador único.
- `research_id` (UUID, FK -> `research.id` on delete CASCADE): Pesquisa vinculada.
- `position` (Integer): Ordem de exibição (0 a 4).
- `title` (String 500): Título do ponto em pt-BR.
- `description` (Text): Descrição das diretrizes de investigação.
- `dependencies` (JSON List): Lista de referências a pontos predecessores (1-based index ou título).
- `is_parallelizable` (Boolean): Se o ponto pode rodar concorrentemente com outros do lote.
- `status` (Enum): `pending`, `in_progress`, `approved`, `blocked`, `failed`.
- `attempt_count` (Integer): Número de tentativas de auditoria já realizadas (0 a 4).
- `audit` (JSON): Resultado da auditoria determinística e cognitiva.

### 1.3 `Evidence` (Evidência Coletada por Persona)
Representa um trecho factual coletado de uma página da web por uma das personas.
- `id` (UUID): Identificador único.
- `research_point_id` (UUID, FK -> `research_points.id` on delete CASCADE): Ponto associado.
- `persona` (String 24): Persona autora (`historian`, `skeptic`, `pragmatist`, `futurist`).
- `source_url` (Text): URL completa da fonte consultada.
- `source_title` (Text): Título da página ou documento.
- `excerpt` (Text): Citação exata verbatim extraída da página.
- `claim` (Text): Afirmação sustentada pelo trecho.
- `analysis` (Text): Análise contextual da persona com marcações de incerteza.
- `accessed_at` (DateTime): Data e hora da coleta.
- `version` (Integer): Controle de concorrência otimista (*optimistic locking*).
- **Restrição de Unicidade**: `(research_point_id, persona, source_url)`.

### 1.4 `Event` / `AgentEventLog` (Eventos de Stream em Tempo Real)
Armazena eventos operacionais públicos transmitidos via SSE.
- `id` (Integer, Auto-increment): Cursor incremental para reconexão via `Last-Event-ID`.
- `research_id` (UUID, FK -> `research.id` on delete CASCADE): Pesquisa vinculada.
- `persona` (String 24): Identificador do agente emissor (`scout`, `historian`, `auditor`, `system`, etc.).
- `event_type` (String 64): Tipo do evento (`scout_started`, `sources_scanned`, `verdict_rendered`, etc.).
- `summary` (String 500): Resumo textual seguro em linguagem natural.
- `metrics` (JSON): Metadados quantitativos seguros (quantidades de fontes, rodada, ID do ponto).
- `created_at` (DateTime): Timestamp de geração.

### 1.5 `Report` (Relatório Final Sintetizado)
O documento final em formato Markdown fundamentado nas evidências.
- `id` (UUID): Identificador único do relatório.
- `research_id` (UUID, FK -> `research.id` on delete CASCADE, Unique): Pesquisa correspondente.
- `content_markdown` (Text): Texto integral do relatório em pt-BR com citações em links Markdown.
- `citation_metrics` (JSON): Métricas de contagem de fontes e evidências validadas.
- `audit_findings` (JSON): Registro consolidado de todas as decisões do auditor por ponto.
- `generated_at` (DateTime): Data e hora de conclusão da síntese.

### 1.6 `AuditTrail` (Trilha de Auditoria e Qualidade)
Registro imutável de cada tentativa de auditoria, falhas de workers ou despacho de webhook.
- `id` (Integer, Auto-increment): Identificador.
- `research_id` (UUID, FK -> `research.id` on delete CASCADE): Pesquisa.
- `point_id` (UUID, FK nullable): Ponto auditado, se aplicável.
- `stage` (String 32): Etapa registrada (`point_audit`, `worker_failure`, `callback`).
- `attempt` (Integer, nullable): Número da tentativa.
- `details` (JSON): Detalhes completos do veredito ou do erro.
- `created_at` (DateTime): Timestamp do evento de auditoria.

### 1.7 `AdminSession` (Sessão Administrativa Revogável)
Sessões ativas do operador via cookie seguro.
- `id` (UUID): ID interno da sessão.
- `token_hash` (String 64, Unique): Hash criptográfico do `jti` do token JWT emitido.
- `csrf_hash` (String 64): Hash do segredo CSRF emitido para proteção de mutações.
- `expires_at` (DateTime): Data limite de expiração da sessão.
- `revoked_at` (DateTime, nullable): Data de revogação explícita (logout).
- `created_at` (DateTime): Data de criação.

### 1.8 `AppSettings` (Configurações e Credenciais Criptografadas)
Armazenamento das chaves de API e mapeamentos de modelo com criptografia AES-256-GCM.
- `id` (Integer, PK = 1): Registro singleton de configurações do sistema.
- `encrypted_credentials` (JSON/Text): Dicionário de chaves de provedores criptografadas.
- `models` (JSON): Mapeamento de modelo por agente (`scout`, `historian`, `auditor`, etc.).
- `callback_url` (String 2048, nullable): Webhook global para pesquisas originadas na UI.
- `openai_base_url` (String 2048, nullable): Base URL personalizada para provedor compatível OpenAI.
- `updated_at` (DateTime): Timestamp da última alteração com hot-reload dinâmico.
