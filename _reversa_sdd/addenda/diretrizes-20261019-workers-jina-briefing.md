# Adendo Normativo Aprovado: Diretrizes Jina, Persona Workers e Briefing Síncrono

> **Identificador:** `diretrizes-20261019-workers-jina-briefing`  
> **Status:** 🟢 DIRETRIZES APROVADAS (Documental / Requisitos Vigentes)  
> **Data:** 2026-10-19  
> **Origem:** Decisão explícita do operador registrada no relato `_reversa_bugs/investigacao-redator/intake/relato-20261019-2100-doc-worker-jina-sync.md`.  
> **Aviso de Implementação:** Este adendo define as diretrizes normativas de produto e especificações de requisitos canônicos de alto nível. A implementação em código fonte (`app/`) e a verificação operacional permanecem futuras/não-executadas nesta sprint documental.

---

## Vigência e Precedência Normativa

- **Vigência:** A partir de 2026-10-19.
- **Precedência:** Este adendo possui precedência normativa sobre as especificações anteriores presentes em `_reversa_forward/001-modulo-briefing/requirements.md`, `_reversa_forward/002-investigacao-personas/requirements.md`, `_reversa_forward/003-modulo-auditoria/requirements.md` e nos adendos prévios de `_reversa_sdd/addenda/`.
- **Regra de Leitura:** Qualquer trecho das especificações anteriores ou artefatos da extração SDD em `_reversa_sdd/` (PRD, SDD Briefing, etc.) que conflite com o presente adendo considera-se superado por esta diretriz aprovada.

---

## 1. Contrato de Coleta Integral Jina e Limpeza de HTML

1.1. **Entrada do Worker e Formulação de Query:** Cada worker recebe como entrada sua personalidade cognitiva (`persona`), o ponto de investigação atribuído e a ferramenta de busca (`tool`). A formulação e o refinamento da query de busca são realizados autonomamente pelo modelo a partir dessas entradas.  
1.2. **10 Páginas Integrais por Query:** A ferramenta de busca Jina (`jina_search`) deve fornecer ao worker 10 páginas em texto limpo com seus corpos completos (não resumos, snippets, ou cortes de busca). O conteúdo informativo deve ser entregue na íntegra, sem truncamento silencioso do corpo.  
1.3. **Limpeza/Parser Prévio Anti-Boilerplate:** Todo o conteúdo HTML bruto obtido deve passar obrigatoriamente por um parser/pipeline de limpeza que expurga cabeçalhos (`header`), rodapés (`footer`), barras de navegação (`nav`), anúncios, scripts e lixo institucional/acessibilidade, entregando ao worker apenas o corpo de texto limpo e informativo na íntegra.  
1.4. **Garantia de Aprendizado do Worker e Saída Estruturada:** A premissa cognitiva é de que a leitura das páginas integrais sempre fornece aprendizado ao worker. O worker **nunca** deve retornar uma síntese analítica vazia ou nula. Tudo o que for aprendido de relevante deve ser condensado na saída estruturada, com atribuição de fontes e URLs lidas, sem invenção de dados ou fontes fictícias e sem descartar evidências parciais relevantes.  
1.5. **Orçamento e Parada Voluntária:**
   - Cada worker (instanciado para uma persona e um ponto de investigação) executa a primeira query obrigatoriamente.
   - O worker analisa o material das 10 páginas limpas e decide internamente se a informação coletada é suficiente para o ponto ou se necessita formular nova query.
   - O orçamento é de no máximo **3 queries distintas** por persona/ponto por rodada. A parada voluntária antes de 3 queries é encorajada ao atingir suficiência.
   - Retries técnicos de transporte/rede da mesma query não contam como novas queries.

