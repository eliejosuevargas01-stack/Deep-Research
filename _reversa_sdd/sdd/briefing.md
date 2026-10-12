# Spec: Módulo backend de briefing

**Versão:** 1.0  
**Status:** 🟡 PLANEJADO — rascunho documental, sem aprovação técnica ou auditoria de implementação.  
**Autor:** reversa-spec-sdd  
**Data:** 2026-10-11  
**Reviewers:** Orchestrator (contrato e gates); usuário (decisões de produto pendentes).

## 1. Resumo

🟡 PLANEJADO: Receber tema, obter resultados SERP via Jina, sem garantia de Google exclusivo e gerar pontos de foco para revisão do operador. Backend permite editar, aprovar, consultar conteúdo aprovado e reabrir; não responde ao tema nem inicia pesquisa.

## 2. Contexto e Motivação

🟡 PLANEJADO — **Problema:** Operador precisa decidir escopo investigativo antes da investigação; consumidor futuro precisa de briefing aprovado.
🟡 PLANEJADO — **Evidências:** PRD e RF-01 a RF-10 dos requisitos da feature, especialmente esclarecimentos da seção 9; nenhuma medição de uso ou regra extraída do código.
🟡 PLANEJADO — **Por que agora:** Usuário definiu briefing backend como único componente desta etapa. `.reversa/active-requirements.json` identifica `001-modulo-briefing`; estado global antigo não comprova entrega desta feature.

## 3. Goals (Objetivos)

- 🟡 PLANEJADO — G-01: Validar tema com 3 a 300 caracteres antes de chamadas externas.
- 🟡 PLANEJADO — G-02: Gerar, salvar edições e aprovar somente conteúdo com 3 a 7 pontos de foco, título e descrição; alvo habitual 5, não exatamente 5.
- 🟡 PLANEJADO — G-03: Isolar busca e geração, preservar registro em retentativas e expor somente conteúdo aprovado ao consumidor futuro.

| Métrica | Baseline atual | Target | Prazo |
|---|---|---|---|
| 🟡 PLANEJADO — Quantidade válida | Não medida | 100% dos conteúdos aceitos entre 3 e 7 | Gate de aceite |
| 🟡 PLANEJADO — Busca sem falhas | Não medida | 1 chamada SERP, 0 leitura de páginas | Gate de contrato e testes |
| 🟡 PLANEJADO — Chamadas externas simultâneas na geração | Não medida | Máximo 1 | Gate de testes isolados |
| 🟡 PLANEJADO — Segredos expostos | Não medida | 0 ocorrências em payloads/logs | Gate de segurança |

## 4. Non-Goals (Fora do Escopo)

- 🟡 PLANEJADO — NG-01: Pesquisa profunda, workers de personas, respostas conclusivas e relatórios.
- 🟡 PLANEJADO — NG-02: Frontend, telas e contratos globais de pesquisa.
- 🟡 PLANEJADO — NG-03: Leitura de páginas, Jina Reader, scraping e tools/provedores alternativos de busca.
- 🟡 PLANEJADO — NG-04: Implementação, migrações, testes executáveis, deploy ou alteração de estado nesta entrega documental.

## 5. Usuários e Personas

🟡 PLANEJADO — **Primário:** Operador da pesquisa; informa tema, revisa, edita, reordena, aprova e reabre.
🟡 PLANEJADO — **Secundário:** Módulo de pesquisa, consumidor futuro de foco aprovado; sua execução fica fora.
🟡 PLANEJADO — **Jornada atual:** Não descrita pelas fontes; não inferir telas ou práticas operacionais do legado.
🟡 PLANEJADO — **Jornada futura:** Operador solicita geração, revisa rascunho, salva ajustes e aprova; pode reabrir para editar. Consumidor consulta conteúdo aprovado sem iniciar investigação neste módulo.

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

