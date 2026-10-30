# Auditoria Independente de Pré-Voo (Fase 1) — Deep Research Workspace

> **Status:** Avaliação Preliminar Concluída (Não é Aprovação Final de Release)  
> **Disposição:** `preliminary_pending_round5_and_QA`  
> **Árbitro:** Hermes Quality Arbitrator Independente  
> **Modelo:** `ag/gemini-3.8-flash-high` | **Reasoning:** `high` | **Provedor:** `custom (provider9router)`  
> **Perfil:** `critique-native`  
> **Timestamp UTC:** `2026-10-27T00:40:16Z`  
> **Arquivo de Dados Estruturado:** `docs/frontend/remediation/audit-preflight-r1.json`

---

## 1. Escopo e Mandato da Fase 1

Esta auditoria de pré-voo constitui a **Fase 1 (Read-Only)** de verificação independente da arquitetura de backend, integridade de segurança, conformidade normativa, implementação do frontend e prontidão dos testes automatizados.

Conforme as diretrizes normativas vigentes:
1. **Não é aprovação final de release**: A aprovação para o teste visual final de aceitação (G04 / Cucumber) está condicionada à conclusão da Rodada 5 de crítica visual e à finalização das correções da suíte de testes de QA.
2. **Sem subagentes nativos ou modelos substitutos**: Avaliação executada com rigor no modelo e raciocínio solicitados.
3. **Imutabilidade**: Nenhum arquivo de produção, teste existente, evidência legada ou variáveis de ambiente foi modificado durante este processo.

---

## 2. Resumo da Avaliação dos Critérios (C01–C09, G01–G06 e S01)

| Critério | Descrição Resumida | Situação | Evidência Principal / Justificativa |
|---|---|:---:|---|
| **C01** | Frontend e backend servidos juntos sem API_SECRET_KEY na UI | **PASS** | `app/main.py` serve `frontend/dist`. Assets confinados; arquivos inexistentes retornam 404 estrito. Cookie `dr_local_session` HttpOnly emitido automaticamente para loopback. |
| **C02** | Comunicação real frontend/backend no endereço entregue | **UNPROVEN** | Comunicação real comprovada em `http://127.0.0.1:3002/`. Execução de 2 pontos gerou timeout 504 no provedor; relatório real `dee9fa33-1205-4323-8715-ab388deb8747` comprova redação sem re-execução paga. Prova visual integrada pendente da Rodada 5. |
| **C03** | Testes cobrem o caminho de uso efetivo | **UNPROVEN** | 422 testes de backend aprovados; 13 testes de fontes aprovados. Suíte Cucumber (G04) contém lacunas ativas sob correção no pacote de prontidão de QA. |
| **C04** | Payloads reais e preferências aplicadas | **UNPROVEN** | Requisições reais em `live-payloads.jsonl` refletem `n_pontos` e personas. Gates de backend rejeitam não selecionadas. Conclusão da execução com 2/2 personas ativas pendente da Rodada 5. |
| **C05** | Botão `+` expansível no compositor | **PASS** | Painel `ResearchPreferences` funcional, com limites respeitados e persistência de snapshot no histórico corrigida em `App.tsx` e `history.ts`. |
| **C06** | Animações perceptíveis e coerentes | **UNPROVEN** | Transições GSAP implementadas e com fallback em `prefers-reduced-motion`. Validação visual nativa de frames na Rodada 5 pendente. |
| **C07** | Cor marcante coerente com referência aprovada | **PASS** | Paleta Dominus Violet (`#6D28D9` / `#7C3AED`), Indigo e Navy com superfícies claras. Documentação original em `docs-src/assets/docs.css` preservada. (Apontado P2 sobre contraste de notas explicativas). |
| **C08** | Fidelidade a DominusLabs e documentação da API | **PASS** | Tokens tipográficos (Outfit, Inter, JetBrains Mono) auto-hospedados no bundle Vite. Topologia Comp C preservada com canvas central e barra lateral. |
| **C09** | Qualidade de chat e experiência integrada | **UNPROVEN** | Sugestões semânticas, compositor responsivo e validação estrita de fontes. Apontados 2 problemas de usabilidade/cópia honesta no `PlanView` e no `App.tsx`. |
| **G01** | Preferências globais e credenciais editáveis (Adendo 002) | **PASS** | Precedência Banco Cifrado > Ambiente implementada em `credentials_repository.py` e `credential_resolver.py`. `CREDENTIALS_MASTER_KEY` estritamente no ambiente. Foco no primeiro campo inválido em `SettingsView`. |
| **G02** | Fluxo Tema -> Plano -> Iniciar -> Relatório real sem SSE falso | **PASS** | Execução síncrona real sem simulação de pensamento do Checkpoint 2. Relatório real com 9.352 caracteres gravado no banco de dados. |
| **G03** | Aprovação por auditor Hermes independente | **UNPROVEN** | Fase 1 preliminar concluída; parecer final aguarda correções de P1 e conclusão da Rodada 5. |
| **G04** | Cucumber visual Gherkin pós-aprovação | **pending_post_approval** | Gate de release agendado após aprovação da auditoria. Comando requerido: `npm --prefix frontend run test:e2e` (ou `npx cucumber-js`). |
| **G05** | Cinco rodadas Impeccable na aplicação corrigida | **UNPROVEN** | Rodadas 1 a 4 executadas. Rodada 5 de captura visual e crítica A/B em andamento. |
| **G06** | Build e execução em comando único documentado | **PASS** | `npm --prefix frontend run build` e execução pelo FastAPI com confinamento seguro de estáticos. Nenhuma chave manual exigida do usuário. |
| **S01** | Separação contábil e rastreabilidade tripartite de fontes | **PASS** | Modelo tripartite (consultadas, utilizadas, não citadas) implementado. Consulta GET protegida no relatório real retornou 11/9/2 com validação estrita de hash e zero chamadas a modelos. |

