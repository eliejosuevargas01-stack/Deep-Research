# Data Delta: Modelo de Dados Relacional MVP

> Identificador: `001-pesquisa-profunda-mvp`
> Data: `2026-10-21`
> Contexto: Cenário Greenfield — Criação Inicial do Esquema SQLite Permanente
> Referências de origem: `_reversa_sdd/prd.md#8-modelo-de-dados-tabelas`, `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md#9-modelo-de-dados`, `_reversa_sdd/sdd/endpoint-busca-com-personas.md#9-modelo-de-dados`, `_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md#9-modelo-de-dados`, `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#9-modelo-de-dados` e `_reversa_forward/001-pesquisa-profunda-mvp/requirements.md#4-regras-de-negocio-novas-ou-alteradas`.

---

## 1. Resumo do Delta

Em virtude de ser um cenário greenfield, não há banco de dados legado pré-existente a ser migrado. O presente artefato define a especificação DDL formal do esquema inicial, os tipos relacionais, restrições de integridade, chaves estrangeiras, índices de alta performance e a política de ciclo de vida das tabelas no SQLite permanente.

---

## 2. Esquema Relacional Formal (Tabelas e Campos)

### 2.1 Tabela `pesquisa`
Armazena a raiz de cada ciclo investigativo submetido ao pipeline, mantendo o tema de entrada e recebendo o dossiê consolidado e os metadados de entrega do webhook ao término do fluxo.

| Campo | Tipo SQL | Modificadores | Descrição |
|-------|----------|---------------|-----------|
| `id_pesquisa` | TEXT (UUID) | PRIMARY KEY, NOT NULL | Identificador canônico da pesquisa gerado via UUID v4 na criação do plano |
| `tema` | TEXT | NOT NULL | Tema investigativo submetido pelo usuário via `POST /api/v1/plan` |
| `criado_em` | TEXT (ISO 8601) | NOT NULL | Timestamp UTC de criação da pesquisa |
| `dossier_final` | TEXT | NULL | Conteúdo analítico integral do dossiê em Markdown gerado pelo endpoint `writer` |
| `concluido_em` | TEXT (ISO 8601) | NULL | Timestamp UTC de persistência do dossiê final |
| `webhook_status` | TEXT | NULL | Status da entrega no callback: `entregue`, `pendente_reenvio` ou `falha_definitiva` |
| `webhook_resposta` | TEXT | NULL | Registro resumido do código HTTP ou detalhe da falha retornado pelo webhook receptor |

---

### 2.2 Tabela `pontos`
Armazena os N eixos de investigação formulados pela persona `planejador` a partir dos metadados da SERP na etapa 1, mantendo o status de evolução no pipeline e recebendo os apontamentos críticos da auditoria.

| Campo | Tipo SQL | Modificadores | Descrição |
|-------|----------|---------------|-----------|
| `ponto_id` | TEXT (UUID) | PRIMARY KEY, NOT NULL | Identificador exclusivo do ponto de investigação (UUID v4) |
| `id_pesquisa` | TEXT (UUID) | NOT NULL, REFERENCES `pesquisa`(`id_pesquisa`) ON DELETE CASCADE | Chave estrangeira referenciando a pesquisa raiz |
| `tema` | TEXT | NOT NULL | Cópia desnormalizada do tema da pesquisa para isolamento analítico |
| `ponto_n` | INTEGER | NOT NULL | Número sequencial do ponto (1 até N) |
| `ponto` | TEXT | NOT NULL | Enunciado temático do ponto de investigação a ser apurado |
| `status` | TEXT | NOT NULL | Estado operacional: `pendente` → `em_andamento` → `coletado` → `aprovado` / `reprovado` |
| `pontos_fracos` | TEXT | NULL | Descrição das inconsistências e fragilidades apontadas pela auditoria das 12 perguntas |
| `criado_em` | TEXT (ISO 8601) | NOT NULL | Timestamp UTC de criação do ponto |
| `atualizado_em` | TEXT (ISO 8601) | NOT NULL | Timestamp UTC da última atualização de status ou parecer de auditoria |

