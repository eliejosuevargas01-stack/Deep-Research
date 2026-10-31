# Spec: Endpoint /api/v1/plan — Plano de Investigação

**Versão:** 1.1
**Status:** Planejada (revisão normativa v2)
**Autor:** reversa-spec-sdd
**Data:** 2026-10-27 (original 2026-10-21)
**Reviewers:** Equipe Deep Research

---

## 1. Resumo

🟡 O endpoint `POST /api/v1/plan` constitui a primeira etapa do pipeline de pesquisa profunda Deep Research, encarregado de receber o tema informado pelo usuário, persistir o registro inicial da pesquisa na base SQLite permanente e acionar a persona planejador com suporte de chamadas ao Jina SERP para leitura estrita de resultados de busca, gerando e persistindo N pontos focais de investigação.

🟡 A funcionalidade viabiliza a estruturação prévia do escopo investigativo com base em dados de busca reais sem consumir conteúdo integral de páginas web, estabelecendo a base analítica necessária para as etapas posteriores.

🟡 **v1.1 (normativa):** a entrada do plano não sofre truncamento; o endpoint aceita `execution_mode` e o propaga ao runner; em reavaliação, o plano recebe o histórico acumulado das coletas; o Jina é acessado por rota direta ou proxy, com contrato idêntico.

---

## 2. Contexto e Motivação

**Problema:**
🟡 No processo manual, analistas despendem horas para decompor um tema amplo em perguntas e eixos de investigação consistentes, frequentemente resultando em escopos enviesados ou sem fundamentação prévia no ecossistema de informações públicas.

**Evidências:**
🟡 Levantamentos operacionais documentados no PRD indicam que investigações manuais demoram dias e apresentam baixa rastreabilidade, enquanto ferramentas automáticas concorrentes operam como caixas-pretas que não permitem auditar a fase de planejamento.

**Por que agora:**
🟡 A automação com controle explícito dos pontos investigativos antes da varredura profunda reduz o consumo desnecessário de tokens e assegura alinhamento antes do processamento nas fases seguintes.

**Motivação da revisão v1.1:**
🟡 O limite de 500 caracteres no campo `tema` rejeitava briefings reais de pesquisa (briefings de campanha e dossiês de intake passam disso facilmente), obrigando o usuário a resumir a entrada — perda de informação na porta de entrada do pipeline. Além disso, o endpoint não tinha como escolher entre execução paralela e sequencial, e a reavaliação de plano não enxergava as coletas já realizadas.

---

## 3. Goals (Objetivos)

- [ ] G-01: 🟡 Gerar exatamente N pontos de investigação estruturados para qualquer tema submetido.
- [ ] G-02: 🟡 Persistir a pesquisa e seus pontos na base SQLite permanente com identificadores únicos.
- [ ] G-03: 🟡 Restringir o acesso externo da ferramenta de busca no planejamento exclusivamente a metadados da SERP, impedindo requisições ao Reader de páginas inteiras.
- [ ] G-04 (v1.1): 🟡 Aceitar o briefing integralmente, sem limite artificial de caracteres nem corte silencioso.
- [ ] G-05 (v1.1): 🟡 Propagar `execution_mode` ao pipeline quando `async_execute=true`.
- [ ] G-06 (v1.1): 🟡 Garantir que a rota Jina (direta ou proxy) seja indiferente ao planejador.

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---|---|---|---|
| 🟡 Taxa de pesquisas com N pontos persistidos | 0% | = 100% | 2026-10-31 |
| 🟡 Tempo de resposta da geração do plano | N/A | < 120s | 2026-10-31 |
| 🟡 Conformidade com restrição de acesso apenas à SERP | 0% | = 100% | 2026-10-31 |
| 🟡 Briefings rejeitados por tamanho | > 0 (limite 500) | = 0 | 2026-10-31 |
| 🟡 `execution_mode` propagado ao runner | 0% | = 100% | 2026-10-31 |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: 🟡 O sistema não deve efetuar raspagem de conteúdo completo ou leitura de páginas web (`r.jina.ai`) durante a execução do endpoint de planejamento.
- NG-02: 🟡 O sistema não deve executar buscas paralelas por persona nem acionar personas especializadas (historiador, visionario, cetico, futurista), reservadas para a etapa de busca.
- NG-03: 🟡 O sistema não deve realizar auditoria de qualidade ou gerar o relatório em prosa final nesta etapa.
- NG-04: 🟡 O sistema não deve aplicar fallback hardcoded para o parâmetro N caso as variáveis de ambiente ou configurações estejam ausentes.
- NG-05 (v1.1): 🟡 O sistema **não** deve resumir, cortar ou "normalizar" o briefing recebido para caber em qualquer limite interno.
- NG-06 (v1.1): 🟡 O sistema **não** deve ignorar `execution_mode` quando o pipeline assíncrono for disparado.