---

## 3. Verificação de Segurança e Fronteiras de Sessão

### 3.1. Confronto com `preintegration-security-observations.json`

As cinco vulnerabilidades e anomalias de fronteira levantadas na inspeção pré-integração foram examinadas no código-fonte final de `app/ui_session.py`:

1. **Rejeição de Portas Divergentes (Different port origin):**  
   *Situação:* **CORRIGIDO.**  
   *Mecanismo:* A função `get_request_origin` (`app/ui_session.py:88-117`) inclui explicitamente a porta na origem canônica esperada. `_canonical_origin` compara scheme e netloc completos; qualquer porta não idêntica invalida a requisição com `canon_origin != expected_origin`.
2. **Obrigatoriedade de Origin/Referer em Requisições Mutantes (CSRF):**  
   *Situação:* **CORRIGIDO.**  
   *Mecanismo:* Em `app/ui_session.py:270-274`, métodos mutantes (`POST`, `PUT`, `DELETE`, `PATCH`) exigem estritamente `Origin` ou `Referer`. A ausência de ambos retorna `False` imediatamente.
3. **Rejeição de Esquema Divergente (Different scheme origin):**  
   *Situação:* **CORRIGIDO.**  
   *Mecanismo:* `_canonical_origin` valida o esquema (`http` vs `https`) confrontando com o esquema canônico da requisição.
4. **Rejeição de Hostnames com Prefixo 127 Malicioso (Untrusted 127-prefix hostname):**  
   *Situação:* **CORRIGIDO.**  
   *Mecanismo:* A função `_is_local_host` (`app/ui_session.py:63-86`) restringe nomes a `ALLOWED_LOCAL_HOSTNAMES` (`localhost`, `127.0.0.1`, `::1`) ou validação estrita via `ipaddress.ip_address(raw_host).is_loopback`. Nomes como `127.example.com` disparam `ValueError` e são rejeitados com `False`.