**Restrições e Regras de Validação:**
- Restrição de unicidade: `UNIQUE (id_pesquisa, ponto_n)`.
- Valores permitidos para `status`: `'pendente'`, `'em_andamento'`, `'coletado'`, `'aprovado'`, `'reprovado'`.
- Transição de status proibida: nenhum ponto pode passar para `aprovado` ou `reprovado` sem antes ter passado por `coletado` com registro correspondente em `conteudo_coletado`.

---

### 2.3 Tabela `conteudo_coletado`
Armazena o texto integral extraído da web pelos trabalhadores paralelos das 4 personas (`historiador`, `visionario`, `cetico`, `futurista`) na etapa de busca (`POST /api/v1/search`), sem truncamento sintático ou supressão de referências canônicas.

| Campo | Tipo SQL | Modificadores | Descrição |
|-------|----------|---------------|-----------|
| `id` | TEXT (UUID) | PRIMARY KEY, NOT NULL | Identificador canônico do registro de coleta (UUID v4) |
| `id_pesquisa` | TEXT (UUID) | NOT NULL, REFERENCES `pesquisa`(`id_pesquisa`) ON DELETE CASCADE | Chave estrangeira referenciando a pesquisa |
| `ponto_id` | TEXT (UUID) | NOT NULL, REFERENCES `pontos`(`ponto_id`) ON DELETE CASCADE | Chave estrangeira referenciando o ponto investigado |
| `tema` | TEXT | NOT NULL | Tema da pesquisa |
| `ponto` | TEXT | NOT NULL | Enunciado do ponto correspondente |
| `conteudo_coletado`| TEXT | NOT NULL | Texto integral agregado retornado pelo raspador, preservado sem cortes |
| `urls_lidas` | TEXT (JSON) | NOT NULL | Vetor serializado em JSON com todas as URLs consultadas durante o processo |
| `urls_fonte` | TEXT (JSON) | NOT NULL | Vetor serializado em JSON com as URLs canônicas selecionadas como referência |
| `criado_em` | TEXT (ISO 8601) | NOT NULL | Timestamp UTC de registro da coleta |

**Restrições:**
- Unicidade de coleta por ponto: `UNIQUE (id_pesquisa, ponto_id)`.

---

### 2.4 Tabela `credenciais`
Armazena parâmetros sensíveis de integração (chaves de API de LLM e Jina, base URLs personalizadas e segredos operacionais). Todos os valores sensíveis são obrigatoriamente cifrados em repouso com algoritmo Fernet (`cryptography.fernet`) utilizando a chave mestra `CREDENTIALS_MASTER_KEY`.

| Campo | Tipo SQL | Modificadores | Descrição |
|-------|----------|---------------|-----------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Identificador numérico da credencial |
| `chave` | TEXT | UNIQUE, NOT NULL | Identificador textual canônico da configuração (ex: `OPENAI_API_KEY`, `JINA_API_KEY`, `CALLBACK_WEBHOOK_URL`) |
| `valor_cifrado` | TEXT | NOT NULL | Carga criptografada em Base64 gerada por Fernet com `CREDENTIALS_MASTER_KEY` |
| `base_url` | TEXT | NULL | URL base de endpoint personalizada (opcional, aplicável a LLM e Jina) |
| `tipo` | TEXT | NOT NULL | Classificação funcional: `llm`, `jina`, `webhook` ou `parametro` |
| `descricao` | TEXT | NULL | Anotação descritiva da finalidade da credencial |
| `atualizado_em`| TEXT (ISO 8601) | NOT NULL | Timestamp UTC da última modificação |

---

## 3. DDL Inicial e Índices de Desempenho