🟡 PLANEJADO: IDs mantidos sem renumeração; cada linha corresponde ao mesmo RF em `_reversa_forward/001-modulo-briefing/requirements.md`, seção 5. RN e esclarecimentos complementam o critério, não criam outro RF.

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| 🟡 PLANEJADO — RF-01 | O sistema deve receber tema e criar registro identificável em geração. | Must | Dado tema de 3 ou 300 caracteres, quando criar, então aceitar; 2 ou 301 são rejeitados antes de chamadas externas. RN-01. |
| 🟡 PLANEJADO — RF-02 | O sistema deve oferecer somente tool SERP via Jina ao agente. | Must | Dada busca bem-sucedida, então obter resultados SERP via Jina (Google exclusivo dispensado pelo usuário), não ler páginas nem fazer outra busca; chamadas sequenciais somente após falha. RN-02; contrato condicionado a T003. |
| 🟡 PLANEJADO — RF-03 | O sistema deve gerar rascunho de pontos importantes. | Must | Dado resultado SERP, quando gerar, então salvar 3 a 7 pontos com título e descrição, sem conclusão; 3, 4, 6 e 7 são válidos, 5 é alvo habitual. RN-03. |
| 🟡 PLANEJADO — RF-04 | O sistema deve carregar instrução de arquivo da pasta de prompts. | Must | Dado arquivo alterado, quando ocorrer próxima geração, então usar nova instrução sem mudar lógica; arquivo ausente/vazio impede chamada do agente. RN-04. |
| 🟡 PLANEJADO — RF-05 | O sistema deve permitir editar rascunho. | Must | Dado rascunho, quando alterar/adicionar/remover/reordenar e salvar 3 a 7 pontos, então versão fica consultável; <3 ou >7 retorna 422 e mantém versão anterior. RN-05. |
| 🟡 PLANEJADO — RF-06 | O sistema deve permitir aprovação. | Must | Dado rascunho com 3 a 7 pontos válidos, quando aprovar, então estado aprovado; quantidade inválida é recusada preservando versão anterior; edição direta é recusada. RN-06. |
| 🟡 PLANEJADO — RF-07 | O sistema deve expor briefing aprovado ao consumidor futuro. | Must | Dado aprovado, quando consultar conteúdo para etapa posterior, então disponibilizar conteúdo aprovado sem iniciar investigação. RN-07; fonte registra requisito originalmente inferido. |
| 🟡 PLANEJADO — RF-08 | O sistema deve informar falhas de busca, geração e prompt. | Must | Dada falha, então não publicar rascunho inválido e retornar motivo seguro, sem segredos. |
| 🟡 PLANEJADO — RF-09 | O sistema deve reabrir briefing aprovado. | Must | Dado aprovado, quando solicitar reabertura, então retornar a rascunho e permitir edição; não acrescentar restrição baseada em execução de pesquisa. RN-06. |
| 🟡 PLANEJADO — RF-10 | O sistema deve retentar automaticamente operação externa que falhar. | Must | Dada falha externa, então até 4 tentativas totais por operação, inicial mais 3, sequenciais no mesmo registro; falha LLM reutiliza SERP bem-sucedida sem refazer busca. |

### 6.2 Fluxo Principal (Happy Path)

1. 🟡 PLANEJADO: O usuário envia tema; o sistema valida limite e identifica registro em geração.
2. 🟡 PLANEJADO: O sistema lê prompt do arquivo para esta geração e obtém SERP por única tool SERP Jina, sem garantia de Google exclusivo e sem leitura de páginas; ordem concreta entre leitura e busca depende de OQ-04.
3. 🟡 PLANEJADO: O sistema entrega prompt, tema e SERP ao agente; valida saída antes de publicar rascunho de 3 a 7 pontos.
4. 🟡 PLANEJADO: O usuário revisa e salva edições dentro do mesmo intervalo; o sistema preserva ordem salva.
5. 🟡 PLANEJADO: O usuário aprova; o sistema bloqueia edição direta e disponibiliza conteúdo aprovado, sem iniciar pesquisa.

### 6.3 Fluxos Alternativos