5. **Tratamento de Cookie com Unicode Malformado sem Exceção (Malformed Unicode cookie):**  
   *Situação:* **CORRIGIDO.**  
   *Mecanismo:* Em `verify_session_token` (`app/ui_session.py:204-210`), os segmentos Base64 passam por validação ASCII estrita com tratamento explícito de `UnicodeEncodeError`, retornando `False` de forma segura sem lançar exceções 500.

### 3.2. Servimento de Estáticos e Prevenção de Path Traversal

Em `app/main.py:150-205`:
- O diretório de estáticos `FRONTEND_DIST_DIR / "assets"` resolve o caminho absoluto e valida com `requested_file.relative_to(assets_dir)`.
- Arquivos estáticos inexistentes (com extensão de arquivo) retornam `HTTP 404 Not Found` em vez de cair na rota catch-all que serve o `index.html` da SPA (`app/main.py:180-190`).
- Rotas reservadas (`/api/*`, `/health`, `/docs*`, `/openapi.json`, `/app/session`) estão protegidas do fallback da SPA.

---

## 4. Conformidade Normativa com o Adendo 002

O repositório e os serviços foram verificados quanto à inversão normativa de precedência de credenciais:
- **Prioridade 1 (Banco Cifrado):** `app/db/credentials_repository.py:25-37` consulta prioritariamente a tabela `credenciais` e decifra o valor com `CryptoService`.
- **Prioridade 2 (Fallback no Ambiente):** Linhas 39-42 recorrem a `os.environ.get(chave)` caso o registro não exista ou esteja vazio no banco.
- **Exceção de Bootstrap (`CREDENTIALS_MASTER_KEY`):** Restrita estritamente às variáveis de ambiente do sistema operacional em `app/services/crypto_service.py:16-23`.
- **Ausência em Ambas as Camadas:** Lança expressamente `ValueError` conforme RN-02, sem valores hardcoded.
- **Frontend / SettingsView:** Mensagem explicativa da RN-10 atualizada para informar a precedência `Banco Cifrado > Ambiente`.

---

## 5. Auditoria de Código e Apontamentos Concretos (P1–P3)

Durante a inspeção minuciosa dos componentes de interface e automação de testes, foram registrados os seguintes achados que impedem a aprovação imediata:

### 5.1. [P1] Ausência de Gestão de Foco e Escape no AlertDialog de Plano
- **Localização:** `frontend/src/components/PlanView.tsx:93-121`
- **Categoria:** Acessibilidade / Navegação por Teclado (WCAG 2.1)
- **Diagnóstico:** O elemento inline `div.query-confirm-reset` possui `role="alertdialog"` e `aria-labelledby="confirm-reset-title"`, mas:
  1. Não move o foco automaticamente para o botão de cancelamento ou para o container ao ser exibido.
  2. Não possui ouvinte de evento `onKeyDown` para fechar a caixa de diálogo ao pressionar a tecla `Escape`.
  3. Ao ser fechado via clique em "Cancelar", não devolve o foco ao botão disparador (`Novo tema`).
- **Ação Requerida:** Adicionar listener de teclado para `Escape`, capturar/gerenciar foco inicial e restaurar foco no elemento acionador ao cancelar.

### 5.2. [P1] Cópia Enganosa na Confirmação de Troca de Pesquisa no Histórico
- **Localização:** `frontend/src/App.tsx:437`
- **Categoria:** Fidedignidade de Estado (Truthful UI)
- **Diagnóstico:** Ao carregar um registro histórico com execução ativa, o código executa:
  ```ts
  if (!window.confirm('Existe uma pesquisa em andamento. Deseja interromper e abrir esta pesquisa?')) return;
  ```
  O termo "interromper" induz o usuário ao erro, pois o backend FastAPI executa o pipeline síncrono de busca e escrita sem suporte a cancelamento remoto via navegador. A tarefa continuará consumindo recursos no servidor em segundo plano.
- **Ação Requerida:** Ajustar o texto da confirmação com transparência técnica:
  `"Existe uma pesquisa sendo executada no servidor. Deseja mudar a visualização para este histórico? (Atenção: a execução no servidor continuará em segundo plano)"`.