1.6. **Políticas Pendentes (Exceções de Coleta Upstream):**
   - Retorno de menos de 10 páginas pelo provedor externo;
   - Páginas ilegíveis ou com conteúdo inacessível;
   - Estouro de janela de contexto do modelo pelo volume agregado dos corpos de texto limpos;
   - Falha fatal/irrecuperável de uma persona individual;
   - Protocolo Search vs Reader (a diretriz é conceitual de leitura de corpos integrais limpos, não constituindo garantia física da API pública Jina nem adoção obrigatória do endpoint Reader).  
   Essas situações constituem políticas de recuperação formalmente PENDENTES de especificação futura, não devendo ser presumidas como resolvidas por código ou testes existentes.

---

## 2. Persistência Individual, Barreira de Sincronização e Merge das 4 Personas

2.1. **Persistência Individual Pré-Merge:** Assim que uma persona conclui sua busca e gera sua síntese analítica não-vazia (com atribuição de fontes e URLs lidas), o resultado é gravado individualmente no banco de dados (`research_step_results`).  
2.2. **Barreira Estrita das 4 Personas:** O ponto de investigação **não** transita para auditoria até que todas as 4 personas (`historian`, `skeptic`, `pragmatist`, `futurist`) tenham concluído suas análises e persistido seus resultados.  
2.3. **Etapa Formal de Merge Inter-Personas:**  
   - Após as 4 respostas estarem persistidas para o mesmo ponto e rodada, o sistema executa um procedimento de **merge/conexão**.  
   - O merge consolida as 4 visões complementares (histórica, cética, pragmática, prospectiva), preservando as origens, contradições e lacunas identificadas, sem inventar fatos nem perder rastreabilidade de origem.  
2.4. **Disparo da Auditoria:** Somente após a conclusão e gravação do merge o ponto é submetido ao Agente Auditor (Feature 003).

---

## 3. Gestão de Ciclo de Vida da Auditoria e Teto de Tentativas

3.1. **Quatro Tentativas Totais por Ponto:** O ciclo completo de investigação + auditoria para cada ponto possui um teto rígido de **4 tentativas totais** (1 tentativa inicial + até 3 retentativas/reprovações).  
3.2. **Quarta Reprovação e Transição para Redação:** Caso o ponto atinja a 4ª reprovação na auditoria, a busca de novas evidências/re-pesquisa para esse ponto é encerrada definitivamente. O ponto é marcado como concluído com ressalvas (`AUDIT_CAVEAT`). A transição para a fase de redação (`WRITE` / Writer) ocorre somente após TODOS os pontos de pesquisa atingirem estado conclusivo (`AUDIT_APPROVED` ou `AUDIT_CAVEAT`); a 4ª reprovação de um ponto isolado não dispara o Writer enquanto outros pontos estiverem ativos na investigação ou auditoria.

---

## 4. Briefing Estritamente Síncrono (Request/Response HTTP 200/201)

4.1. **Operação Síncrona HTTP:** Os endpoints de criação e revisão de briefing (`POST /briefings` e `PATCH /briefings/{research_id}`) devem processar a geração do rascunho de pontos (Scout SERP + LLM) de forma estritamente síncrona dentro do ciclo da requisição/resposta HTTP, retornando status HTTP 200/201 com o briefing concluído.  
4.2. **Eliminação de Polling:** Fica proibida a exigência de polling do cliente HTTP ou padrão assíncrono com HTTP 202 para a etapa de obtenção do briefing.  
4.3. **Async/Await Interno e Operações em Background:** O uso de corrotinas `async/await` no backend é mantido. A execução em background é permitida tanto para o disparo da investigação posterior (`POST /briefings/{research_id}/investigate` e pós-PATCH) quanto para o despacho de notificações assíncronas/webhooks de entrega de relatório final; o mecanismo assíncrono não é prescrito (ex.: BackgroundTasks, task queue, etc.). O que permanece proibido com HTTP 202/polling é estritamente a etapa de criação e revisão do briefing.

---

## 5. Cenários Documentais de Aceitação Normativa (Adicionados 2026-10-19)

Os seguintes cenários constituem critérios puramente DOCUMENTAIS de aceitação normativa (não são testes runtime executados nesta sprint):