- 🟡 PLANEJADO — Falha SERP: retentar somente busca no mesmo registro, uma chamada por vez, até 4 tentativas totais; esgotamento resulta em falho e motivo seguro.
- 🟡 PLANEJADO — Falha LLM após sucesso SERP: retentar somente LLM com SERP obtida, até 4 tentativas totais; sem busca adicional. Saída inválida de parse ou contagem fora de 3..7 é falha de LLM dentro do teto de 4 e reutiliza SERP; esgotadas as 4 tentativas, o briefing é marcado FAILED sem rascunho inválido.
- 🟡 PLANEJADO — Reabertura: aprovado retorna a rascunho, libera edição e deixa de ser conteúdo atualmente aprovado para consumidor futuro; não dispara agente ou investigação.
- 🟡 PLANEJADO — Saída estrutural inválida (parse/formato/title-description/faixa3..7) consome tentativa no teto4 com SERP reuso e exaustão FAILED; orientação de pontos de foco sem conclusão vem do prompt, sem julgador semântico automático ou chamadas extras.

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| 🟡 PLANEJADO — RNF-01 | Modularidade | Regras, prompts e contratos dentro do módulo | Escolha de stack/reuso pendente, não fato legado |
| 🟡 PLANEJADO — RNF-02 | Segurança | 0 segredos em respostas, logs e registro | Inclui `JINA_API_KEY` e chaves LLM |
| 🟡 PLANEJADO — RNF-03 | Confiabilidade | 0 rascunhos parciais publicados como válidos | Falha não substitui conteúdo anterior válido |
| 🟡 PLANEJADO — RNF-04 | Testabilidade | Dependências substituíveis sem rede | Plano de verificação, nenhum teste implementado aqui |
| 🟡 PLANEJADO — RNF-05 | Rastreabilidade | Tema, busca, prompt usado, edições e aprovação | Should; armazenamento concreto pendente |

## 8. Design e Interface

🟡 PLANEJADO — **Componentes afetados:** Interface backend para criar, consultar, editar, aprovar, reabrir e consultar aprovado; adaptadores SERP/LLM e leitura de prompt. Nomes de rotas, métodos e schemas de transporte não congelados.
🟡 PLANEJADO — **Comportamento esperado:** Respostas permitem identificar registro e estado; falhas mostram motivo seguro. UI não aplicável; frontend fora do escopo.

| Estado lógico | Significado | Transição prevista |
|---|---|---|
| 🟡 PLANEJADO — Em geração | Registro criado, processamento pendente | Sucesso válido: rascunho; falha terminal: falho |
| 🟡 PLANEJADO — Rascunho | Conteúdo editável com 3 a 7 pontos | Edição válida mantém estado; aprovação válida: aprovado |
| 🟡 PLANEJADO — Aprovado | Conteúdo disponível ao consumidor; edição direta recusada | Reabertura: rascunho |
| 🟡 PLANEJADO — Falho | Nenhum rascunho inválido disponibilizado | Recuperação manual/regeneração pendente; não inventar endpoint |

🟡 PLANEJADO: Identificadores serializados de estado e resposta a registro inexistente permanecem em OQ-02; ausência não deve ser apresentada como aprovado.

## 9. Modelo de Dados

🟡 PLANEJADO — **Modelo lógico proposto, não schema aprovado:** Briefing contém identificador, tema, estado e lista ordenada de pontos; cada ponto contém título e descrição. Referência ao resultado SERP e prompt efetivamente usado viabiliza reuso e rastreabilidade sem segredos.
🟡 PLANEJADO — **Persistência:** Retentativas mantêm mesmo registro. Edição rejeitada mantém versão anterior; aprovação/reabertura refletem conteúdo e estado coerentes. Atomicidade, versionamento, retenção e armazenamento dependem de OQ-03.
🟡 PLANEJADO — **Migrações necessárias:** Indeterminado até decisão de persistência; nenhuma tabela, banco, migration ou alteração implementada neste documento.

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 PLANEJADO — Jina Search `https://s.jina.ai/`, SERP sem motor exclusivo | Obrigatória, contrato de cliente aceito; integração não testada | Retentativas de falha externa, depois falho; nenhum provedor alternativo |
| 🟡 PLANEJADO — Provedor LLM compatível com módulo de completude | Obrigatória | Retentativas com SERP reaproveitada, depois falho |
| 🟡 PLANEJADO — Arquivo na pasta de prompts | Obrigatória | Ausente/vazio: falha de configuração sem chamar agente |