### 5.3. [P1] Lacunas de Asserção e Seletor na Suíte Cucumber de Fontes (QA)
- **Localização:** `frontend/features/step_definitions/steps.ts:1949, 1982-1987` e `frontend/features/support/world.ts:102-116`
- **Categoria:** Garantia de Qualidade e Integridade de Testes
- **Diagnóstico:** O pacote de revisão `.impeccable/remediation-20261026/qa-readiness-root-review.md` identificou defeitos críticos nos passos de teste:
  1. No passo de validação de hash (`steps.ts:1982-1987`), a asserção apenas confere se o badge contém o texto `'Evidências completas'`, sem comparar o hash SHA-256 criptográfico real com o artefato publicado.
  2. O seletor em `steps.ts:1949` procura `.history-item-card`, enquanto a classe real gerada por `HistoryView.tsx` é `.history-card`.
  3. A guarda de segurança de requisições mutantes no `world.ts:102-116` monitorava eventos `on('request')` (disparados quando a requisição já foi enviada) em vez de aplicar interceptação prévia com `context.route` para abortar qualquer `POST`.
- **Ação Requerida:** Aguardar a aplicação completa das correções preparadas pelo responsável de QA antes de liberar o Gate G04.

### 5.4. [P2] Contraste Marginal no Texto de Apoio de Fontes
- **Localização:** `frontend/src/components/SourceBreakdown.css:125-130`
- **Categoria:** Acessibilidade / Contraste de Cores (WCAG AA)
- **Diagnóstico:** A classe `.source-explanation-note` utiliza `color: var(--color-text-muted, #6b7280)` em tamanho `0.82rem` (~13.1px).
  - Em fundo branco (`#FFFFFF`): contraste de 4.76:1 (aprovado no limite mínimo de 4.5:1).
  - Em fundo sutil (`#F3F4F6`): contraste de **4.32:1**, reprovado pelo critério WCAG AA para textos normais.
- **Ação Requerida:** Atualizar a cor para `var(--color-text-secondary, #374151)`, alcançando contraste robusto de 8.8:1 sobre branco e 8.0:1 sobre superfícies cinzas.

### 5.5. [P2] Conclusão da Rodada 5 de Crítica Visual Pendente
- **Localização:** `docs/frontend/remediation/critiques/round-5/`
- **Categoria:** Evidência Visual Nativa
- **Diagnóstico:** As capturas de tela finais em viewports de 375px, 837px e 1440px com o modelo nativo Gemini 3.8 Flash High estão em processo de finalização.

### 5.6. [P3] Estilos Inline em `SourceBreakdown.tsx`
- **Localização:** `frontend/src/components/SourceBreakdown.tsx:88, 161, 269, 293`
- **Categoria:** Manutenibilidade e Consistência de CSS
- **Diagnóstico:** Propriedades pontuais de flexbox e cores declaradas em inline style podem ser extraídas para `SourceBreakdown.css`.

---

## 6. Hashes Criptográficos dos Artefatos de Produção e Referência