---

## 5. Usuários e Personas

**Usuário primário:** 🟡 Analista de Research: profissional que submete briefings temáticos via interface ou API e necessita de eixos temáticos claros para direcionar o aprofundamento investigativo.
**Usuário secundário:** 🟡 Redator/Dev integrador: desenvolvedor que orquestra os endpoints modulares em pipelines automatizados de conteúdo e consome os identificadores gerados.
**Persona do sistema:** 🟡 Persona `planejador`: agente de inteligência artificial com diretriz de formular queries objetivas e selecionar os N ângulos investigativos de maior relevância informativa.

**Jornada atual (sem a feature):**
1. 🟡 O analista recebe um briefing aberto e precisa listar manualmente tópicos de busca em motores tradicionais.
2. 🟡 O analista lê títulos de páginas e anota hipóteses em planilhas sem rastreabilidade nem persistência relacional.
3. 🟡 O processo consome horas antes do início da redação ou da validação das hipóteses.

**Jornada futura (com a feature):**
1. 🟡 O usuário submete o payload contendo o tema (integral) para `POST /api/v1/plan`, opcionalmente com `execution_mode`.
2. 🟡 O sistema registra a pesquisa no SQLite permanente e consulta a SERP via Jina (direta ou proxy, indiferentemente).
3. 🟡 O sistema retorna o identificador único da pesquisa e os N pontos formulados prontos para a etapa de busca.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | 🟡 O sistema deve receber uma requisição HTTP POST no endpoint `/api/v1/plan` contendo o campo obrigatório `tema` em formato JSON. | Must | 🟡 Payload com tema válido ⇒ HTTP 201 com objeto contendo `id_pesquisa` e `pontos`. |
| RF-02 | 🟡 O sistema deve criar e persistir o registro da nova pesquisa na tabela `pesquisa` com identificador UUID único e timestamp de criação. | Must | 🟡 Persistência de `id_pesquisa` e `tema` no SQLite. |
| RF-03 | 🟡 O sistema deve consultar a variável de ambiente `N_PONTOS` ou a tabela de credenciais para obter N, interrompendo com HTTP 500 se a configuração estiver ausente. | Must | 🟡 Ausência de `N_PONTOS` ⇒ recusa sem valor implícito em código. |
| RF-04 | 🟡 O sistema deve acionar o modelo LLM OpenAI-compatible com a persona `planejador` e disponibilizar a ferramenta Jina SERP (`s.jina.ai`) para formulação de queries exploratórias. | Must | 🟡 Chamada restrita à consulta SERP, sem downloads de corpo de página. |
| RF-05 | 🟡 O sistema deve processar a resposta do LLM através de parser estruturado e persistir os N pontos na tabela `pontos` com `tema`, `id_pesquisa`, `ponto_id`, `ponto_n`, `ponto` e status inicial `pendente`. | Must | 🟡 Exatamente N registros vinculados ao `id_pesquisa`. |
| RF-06 | 🟡 O sistema deve retornar a lista completa com os N pontos ordenados numericamente com seus identificadores e status. | Must | 🟡 Coleção de pontos com contagem exata igual a N. |