```sql
-- Ativação de integridade referencial e performance WAL
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 30000;

-- 1. Tabela pesquisa
CREATE TABLE IF NOT EXISTS pesquisa (
    id_pesquisa TEXT PRIMARY KEY NOT NULL,
    tema TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    dossier_final TEXT,
    concluido_em TEXT,
    webhook_status TEXT,
    webhook_resposta TEXT
);

CREATE INDEX IF NOT EXISTS idx_pesquisa_criado_em ON pesquisa (criado_em DESC);

-- 2. Tabela pontos
CREATE TABLE IF NOT EXISTS pontos (
    ponto_id TEXT PRIMARY KEY NOT NULL,
    id_pesquisa TEXT NOT NULL,
    tema TEXT NOT NULL,
    ponto_n INTEGER NOT NULL,
    ponto TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente',
    pontos_fracos TEXT,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    FOREIGN KEY (id_pesquisa) REFERENCES pesquisa(id_pesquisa) ON DELETE CASCADE,
    CONSTRAINT uq_pesquisa_ponto_n UNIQUE (id_pesquisa, ponto_n)
);

CREATE INDEX IF NOT EXISTS idx_pontos_id_pesquisa_status ON pontos (id_pesquisa, status);

-- 3. Tabela conteudo_coletado
CREATE TABLE IF NOT EXISTS conteudo_coletado (
    id TEXT PRIMARY KEY NOT NULL,
    id_pesquisa TEXT NOT NULL,
    ponto_id TEXT NOT NULL,
    tema TEXT NOT NULL,
    ponto TEXT NOT NULL,
    conteudo_coletado TEXT NOT NULL,
    urls_lidas TEXT NOT NULL,
    urls_fonte TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    FOREIGN KEY (id_pesquisa) REFERENCES pesquisa(id_pesquisa) ON DELETE CASCADE,
    FOREIGN KEY (ponto_id) REFERENCES pontos(ponto_id) ON DELETE CASCADE,
    CONSTRAINT uq_conteudo_ponto UNIQUE (id_pesquisa, ponto_id)
);

CREATE INDEX IF NOT EXISTS idx_conteudo_id_pesquisa ON conteudo_coletado (id_pesquisa);

-- 4. Tabela credenciais (criptografada com Fernet)
CREATE TABLE IF NOT EXISTS credenciais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT UNIQUE NOT NULL,
    valor_cifrado TEXT NOT NULL,
    base_url TEXT,
    tipo TEXT NOT NULL,
    descricao TEXT,
    atualizado_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_credenciais_chave ON credenciais (chave);
```

---

## 4. Política de Precedência e Resolução em Execução

Para garantir isolamento de contêineres e segurança de operação, a camada de acesso a dados (`app/db/credentials_repository.py`) adota a regra de negócio **RN-10**:

```
      [Requisição de Parâmetro/Chave (ex: OPENAI_API_KEY)]
                               |
                               v
            Existe no Ambiente (os.environ)?
                    /                \
                 SIM                  NÃO
                 /                      \
      Retorna valor do ENV         Existe na tabela 'credenciais'?
      (Precedência imediata)          /                     \
                                   SIM                       NÃO
                                   /                           \
                        Aplica Fernet.decrypt()        Erro 500: Chave Ausente
                        com CREDENTIALS_MASTER_KEY     (Sem fallback hardcoded)
```

---

## 5. Estratégia de Inicialização e Migrações

- **Inicialização Limpa (Boot):** A aplicação executa `init_db()` na inicialização do ciclo de vida FastAPI (`lifespan`), executando as declarações DDL idempotentes (`CREATE TABLE IF NOT EXISTS`) e verificando a ativação de `PRAGMA foreign_keys = ON;`.
- **Evolução Futura:** O projeto adota suporte arquitetural para migrações via Alembic a partir do baseline gerado, permitindo acréscimo de colunas ou novos índices sem interrupção de serviço. O arquivo de banco relacional deve residir obrigatoriamente no caminho persistido montado pelo contêiner (ex: `/data/deep_research.db`).