### Backend (Python/FastAPI)
- `app/main.py`: `5dec5025cacca8cf3ef28a7041d8b2fc4d0e23a232902d9118b700b8f268924f`
- `app/ui_session.py`: `d1e38511c08355522671e0e53fc711ca3a17fc7f0147f70dfa60af8f98f19a6a`
- `app/core/security.py`: `f39a7eccf0339a66ae971803509dbb6f83934874137acb92722ea1190c9e97c7`
- `app/core/planner.py`: `01399c807a8377a07559e26515f0ab2edf780db6dc61f30e4848f97069b11363`
- `app/core/searcher.py`: `389a00d3ace9fc08792e7d098a4c7fd6642263ccdd4b3814addaffb2fb78e939`
- `app/core/auditor.py`: `2defde70a9bac56f36040b6a70fcc833090398001b7ccd37ae50894ce95bb819`
- `app/core/writer.py`: `e441fb2e1c1e2ac1fa9b8585f16a68013d3901bdec6cff23c1604beb9da4f7b3`
- `app/core/personas.py`: `832e7ee75a5b514d10daf798974d9441caba5cd96cee2371c897fed42162c498`
- `app/core/plan_validator.py`: `1ce6b710db54705d69bacc530a1a87a0623e6726e601d76b2a3585455202934d`
- `app/core/pipeline_runner.py`: `985a8797b79d5766c86bd7c154cf0c12e0c2135259de29ebd14a5fcff9675c6c`
- `app/db/credentials_repository.py`: `723b70cd2e2c0a5ac544336af0791a0d745118c49fc47cd95593151996efbf2f`
- `app/db/research_repository.py`: `7f878a01dda4a4e6e9d1be8c86469fc13f6ea1f97ac4ef47434f648323a64ae9`
- `app/services/credential_resolver.py`: `d6c87d217758433e208dbecf7e3c9e0a1f4953dd7011e149d74c6ecba1a299d1`
- `app/services/source_accounting_service.py`: `2f2452045a2436fb0ac939867b793ac1118eb1c15c780422e3a0cbb5d6dea323`
- `app/schemas/sources.py`: `ad8a061ac8d511958bf27a9e5c5b9409fffcfef575b790f4edcb3634fdeed0b9`
- `app/schemas/plan.py`: `157c714bc3caf223e1135620cda1307b2f76c413f9704d40a8ea93f5138f5c18`
- `app/schemas/search.py`: `5db87b23efe5bdd125ed9b95f396a0b1910710441ce9f35e225ddc874dac6c8b`
- `app/schemas/audit.py`: `db1e5f88847fffdc57adab7c9bec42723d2f181c21890f9b2c6a63750f383e25`
- `app/schemas/writer.py`: `7b0f771ab8d5c981de1a8a52ddf5030b588fd380b7bd6186ce62803f45dce1d0`

### Frontend (Código-fonte TypeScript e Estilos)
- `frontend/src/App.tsx`: `22ba2040d5b609110611c6749aad99b4cf18954d56ac536b0097fb4551c6633e`
- `frontend/src/components/Composer.tsx`: `0d58214a3904faab35b3d523c49223b6881c25c4cc2bcfab6c3e100ec63ece98`
- `frontend/src/components/PlanView.tsx`: `1d1a177b69532ac08e84475979837a61ba1315fa6d86d5f7dcca9414f7d98957`
- `frontend/src/components/ExecutionView.tsx`: `0e8dbbad51d8b93feed301dc30385c7f16e4004ba9b4a09b9097c8e615343d0e`
- `frontend/src/components/ReportView.tsx`: `c04dbaa5fcd1118b82e551b57e3fbeae19e6b182d0d7d3c5648f07fcb2c9e4ed`
- `frontend/src/components/SourceBreakdown.tsx`: `254e96e2961d4961c83fa9ad85e9435923d093f8344e1436c471d524e3cff194`
- `frontend/src/components/SourceBreakdown.css`: `48a928380eed00f1246afd87dc25dad968fe7847c5454683ad93304dde65fde8`
- `frontend/src/components/HistoryView.tsx`: `4fdf35b2546b255d18e6f440b6de50c72ff249a4f4e93057f9b52c48c84da356`
- `frontend/src/components/SettingsView.tsx`: `7b6a7082a1c6b2bcfe2f6a78d33d66d3b37e891d0ef12c2cd9b27ef4c8b3b207`
- `frontend/src/components/DocsView.tsx`: `4fa7b5a2a74960d082576742613b800ddfb30b388e3e552a6bbc568a20d552ba`
- `frontend/src/components/ResearchPreferences.tsx`: `4e0d5a696bda24d76335ff4c7497090167484d9d3ce194d50f51994d25f4c105`
- `frontend/src/services/api.ts`: `4c50d977652fb19f0552b3035350759e2aae1102e2670c7851b679a699906b20`
- `frontend/src/services/history.ts`: `a9dd3f3a01a0d531f631e2582885cc913c83061e4f3f5d702ce169f5a5dc6235`
- `frontend/src/types/api.ts`: `cf555a8fbecc904da53f0d6b284aea230334bf65c2287d502bffe0393792f653`
- `frontend/src/styles/tokens.css`: `a2c6b1de2fbcb84a9ac4e3166375d664cbf5460495a3cf039dacc56699683239`
- `frontend/src/styles/main.css`: `0e537b6cb0117a6402847ea04bd5e79d7aaf483845dcb9adab988937aac3935a`
- `frontend/src/styles/components.css`: `20aa864d9477d5767334e135ff04f2b4db1a74db83a53605a62cc71b98b6726f`
- `frontend/src/styles/execution-view.css`: `c754041e4ad09aa6d0419ecb5f4d9069578233b898ae764b4c495cf868df30a6`
- `frontend/src/components/plan-settings-polish.css`: `7e73cce204a0e84a760f6222195cfca6c766db59575a84ec8a3b622187d687b9`