### 6.2 Requisitos da revisão v1.1 (normativos)

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-07 | 🟡 A entrada do planejamento não pode ser truncada nem rejeitada por limite artificial de caracteres. O campo `tema` deve aceitar o briefing integral; limites apenas de sanidade mínima (`min_length=5`). | Must | 🟡 Briefing de 8.000 caracteres é aceito e chega integral ao LLM; nenhum corte silencioso em nenhuma camada. |
| RF-08 | 🟡 O payload de entrada deve aceitar `execution_mode` (`"parallel"` \| `"sequential"`, default `"parallel"`) e propagá-lo ao runner quando `async_execute=true`. | Must | 🟡 `execution_mode="sequential"` + `async_execute=true` ⇒ o runner processa os pontos um por vez; valor inválido ⇒ 422. |
| RF-09 | 🟡 Em reavaliação de plano (pesquisa com pontos e coletas existentes), o contexto do planejador deve incluir o **histórico acumulado** das rodadas de coleta por ponto, sem substituir rodadas anteriores. | Should | 🟡 Ponto com 2 rodadas ⇒ o contexto de reavaliação contém ambas, identificadas por `rodada`. |
| RF-10 | 🟡 A ferramenta Jina usada no planejamento deve ter contrato idêntico nas rotas direta e proxy (paridade total), sem erro de parsing. | Must | 🟡 Mesma query nas duas rotas ⇒ mesmo conjunto de itens parseados. |
| RF-11 | 🟡 A resposta do plano deve expor as preferências efetivas aplicadas, incluindo `execution_mode`. | Should | 🟡 `preferencias.execution_mode` presente no payload de resposta. |

### 6.3 Fluxo Principal (Happy Path)

1. 🟡 O usuário envia `POST /api/v1/plan` com payload JSON informando o `tema` (integral) e, opcionalmente, `execution_mode`.
2. 🟡 O sistema valida o payload, gera `id_pesquisa` e persiste o registro na tabela `pesquisa`.
3. 🟡 O sistema recupera `N_PONTOS` e invoca o LLM com a persona `planejador`.
4. 🟡 O modelo invoca a ferramenta Jina SERP com query derivada do tema e recebe títulos e resumos.
5. 🟡 O modelo seleciona os N pontos mais relevantes, formatando em JSON estrito, e o Avaliador Semântico audita escopo, público, temporalidade e sobreposição de eixos (recebendo a instrução explícita de retornar `sobreposicao_eixos: []` para `N=1` ou todos os $N(N-1)/2$ pares canônicos `1 <= eixo_1 < eixo_2 <= N`).
6. 🟡 O sistema faz o parsing e grava cada registro na tabela `pontos`.
7. 🟡 O sistema retorna HTTP 201 com `id_pesquisa`, `tema`, `n_pontos`, `preferencias` (incluindo `execution_mode`) e a lista detalhada dos pontos.

### 6.4 Fluxos Alternativos

**Fluxo Alternativo A — Pesquisa pré-existente informada:**
1. 🟡 O usuário envia o campo opcional `id_pesquisa` para reaproveitar cadastro administrativo existente.
2. 🟡 O sistema verifica a existência prévia e vincula a geração dos novos pontos ao identificador informado.

**Fluxo Alternativo B — Execução assíncrona do pipeline (v1.1):**
1. 🟡 O usuário envia `async_execute=true` e `execution_mode="sequential"`.
2. 🟡 O sistema persiste a pesquisa, gera os pontos e dispara o runner em background com o modo solicitado.
3. 🟡 O runner executa busca → auditoria → (retries com histórico acumulado) → redação, respeitando o modo.

**Fluxo Alternativo C — Reavaliação de plano com coletas existentes (v1.1):**
1. 🟡 O plano é reavaliado para uma pesquisa que já possui coletas.
2. 🟡 O contexto inclui o histórico acumulado por ponto (RF-09), sem descartar rodadas.

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Performance | Latência total < 120s por requisição | Envolve SERP e inferência LLM |
| RNF-02 | 🟡 Timeout operacional | 600s por chamada externa | Conforme PRD |
| RNF-03 | 🟡 Resiliência de chamadas externas | 1 tentativa inicial + 3 retries com backoff | Aplicado a Jina SERP e LLM |
| RNF-04 | 🟡 Persistência | SQLite permanente | Dados sobrevivem a reinícios |
| RNF-05 | 🟡 Isolamento modular | Monolito modular sem dependência de outros endpoints | Executa de forma autônoma |
| RNF-06 (v1.1) | 🟡 Zero truncamento de entrada | 0 caracteres cortados | Briefing integral |
| RNF-07 (v1.1) | 🟡 Paridade de transporte Jina | 0 divergências direta × proxy | Ver `sdd/proxy-jina-paridade-total.md` |

