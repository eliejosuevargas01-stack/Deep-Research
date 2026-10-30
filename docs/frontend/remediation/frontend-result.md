# Relatório de Remediação do Frontend — Checkpoint 1

## 1. Arquivos Modificados e Entregues

A remediação corretiva completa do frontend foi implementada nos arquivos autorizados sob `frontend/**`, `DESIGN.md`, `.impeccable/**` e relatórios de acompanhamento sob `docs/frontend/remediation/`:

### Componentes e Aplicação
- `frontend/src/App.tsx`:
  - Sessão integrada automática via `GET /app/session` iniciada em estado não autenticado (`false`).
  - Bloqueio de submissão do compositor durante bootstrapping (`isBootstrapping`) ou em caso de erro de sessão (`sessionBootstrapError`).
  - Preservação estrita de preferências manuais do usuário sem sobreposição indevida por novas leituras de sessão.
  - Limpeza do campo do compositor **somente após a formulação bem-sucedida do plano**, evitando concorrência com o botão `Iniciar pesquisa` ou envios duplicados; em caso de erro de validação/servidor, o texto do tema é preservado intacto.
  - Ação `handleEditTheme` integrada ao banner do plano para permitir resgatar o tema no compositor com foco e rolagem imediata.
  - Chamada à busca (`api.searchPoints`) utilizando estritamente o snapshot imutável gravado no plano (`currentPlan.preferencias?.personas`); caso o plano seja legado (sem snapshot), passa `undefined` para que o backend utilize seu padrão ou snapshot próprio persistido no banco, **nunca fazendo fallback para as escolhas atuais do compositor**.
  - Recuperação sensível ao estágio (`handleRetryExecution`): se a auditoria já estiver aprovada e a falha tiver ocorrido apenas no redator, aciona diretamente a retentativa de redação (`handleRetryWriter`) sem reexecutar a busca; se a falha for na busca ou auditoria, reinicia o fluxo a partir da busca mantendo o plano e preferências.
  - Passagem de `plan={currentPlan}`, `onRetry={handleRetryExecution}` e `onEditTheme={handleEditTheme}`.
- `frontend/src/components/Composer.tsx`:
  - Barra de ferramentas integrada ao botão expansível `+` de preferências de pesquisa.
  - Texto de ajuda permanente com tamanho legível `>= 13px` (`0.88rem`), contraste adequado e instruções dinâmicas exatas:
    - Vazio: "Mínimo de 5 e máximo de 500 caracteres para formular o tema."
    - Comprimento < 5: "Faltam X caracteres para atingir o mínimo de 5."
    - Comprimento > 500: "Tema excede o limite em X caracteres (máximo 500). Reduza o texto para continuar."
    - Válido: "Tema com comprimento válido (pressione Enter para formular o plano de investigação)."
  - Remoção de `maxLength={600}` restritivo, preservando texto colado em excesso para edição e correção pelo usuário sem truncamento silencioso.
  - Apenas um controle primário de envio (`.composer-send-btn`) sem duplicidade de CTAs concorrentes.
- `frontend/src/components/ResearchPreferences.tsx`:
  - Popover expansível não modal (`role="region"`) adjacente ao compositor, com abertura/fechamento acessível.
  - Delimitação pelo viewport com `max-height: min(80vh, 520px); overflow-y: auto;` e cabeçalho fixo (`position: sticky; top: 0`), garantindo que o botão fechar esteja sempre visível e alcançável em telas curtas ou modo paisagem móvel.
  - Seletor de pontos analíticos com presets de 1 a 5 e entrada numérica direta para suporte a até 20 pontos.
  - Checklist de personas com descrições associadas (`aria-describedby`) e trava de segurança que impede desmarcar a última persona restante.
  - Navegação por teclado nos botões de preset (ArrowLeft/ArrowRight) e tecla Escape com restauração imediata do foco no botão `+`.
  - Animação GSAP estabilizada executada estritamente na montagem, eliminando reinicializações indevidas a cada clique interno.
