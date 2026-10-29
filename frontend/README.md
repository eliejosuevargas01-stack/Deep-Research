# Deep Research — Frontend (Checkpoint 1)

Interface web profissional e de alta confiabilidade para o **Deep Research**, desenvolvida com **React 18**, **TypeScript**, **Vite** e **CSS Puro** tokenizado, inspirada na identidade visual dos docs da **DominusLabs** (violeta `#6D28D9`/`#7C3AED`, índigo `#4F46E5`, papel `#F9FAFB`, fontes Outfit, Inter e JetBrains Mono) e construída estritamente sobre a topologia aprovada no Comp C.

---

## 1. Visão Geral e Arquitetura

O frontend opera integrado diretamente ao backend FastAPI no mesmo endereço, sem necessidade de configuração manual de chaves de API pelo usuário no navegador:
- **Sessão Automática Same-Origin (`GET /app/session`):** Inicialização transparente com cookies `HttpOnly` `SameSite=Strict` assinados no servidor. Nenhuma chave mestra ou segredo de aplicação é exigido ou exposto no cliente.
- **Preferências de Investigação Dinâmicas (`+`):** Painel acessível ao lado do compositor para seleção de 1 a 20 pontos analíticos estruturados e subconjunto de personas especializadas de busca web (Historiador, Visionário, Cético, Futurista).
- **Planejamento (`POST /api/v1/plan`):** Formulação de eixos investigativos estruturados com hipóteses falseáveis, consultas canônicas e critérios de conclusão. Não executa buscas automaticamente.
- **Divulgação Progressiva:** Planos com múltiplos pontos investigativos utilizam acordeão para manter o botão `Iniciar pesquisa` visível e acessível imediatamente, sem exigir rolagem excessiva.
- **Transição com Ação Única:** O plano é exibido com o botão exclusivo `Iniciar pesquisa`.
- **Execução Síncrona (`POST /api/v1/search` → `POST /api/v1/audit` → `POST /api/v1/writer`):**
  - Varredura web com as personas analíticas selecionadas e snapshot imutável por pesquisa.
  - Auditoria cumulativa frente às 12 perguntas de qualidade (limiar de corte 11/12).
  - Bloqueio estrito da redação se os pontos não forem aprovados na auditoria após as tentativas.
  - Redação do dossiê em Markdown sanitizado com lista de fontes canônicas verificadas. Foco automático no topo do dossiê ao concluir.
- **Configurações e Segurança de Provedores:**
  - Cadastro de credenciais de provedores externos (OpenAI, Jina, Webhooks) com cifra Fernet (AES-128-CBC + HMAC-SHA256) em repouso no servidor.
  - Apresentação clara de metadados mascarados e respeito à regra de precedência **RN-10** (banco cifrado sobrepõe `.env`; Adendo 002).
  - Proteção contra perda acidental de rascunhos no formulário de configurações.
- **Histórico Local:** Persistência no navegador de pesquisas concluídas para consulta instantânea sem reprocessamento e sem vazamento de raciocínio interno.

---

## 2. Comandos de Execução

Dentro do diretório `frontend/`:

### Instalação de Dependências
```bash
npm install
```

### Modo de Desenvolvimento (Vite Dev Server)
Por padrão, o proxy redireciona chamadas `/app`, `/api` e `/health` com `changeOrigin: false` para o backend em `http://127.0.0.1:8010`:
```bash
npm run dev
```

### Compilação de Produção e Typecheck
```bash
npm run build
```
Executa `tsc` para verificação rigorosa de tipos e gera os assets otimizados em `dist/`.

### Pré-visualização do Bundle de Produção
```bash
npm run preview
```

---

## 3. Notas de Proxy e Produção

- **Ambiente de Desenvolvimento:** O arquivo `vite.config.ts` configura proxy com `changeOrigin: false` preservando o Host para `/app`, `/api` e `/health` em `127.0.0.1:8010`, garantindo a validação de mesma origem contra ataques CSRF.
- **Ambiente de Produção:** O bundle estático compilado em `dist/` é servido nativamente pelo FastAPI através de rotas dedicadas (`/`, `/assets/*`), garantindo operação same-origin estrita e zero dependência de Node.js em produção.
- **Segurança de Credenciais:** Nenhuma chave mestra ou segredo de provedor (.env) é exposto ou embutido no código cliente.

---

## 4. Escopo do Checkpoint 1 vs Checkpoint 2

| Recurso | Checkpoint 1 (Entregue) | Checkpoint 2 (Implementado) |
| :--- | :--- | :--- |
| **Execução da Pesquisa** | Síncrona com estados reais (`Search` → `Audit` → `Writer`) | Streaming em tempo real via Server-Sent Events (SSE) |
| **Tokens e Atividade do Modelo** | Renderização após conclusão de cada etapa | Streaming de tokens do LLM via `agent.delta` com reconexão por snapshot |
| **Dossiê Final** | Markdown sanitizado, exportação `.md` e cópia | Entrega após eventos de busca e auditoria |
| **Autenticação** | Sessão automática via cookie HttpOnly SameSite=Strict | Preserva a sessão existente |