---

## 8. Design e Interface

**Componentes afetados:**
- 🟡 Rota FastAPI `POST /api/v1/plan`
- 🟡 Módulo de orquestração `core/planner.py`
- 🟡 Cliente de ferramentas `tools/jina_client.py`
- 🟡 Repositório de dados `db/research_repository.py`
- 🟡 Runner do pipeline `core/pipeline_runner.py`

**Comportamento esperado:**
🟡 Interface REST assíncrona, validação Pydantic, códigos semânticos (201 criação, 400 payload inconsistente, 422 validação, 502/504 falhas externas).

### 8.1 Contrato HTTP de entrada (v1.1)

```json
{
  "tema": "briefing integral, sem limite máximo",
  "id_pesquisa": "uuid | null",
  "async_execute": false,
  "callback_url": "https://... | null",
  "n_pontos": 5,
  "personas": ["historiador", "visionario", "cetico", "futurista"],
  "recencia": "auto",
  "execution_mode": "parallel"
}
```

| Campo | Tipo | Regra |
|---|---|---|
| `tema` | string | `min_length=5`; **sem `max_length`** (v1.1) |
| `execution_mode` | `"parallel"` \| `"sequential"` | default `"parallel"`; inválido ⇒ 422 |

### 8.2 Estados da API

- Estado vazio: 🟡 `tema` ausente/curto ⇒ 422 com detalhe do campo.
- Estado de carregamento: 🟡 Conexão ativa durante SERP e inferência, até conclusão ou timeout.
- Estado de erro: 🟡 Resposta estruturada com mensagem, código interno e detalhe da falha externa.
- Estado de sucesso: 🟡 HTTP 201 com objeto JSON completo (pesquisa, pontos, preferências).

---

## 9. Modelo de Dados

```
pesquisa {
  id_pesquisa: string (UUID)
  tema: string                     // briefing integral, sem truncamento
  plano_estruturado: string (JSON) // pedido_original, público, recorte, eixos
  criado_em: timestamp
}

pontos {
  ponto_id: string (UUID)
  id_pesquisa: string (UUID)
  tema: string
  ponto_n: integer                 // 1..N
  ponto: string
  status: string                   // pendente | em_andamento | aprovado | reprovado
  pontos_fracos: string (opcional)
  tentativas: integer              // rodadas de search
  tentativas_auditoria: integer
}
```

**Migrações necessárias:** 🟡 Nenhuma alteração estrutural.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 Jina SERP (`s.jina.ai`) | Obrigatória | HTTP 502 após 1+3 retries; plano abortado sem gravação parcial |
| 🟡 Cloudflare Proxy Worker (opcional) | Opcional | Se configurado, deve ser indistinguível da rota direta |
| 🟡 LLM OpenAI-compatible | Obrigatória | HTTP 502/504 se não responder no limite; transação desfeita |
| 🟡 SQLite Permanente | Obrigatória | Falha crítica de inicialização ou HTTP 500 |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Tema muito curto | 🟡 Menos de 5 caracteres | HTTP 400/422 informando descrição insuficiente |
| EC-02: Jina SERP indisponível | 🟡 503 ou conexão recusada | 3 retries com backoff; persistindo, HTTP 502 |
| EC-03: Timeout do LLM | 🟡 Inferência atinge o limite | Cancela conexão, registra log e retorna HTTP 504 |
| EC-04: Parser falha nos pontos | 🟡 Texto livre sem JSON | Correção sintática; persistindo, descarta transação e retorna HTTP 500 |
| EC-05: `N_PONTOS` ausente | 🟡 Sem configuração | Alerta crítico e recusa sem fallback |
| EC-06 (v1.1): Briefing muito longo | 🟡 Tema com 8.000+ caracteres | **Aceito integralmente**; se exceder janela do provedor, erro explícito de contexto, nunca corte |
| EC-07 (v1.1): `execution_mode` inválido | 🟡 Valor fora do enum | HTTP 422 sem default silencioso |
| EC-08 (v1.1): Proxy diverge da Jina direta | 🟡 Resposta diferente para a mesma query | Erro de contrato; classificado como falha de provedor e reportado como bug bloqueante |