🟡 PLANEJADO: usuário resolveu escolhas de T003 em 2026-10-11. Usar SERP Jina sem garantia de Google exclusivo, parser tolerante com `title`, `url`, `description` e extras ignorados. Timeout de cliente Jina/LLM 30s por tentativa, configurável. `X-Respond-With: no-content` tem evidência documental; não comprova operação real do SaaS. Exemplo sintético não é fixture oficial; nenhuma chamada paga feita.

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| 🟡 PLANEJADO — EC-01: Tema fora do limite | 2 ou 301 caracteres | Rejeitar antes de chamadas externas; regra de contagem/normalização em OQ-05 |
| 🟡 PLANEJADO — EC-02: Quantidade inválida | Geração, edição ou aprovação com 2 ou 8 pontos | Não publicar inválido; edição retorna 422; edição/aprovação preservam versão anterior |
| 🟡 PLANEJADO — EC-03: Busca indisponível | Falha externa SERP | Até 4 tentativas totais sequenciais; esgotamento: falho, motivo seguro; 503 é mitigação proposta pelo PRD, não contrato congelado |
| 🟡 PLANEJADO — EC-04: LLM indisponível | Falha externa após SERP válida | Até 4 tentativas totais LLM, reusar SERP, mesmo registro; depois falho |
| 🟡 PLANEJADO — EC-05: Prompt ausente/vazio | Leitura do arquivo não produz instrução | Falha de configuração; não chamar agente, não substituir por prompt embutido |
| 🟡 PLANEJADO — EC-06: Edição de aprovado | Tentativa sem reabrir | Recusar edição e preservar conteúdo; reabrir permite editar |
| 🟡 PLANEJADO — EC-07: Conteúdo inválido | SERP/LLM não atende contrato ou foco | Não publicar rascunho inválido; falha de parse ou contagem fora de 3..7 consome tentativa do teto de 4 e reutiliza SERP; esgotadas as 4 tentativas, briefing é marcado FAILED sem rascunho inválido; requisito de pontos de foco sem conclusão permanece orientado pelo prompt; não há julgador semântico automático nem retry extra por qualidade/conclusividade. |
| 🟡 PLANEJADO — EC-08: Operações concorrentes | Aprovar/editar/reabrir sobre mesmo registro | Proposta: evitar conteúdo/estado incoerentes; política e resposta em OQ-03, não regra aprovada |

## 12. Segurança e Privacidade

- 🟡 PLANEJADO — **Autenticação/autorização:** Consulta aprovada deve ser segura; identidade, permissões e mecanismo concretos em OQ-02, sem herdar JWT/CSRF do legado.
- 🟡 PLANEJADO — **Dados sensíveis:** Não retornar ou registrar credenciais/conteúdo sensível em erros. Tema pode conter dados do operador; retenção e acesso em OQ-03.
- 🟡 PLANEJADO — **Auditoria:** Rastrear eventos e prompt usado sem segredos é Should; formato, acesso e retenção aguardam plano técnico.

## 13. Plano de Rollout