1. **10 páginas texto integral + limpeza:** A tool Jina Search entrega 10 páginas em texto limpo (corpos completos, não snippets) após pipeline de limpeza que expurga `header`, `footer`, `nav`, scripts, anúncios e lixo institucional/acessibilidade, sem truncamento silencioso.
2. **3 queries / parada cedo:** Cada worker (persona + ponto) executa obrigatoriamente a 1ª query; decide internamente se o material é suficiente; teto rígido de 3 queries distintas por persona/ponto/rodada; parada voluntária antecipada é fluxo normal quando há suficiência.
3. **Resultado não vazio persistido por persona:** Cada uma das 4 personas grava seu resultado analítico não-vazio em `research_step_results` individualmente antes de qualquer merge, com estrita atribuição e sem fontes inventadas.
4. **Nenhum audit antes 4 persistidas mesmo ponto/rodada:** A barreira RN-15 exige que as 4 respostas estejam persistidas para o mesmo ponto e rodada antes do merge; só após o merge o ponto é submetido à auditoria (Feature 003). Falhas terminais não contam como análises válidas.
5. **Merge preserva origens, contradições, lacunas:** O merge consolida as 4 visões complementares sem inventar fatos nem perder rastreabilidade de origem; contradições e lacunas são preservadas.
6. **Briefing criação/revisão síncrono e SERP-only:** `POST /briefings` e `PATCH /briefings/{research_id}` respondem HTTP 200/201 síncrono; fase de briefing usa apenas SERP Jina, sem leitura de 10 páginas integrais (esta aplica-se exclusivamente às personas investigativas da Feature 002).
7. **Investigação pode background:** O disparo da investigação posterior (`POST /briefings/{research_id}/investigate` e pós-PATCH) executa em background; webhooks de callback final também são permitidos em background.
8. **Quarta reprovação continua Writer após todos conclusivos:** Na 4ª reprovação da auditoria (teto de 4 tentativas totais incluindo inicial), a busca encerra para o ponto, que é marcado `AUDIT_CAVEAT`; o avanço para o Agente Redator (Feature 004) aguarda que todos os pontos estejam conclusivos.

---

## 6. Mapa de Artefatos Afetados (Traceability Matrix)

| Artefato | Impacto e Precedência Normativa |
|---|---|
| `_reversa_forward/001-modulo-briefing/requirements.md` | Vigência de geração síncrona HTTP 200/201 (sem 202/polling) e escopo SERP-only do Scout (sem leitura de 10 páginas integrais). |
| `_reversa_forward/002-investigacao-personas/requirements.md` | RN-03 (entrada persona+ponto+tool), RN-05 (10 corpos limpos integrais sem truncamento), RN-06 (máx 3 queries, 1ª obrigatória, aprendizado não-vazio sem fontes inventadas), RN-15 (barreira estrita de 4 análises persistidas antes do merge). |
| `_reversa_forward/003-modulo-auditoria/requirements.md` | RN-301 e precedência do adendo: barreira de 4 análises analíticas persistidas para o mesmo ponto e rodada antes do merge e submissão ao auditor; teto de 4 tentativas totais por ponto (1 inicial + 3 reprovações). |
| `README.md` | Reconciliação dos fluxos síncrono (briefing 201) vs assíncrono (investigate 202 background), contrato de 10 corpos limpos, barreira de 4 personas e tratamento de conflitos CAS sem reenvios cegos. |
| `contracts.md` | Cláusula explícita de barreira de 4 análises persistidas antes de auditoria em Worker Failure Resilience (sem aprovação de 3/4) e políticas pendentes de upstream. |
| `workflow.md` | Diagrama histórico anotado com precedência das diretrizes normativas (briefing síncrono, 10 corpos limpos integrais, barreira de 4 personas, merge e teto de 4 tentativas). |
| `docs/api/briefing-scout.md` | Resposta 202 para investigate em background, normalização de colunas Markdown, restauração de headers em exemplos cURL e tratamento reconciliado de erros. |