### Frontend Dist Bundle (Compilado pelo Vite)
- `frontend/dist/index.html`: `35fc88d8256866231e8985cfc1232a1f58801ae3587ac39827c09dd6ddf686a1`
- `frontend/dist/assets/index-DJ1sYgkX.js`: `c74b7ad3de1eb3cc86080cd3a7c531c815352ca3816dac51b815dffd4c69f749`
- `frontend/dist/assets/index-Wmy6xx4v.css`: `4e3a5ca6dd1fb61d6cf96718b07cf6650d697e4eb9242b9563c5c19dfcf6d3ca`

### Suíte Crítica de Testes
- `tests/unit/test_source_accounting.py`: `270920e3964bc6b59619a54d4a57925fcfedaf915e59c2d19a9299878d83bc97`
- `tests/integration/test_sources_endpoint.py`: `194526a35d4846d410498af9f771b10401068db5a188568639b624f3e1f3c99d`
- `frontend/src/tests/sources-accounting.test.ts`: `bccd808984b6cef45baf596685f11216e900e9bb24903d658cf5039bf17d399e`
- `frontend/features/05_sources_accounting.feature`: `47afe8b9cd2323803f6b2e3654330a75cd9ebae4b7d0c344e96b893420b3ba8f`
- `frontend/features/step_definitions/steps.ts`: `3eafca4227e7365e9eb0975ae8684d3666df957577741182db46b96f3301884c`
- `frontend/features/support/world.ts`: `af612454781a794714186ceaf30f7b1097cc494e48d7652067f09e629d2ad21a`

### Referências Originais de Documentação (Imutáveis)
- `/home/eliezer/Escritorio/dominuslabs-codex/docs-src/assets/docs.css`: `e92d1c398327ed8e2d42fd81a9a3e137c64449bfcd119bf7e56f3894376699cd`
- `/home/eliezer/Escritorio/dominuslabs-codex/docs-src/assets/extra.css`: `b0216d8637c0f338058c85ebc4049502e1b5fc853ab596e6c5c55688e7fa314b`

---

## 7. Disposição e Próximos Passos

### Veredito Preliminar
```text
DISPOSIÇÃO: preliminary_pending_round5_and_QA
```

### Justificativa Holística
A implementação estrutural é sólida e atende às especificações mais exigentes de segurança, normas do Adendo 002 e modelo de fontes S01. Não obstante, o rigor da arbitragem independente impede a antecipação de aprovação para release enquanto pendem:
1. Resolução dos achados P1 de foco e acessibilidade no `PlanView` e cópia honesta no `App.tsx`.
2. Conclusão e congelamento das evidências visuais e críticas nativas da Rodada 5.
3. Finalização da correção de asserções da suíte Cucumber pelo responsável de QA.

Após o saneamento desses pontos pelo trabalhador Hermes, o orquestrador poderá retomar o mesmo contexto independente para a emissão do parecer final da Fase 2. O Gate G04 só deve ser executado após a aprovação formal da Fase 2.