- 🟡 PLANEJADO — **Estratégia proposta:** Primeiro congelar decisões técnicas e validar T003, depois implementação autorizada e verificação isolada; liberação somente após auditoria independente. Nenhum deploy autorizado aqui.
- 🟡 PLANEJADO — **Rollback proposto:** Suspender criação/alteração se contrato divergir, preservar dados existentes; mecanismo, responsáveis e reversão de schema a definir no plano antes de release.
- 🟡 PLANEJADO — **Monitoramento proposto:** Contar chamadas por operação, simultaneidade, estados falhos, violações de faixa e exposição de segredos; janela e alertas no gate de release.

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo/gate concreto |
|---|---|---|---|---|
| 🟡 PLANEJADO — OQ-01 | RESOLVIDA POR DECISÃO, 2026-10-11: SERP Jina sem Google exclusivo; parser tolerante (`title`, `url`, `description`; extras ignorados); modo `no-content` documental. | Integração real não testada | Orchestrator, T003 | Revisar fontes e decisão antes de fechar T003; testes isolados não alegam resposta real |
| 🟡 PLANEJADO — OQ-02 | ⚠️ ABERTO: Quais rotas, métodos, auth, permissões, schemas, estados serializados e erros HTTP? | Alto | Responsável backend + Orchestrator | Congelar contrato antes de implementar interface e gate de acesso seguro |
| 🟡 PLANEJADO — OQ-03 | ⚠️ ABERTO: Como persistir, versionar, proteger concorrência, idempotência e retenção? | Alto | Responsável backend + Orchestrator | Design revisado antes de storage/migrations; checks de preservação e concorrência definidos |
| 🟡 PLANEJADO — OQ-04 | ⚠️ ABERTO: Qual caminho de prompt, ordem leitura/busca e intervalo de retentativas? Timeout Jina/LLM já decidido: 30s por tentativa, configurável. | Médio | Responsável backend + Orchestrator | Antes de adaptadores: plano demonstra teto de 4 e recarga na próxima geração; nenhum formato de arquivo exigido aprovado |
| 🟡 PLANEJADO — OQ-05 | ⚠️ ABERTO: Como contar caracteres, tratar espaços e validar título/descrição além de sua presença? | Médio | Usuário + responsável backend | Antes dos validadores: exemplos de fronteira acordados; não alterar limites 3–300 e 3–7 |
| 🟡 PLANEJADO — OQ-06 | RESOLVIDA TECNICAMENTE, 2026-10-11: parse, formato/lista/title-description e contagem 3..7 inválidos são falhas de saída na tentativa LLM; sem julgador semântico automático. | Retry estrutural dentro do teto RF-10 | Responsável backend + Orchestrator | Concretização técnica de RF-10: até 4 tentativas totais LLM, SERP reutilizada; exaustão FAILED sem rascunho inválido. Prompt orienta pontos de foco sem conclusão; nenhum retry adicional por avaliação semântica. |

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 PLANEJADO — Tema 3–300; pontos 3–7 em geração/edição/aprovação | Exatamente 5 ou limites diferentes não aprovados | Esclarecimentos explícitos; 5 é alvo habitual |
| 🟡 PLANEJADO — Uma tool SERP Jina, sem Google exclusivo e sem leitura de páginas | Reader, scraping, múltiplos provedores fora | RN-02 e decisão do usuário 2026-10-11; parser tolerante; timeout 30s configurável |
| 🟡 PLANEJADO — Até 4 tentativas por operação falha; reuso SERP | Rebuscar após sucesso não permitido | RF-10 e seção 9; mesma identidade do registro |
| 🟡 PLANEJADO — Prompt de arquivo na próxima geração; reabertura livre de restrição inventada | Prompt embutido e bloqueio por execução não aprovados | RN-04/RN-06; edição direta bloqueada até reabertura |

## Apêndice

### Referências e histórico

- 🟡 PLANEJADO — Fontes de produto: `_reversa_sdd/prd.md`; `_reversa_forward/001-modulo-briefing/requirements.md`, RN-01–RN-07, RF-01–RF-10 e seção 9.
- 🟡 PLANEJADO — Contexto operacional lido: `.reversa/state.json`, `.reversa/active-requirements.json`, `AGENTS.md`; não usados para extrair regras antigas ou afirmar implementação.
- 🟡 PLANEJADO — Template: skill `reversa-spec-sdd`, `references/spec_template.md`. Versão 1.0, 2026-10-11: spec única backend; nenhum handoff executado automaticamente.

### Relatório de avaliação

🟡 PLANEJADO: Execução real com Python 3.14.7, exit code 0. Comando: `python3 /root/.hermes/profiles/orchestrator/skills/software-development/reversa/agents/reversa-spec-sdd/scripts/spec_scorer.py --spec /root/projects/deep-research/_reversa_sdd/sdd/briefing.md`.

Trecho literal da saída:
```text
  SCORE TOTAL: 100.0/100  —  ⭐ Excelente — Pronta para implementação

  BREAKDOWN POR DIMENSÃO:
  Dimensão             Score      Peso     Contribuição
  --------------------------------------------------
  Completude           100%       30%     30.0/pt
  Testabilidade        100%       25%     25.0/pt
  Clareza              100%       20%     20.0/pt
  Escopo               100%       15%     15.0/pt
  Edge Cases           100%       10%     10.0/pt
```

- 🟡 PLANEJADO — Gaps críticos e sugestões automáticas: nenhum emitido pelo scorer nesta execução.
- 🟡 PLANEJADO — Gaps de entrega: OQ-01 resolvida por decisão em 2026-10-11; OQ-02–OQ-05 permanecem para design, exceto timeout de OQ-04 definido como 30s configurável e OQ-06 concretização técnica RF-10. T003 aguarda revisão do contrato documental atualizado; integração real não testada. Score e classificação automática não aprovam contrato, produto, segurança ou implementação; gates técnicos e auditoria independente continuam obrigatórios.
- 🟡 PLANEJADO — Próxima etapa depende de autorização explícita; redação não executa `/reversa-forward` nem audita própria implementação.