- `frontend/src/components/Navbar.tsx`:
  - Alinhamento à identidade visual DominusLabs (`brand-link` com destaque em violeta `#6D28D9`).
  - Indicador de status de sessão integrado (pill verde para modo local/conectado, pill violeta durante bootstrapping, pill âmbar para sessão pendente).
  - Remoção completa de badges de chave de API em memória.
  - Ponto de quebra estendido para `max-width: 992px`, eliminando a colisão observada em 916px entre o link de documentação e o badge, além de suportar zoom de 200% sem sobreposições.
- `frontend/src/components/SettingsView.tsx`:
  - Remoção absoluta de campos de `API_SECRET_KEY` manual, chave em memória e configurações de chave externa.
  - Gestão exclusiva dos parâmetros de provedores reais (`OPENAI_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_LIGHT`, `LLM_MODEL_STRONG`, `JINA_API_KEY`, `JINA_BASE_URL`, `N_PONTOS`, `PERSONAS_CONFIG`, `CALLBACK_WEBHOOK_URL`, `WEBHOOK_HMAC_SECRET`).
  - Validação acessível com atributos `aria-invalid` e `aria-describedby`.
  - Proteção contra perda involuntária de rascunhos de configurações digitados (`beforeunload` e alerta visual).
  - Diferenciação honesta entre ausência de parâmetros customizados e falha de rede/requisição com botão de retry.
- `frontend/src/components/PlanView.tsx`:
  - Revisão compacta inicial para qualquer contagem de pontos (inclusive N=1 e N=2 extensos): todos os pontos iniciam colapsados por padrão, permitindo que a visão geral e a única ação `Iniciar pesquisa` estejam imediatamente visíveis no viewport (incluindo 1280x720 e mobile), sem necessidade de rolagem excessiva.
  - Botão global de alternância para expandir/recolher todos os detalhes dos pontos, além de botão individual por ponto.
  - Botão "Editar tema" adicionado ao banner do plano.
  - Chips de snapshot indicando a quantidade de pontos e personas gravadas para o plano.
- `frontend/src/components/ExecutionView.tsx`:
  - Status e rótulos de personas fidedignos baseados no plano recebido: reflete dinamicamente a contagem e os nomes das personas selecionadas ("Varredura web em andamento com 2 personas analíticas (Historiador, Cético)..."), sem inventar contagem de 4 para planos legados.
  - Detecção e exibição tipada de erros (Timeout 504, erro de provedor 502/LLM, etc.) com orientações claras.
  - Botão de retentativa sensível ao estágio (`onRetry`): retenta o redator diretamente se a auditoria já tiver sido aprovada, ou retenta a busca/auditoria se a falha for na coleta.
- `frontend/src/components/ReportView.tsx`:
  - Rolagem automática suave para o topo do dossiê final e foco no container ao concluir a redação.
  - Feedback visual e acessível (`aria-live="polite"`) nos botões de cópia e download de Markdown.
  - Validação estrita de protocolos seguros (`http`, `https`, `mailto`) em links Markdown.
- `frontend/src/components/EmptyState.tsx`:
  - Redação conversacional, direta e task-first ("O que você deseja investigar hoje?").
  - Substituição da grade de botões com semântica incorreta (`role="listitem"`) por estrutura semântica padrão `ul > li > button`.
  - Foco transferido automaticamente para o editor ao clicar em qualquer sugestão.
- `frontend/src/components/DocsView.tsx`:
  - Atualização da documentação operacional explicando a autenticação transparente via cookies HttpOnly SameSite=Strict e o uso externo de `X-API-Key`.

### Serviços e Tipos
- `frontend/src/services/history.ts`:
  - `sanitizeRecord` atualizado para **preservar o snapshot público validado de `preferencias: { n_pontos, personas }`**, eliminando o bug de descarte de preferências na restauração do histórico.
  - Isolamento estrito de reasoning interno, metadados privados e envelopes de chamada.
- `frontend/src/services/api.ts`:
  - Requisições configuradas com `credentials: 'same-origin'`.
  - Remoção completa de `inMemoryApiKey`, `setApiKey`, `getApiKey` e injeção de `X-API-Key`.
  - Endpoint `getSession` para consulta a `/app/session`.
  - Assinatura de `createPlan` suportando parâmetros opcionais `n_pontos` e `personas`.