---

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 Bearer token validado pelo middleware FastAPI.
- **Autorização:** 🟡 Qualquer cliente com token de serviço válido pode submeter temas.
- **Dados sensíveis:** 🟡 Textos temáticos de pesquisa aberta; credenciais de Jina e LLM em tabela criptografada ou variáveis de ambiente.
- **Auditoria:** 🟡 Logs estruturados com `id_pesquisa`, tempo decorrido, retries executados, `execution_mode` e códigos de status.

---

## 13. Plano de Rollout

- **Estratégia:** 🟡 Implantação modular em contêiner Docker único, com testes de contrato de rota.
- **Como reverter (rollback):** 🟡 Restauração da versão estável do contêiner e retenção do SQLite permanente.
- **Monitoramento pós-deploy:** 🟡 Taxas 5xx, latência da SERP, consumo de tokens e rejeições de payload nas primeiras 48h.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | 🟡 ✅ RESOLVIDA em v1.1: não há limite de caracteres para `tema`. O limite máximo existente (500) foi removido por contrariar I-2. | Médio | dev-integrador | 2026-10-27 |
| OQ-02 | 🟡 ✅ RESOLVIDA: N pode ser sobrescrito por requisição (`n_pontos`) com precedência sobre `N_PONTOS` do ambiente. | Alto | analista-research | 2026-10-27 |
| OQ-03 (v1.1) | 🟡 ⚠️ ABERTO: qual o limite prático de briefing antes de estourar a janela do LLM planejador, e a mensagem de erro associada? | Médio | dev-integrador | 2026-10-31 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Utilização estrita de resultados SERP sem ler páginas | Baixar os top 3 links | Evita latência e consumo de tokens no planejamento |
| 🟡 Ausência de fallback hardcoded para N_PONTOS | Assumir valor fixo 5 no código | Força definição explícita do ambiente |
| 🟡 Persistência imediata da pesquisa antes da chamada LLM | Gravar só após sucesso | Garante rastreabilidade do identificador mesmo em falha |
| 🟡 (v1.1) Remover `max_length` do `tema` | Manter 500 e documentar | Limite rejeitava briefings reais; entrada não pode perder informação |
| 🟡 (v1.1) `execution_mode` no payload do plano | Configurar só no `/search` | Com `async_execute=true`, o plano dispara o pipeline inteiro; o modo precisa vir da chamada de entrada |
| 🟡 (v1.1) Reavaliação consome histórico acumulado | Reavaliar só com o tema | Evita refazer plano ignorando evidência já coletada |

---

## Apêndice

### Referências
- PRD Deep Research (`_reversa_sdd/prd.md` v2.0 — invariantes I-1..I-5)
- Spec do Proxy Jina (`_reversa_sdd/sdd/proxy-jina-paridade-total.md`)
- Especificação de Personas (`_reversa_sdd/personas.md`)
- Documentação da API Jina Search (`https://s.jina.ai`)

### Mapa de conformidade do código

| Requisito | Arquivo | Ponto | Estado |
|---|---|---|---|
| RF-07 | `app/schemas/plan.py` | `PlanRequest.tema` (`max_length=500`, ~258) | ❌ limite a remover |
| RF-08 | `app/schemas/plan.py` | `PlanRequest` | ❌ campo inexistente |
| RF-08 | `app/api/v1/endpoints/plan.py` | `runner.run(...)` (~262) | ❌ modo não propagado |
| RF-09 | `app/core/planner.py` | contexto de reavaliação | ❌ não consome histórico |
| RF-10 | `app/tools/jina_client.py` | `search` | ✅ contrato único para as duas rotas |

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 1.0 | 2026-10-21 | reversa-spec-sdd | Elaboração inicial da especificação do plano de investigação |
| 1.1 | 2026-10-27 | reversa-spec-sdd | RF-07..RF-11; remoção do limite de 500 chars; `execution_mode` propagado; histórico acumulado em reavaliação; paridade Jina |