- `frontend/src/types/api.ts`:
  - Definições de `SessionResponse`, `SessionPreferences`, `PlanPreferencias` e extensões de `PlanRequest`/`PlanResponse`.

### Estilos e Design System
- `frontend/src/styles/tokens.css`:
  - Adoção integral dos tokens oficiais da DominusLabs (`violet: #6D28D9`, `violet-2: #7C3AED`, `violet-tint: #F5F0FF`, `violet-line: #DDD6FE`, `indigo: #4F46E5`, `navy: #1E1B4B`, `bg: #F9FAFB`).
  - Fontes: `Outfit` (display), `Inter` (sans), `JetBrains Mono` (código/dados).
- `frontend/src/styles/main.css`:
  - Auto-hospedagem de fontes via pacotes `@fontsource/outfit`, `@fontsource/inter`, `@fontsource/jetbrains-mono`.
  - Adaptação estrita para `prefers-reduced-motion: reduce`.
- `frontend/src/styles/components.css`:
  - Classes `.pill`, `.pill-green`, `.pill-violet`, `.pill-indigo`, `.pill-amber` idênticas às referências da DominusLabs.
  - Alvos de toque com no mínimo 40px/44px de altura em todos os controles interativos.
  - Breakpoint do navbar ajustado para `max-width: 992px` (eliminando colisão de 916px).
  - Grade de sugestões `.sample-topics-grid` ajustada para 1 coluna em telas `<= 768px`.
  - Painel de preferências `.preferences-panel` com rolagem interna delimitada (`max-height: min(80vh, 520px)`) e cabeçalho fixo.
  - Texto de ajuda do compositor `.composer-helper-text` com `0.88rem` (13.2px) e contraste reforçado.
- `DESIGN.md`: Atualizado com a especificação canônica da identidade DominusLabs e tese de movimento.
- `.impeccable/surface-brief.md`: Atualizado refletindo a resolução das críticas da Rodada 1 e a direção estética corrigida.

### Configuração e Testes
- `frontend/vite.config.ts`:
  - Proxy para `/app`, `/api` e `/health` configurado com `changeOrigin: false` em `server` e `preview`, preservando o cabeçalho Host da origem real para validação CSRF no backend.
- `frontend/features/01_research_workspace.feature`:
  - Cenários para visualização compacta inicial de planos extensos de 2 pontos com botão Iniciar imediatamente visível; limpeza do compositor pós-plano e ação "Editar tema"; responsividade em 916px, 837px e 375px (1 coluna de sugestões).
- `frontend/features/02_audit_gating_and_failures.feature`:
  - Cenário de tratamento de erro e retentativa sensível ao estágio após timeout de busca.
- `frontend/features/04_history_and_persistence.feature`:
  - Cenário de preservação de snapshot de preferências (`n_pontos` e `personas`) no histórico local.
- `frontend/features/step_definitions/steps.ts`:
  - Implementação completa dos passos correspondentes sem injeção de credenciais no cliente.

---

## 2. Comparativo com a Referência DominusLabs Docs

| Elemento | Referência DominusLabs (`docs.css` / `extra.css`) | Implementação Deep Research |
| :--- | :--- | :--- |
| **Cor Primária** | Violeta `#6D28D9` / `#7C3AED` | Ações principais, botão enviar, início de pesquisa, focus ring |
| **Superfície e Canvas** | Canvas `#F9FAFB`, cards `#FFFFFF`, bordas `#E5E7EB` | Mapeado diretamente em `--bg`, `--surface`, `--border` |
| **Acentos e Tints** | `#F5F0FF` (tint), `#DDD6FE` (line) | Estados hover, itens ativos de navegação, chips selecionados |
| **Pills de Status** | `.pill-green`, `.pill-violet`, `.pill-amber`, `.dot` | Status de sessão integrada, contagem de pontos e personas |
| **Tipografia** | Outfit (display) + Inter (sans) + JetBrains Mono | Auto-hospedado via fontsource, aplicado em títulos, corpo e tags |
| **Controle de Código/Tags** | Fundo `#F5F0FF`, texto `#5B21B6`, JetBrains Mono | Tags de fontes e identificadores de ponto formatados |

---

## 3. Tese de Movimento (Motion Thesis)

1. **Momento Focal (Focal Moment):**
   - A submissão do tema transiciona para a visualização do plano estruturado através de uma entrada suave (`0.35s`, `power2.out`, deslocamento vertical de 16px).
2. **Continuidade (Continuity):**
   - A transição do plano de investigação para os estágios de execução síncrona (busca, auditoria, redação) utiliza uma pulsação sutil de opacidade (`0.15s`), mantendo o usuário orientado sem saltos desorientadores no canvas.
3. **Feedback e Controle:**
   - O popover de preferências (`+`) e o acordeão de pontos reagem com transições suaves (`0.2s`), contidos estritamente em suas regiões limítrofes.
4. **Orçamento e Acessibilidade (Budget & Accessibility):**
   - Em conformidade estrita com `prefers-reduced-motion: reduce`, todos os deslocamentos espaciais (`y: 16`, `scale: 0.98`) são cancelados, preservando transições instantâneas de estado e mudanças discretas de cor/opacidade.
   - Tweens do GSAP são devidamente destruídos (`killTweensOf`) no desmonte de componentes. Não existem loops decorativos perpétuos nem conteúdo dependente de execução de JS para ser exibido.

---

## 4. Resolução dos 6 Itens da Crítica Rodada 1

1. **Responsividade e Espaço Vertical:**
   - Sugestões em 1 coluna em telas `<= 768px`.
   - Popover de preferências delimitado por `max-height: min(80vh, 520px); overflow-y: auto;` com cabeçalho e botão fechar fixos.
   - Breakpoint do navbar em `992px` eliminando colisão de 916px e suportando zoom de 200%.
2. **Texto de Entrada, Ajuda e Validação:**
   - Texto de abertura conversacional e task-first ("O que você deseja investigar hoje?").
   - Texto de ajuda permanente com `0.88rem` (13.2px) e mensagens dinâmicas exatas de contagem.
   - Preservação de texto longo colado sem truncamento silencioso.
3. **Preservação de Snapshot de Preferências no Histórico:**
   - `historyService` agora projeta e armazena `preferencias: { n_pontos, personas }`.
   - Ao iniciar/reexecutar pesquisas reabertas, utiliza o snapshot gravado no plano sem contaminar ou substituir pelas seleções atuais do compositor.
   - Planos legados sem snapshot passam `undefined`, permitindo que o backend utilize seu padrão ou snapshot no banco.
4. **Status e Rótulos Fidedignos de Personas na Execução:**
   - `ExecutionView` reflete a quantidade real de personas e seus nomes configurados no plano, sem fixar 4 nem inventar personas não selecionadas.
5. **Revisão Compacta Inicial e Continuidade Imediata:**
   - Todos os pontos investigativos iniciam colapsados por padrão (mesmo em planos de 1 ou 2 pontos com textos extensos), garantindo que a única ação `Iniciar pesquisa` esteja imediatamente visível no viewport (incluindo 1280x720 e mobile).
   - Botão "Editar tema" para recuperar o texto no compositor.
   - Compositor limpo apenas após criação bem-sucedida do plano, evitando concorrência com o botão Iniciar.
6. **Recuperação Sensível ao Estágio (Stage-Aware Retry):**
   - Tratamento explícito de timeout (504), erro de provedor (502) e falhas parciais.
   - Retentativa contextual: retenta somente o redator se a auditoria já tiver aprovado, ou retenta a busca/auditoria se a falha for na coleta, preservando o plano e preferências.

---

## 5. Limitações Conhecidas e Próximos Passos

- **Verificação End-to-End:** Conforme diretiva operacional da orquestração, a suíte visual completa de Cucumber será executada após a homologação independente do Auditor Hermes.
- **Compilação e Verificação Estática:**
  - `npx tsc --noEmit`: 0 erros.
  - `npm run build`: compilado com sucesso gerando bundle de produção limpo em `frontend/dist/`.
  - Testes de integração backend (`test_web_app.py`, `test_research_preferences.py`): 35/35 aprovados.
