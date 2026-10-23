# Spec: Endpoint /api/v1/plan — Plano de Investigação

**Versão:** 1.0
**Status:** Planejada
**Autor:** reversa-spec-sdd
**Data:** 2026-10-21
**Reviewers:** Equipe Deep Research

---

## 1. Resumo

🟡 O endpoint `POST /api/v1/plan` constitui a primeira etapa do pipeline de pesquisa profunda Deep Research, encarregado de receber o tema informado pelo usuário, persistir o registro inicial da pesquisa na base SQLite permanente e acionar a persona planejador com suporte de chamadas ao Jina SERP para leitura estrita de resultados de busca, gerando e persistindo N pontos focais de investigação.
🟡 A funcionalidade viabiliza a estruturação prévia do escopo investigativo com base em dados de busca reais sem consumir conteúdo integral de páginas web, estabelecendo a base analítica necessária para as etapas posteriores.

---

## 2. Contexto e Motivação

**Problema:**
🟡 No processo manual, analistas despendem horas para decompor um tema amplo em perguntas e eixos de investigação consistentes, frequentemente resultando em escopos enviesados ou sem fundamentação prévia no ecossistema de informações públicas.

**Evidências:**
🟡 Levantamentos operacionais documentados no PRD indicam que investigações manuais demoram dias e apresentam baixa rastreabilidade, enquanto ferramentas automáticas concorrentes operam como caixas-pretas que não permitem auditar a fase de planejamento nem inspecionar os pontos formulados.

**Por que agora:**
🟡 A automação com controle explícito dos pontos investigativos antes da varredura profunda reduz o consumo desnecessário de tokens e assegura alinhamento antes do processamento paralelo nas fases seguintes.

---

## 3. Goals (Objetivos)

- [ ] G-01: 🟡 O sistema deve gerar exatamente N pontos de investigação estruturados para qualquer tema submetido.
- [ ] G-02: 🟡 O sistema deve persistir a pesquisa e seus pontos na base SQLite permanente com identificadores únicos.
- [ ] G-03: 🟡 O sistema deve restringir o acesso externo da ferramenta de busca na etapa de planejamento exclusivamente a metadados da SERP, impedindo requisições ao scraper de páginas inteiras.

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---|---|---|---|
| 🟡 Taxa de pesquisas com N pontos persistidos | 0% | = 100% | 21/10/2026 |
| 🟡 Tempo de resposta da geração do plano | N/A | < 120s | 21/10/2026 |
| 🟡 Conformidade com restrição de acesso apenas à SERP | 0% | = 100% | 21/10/2026 |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: 🟡 O sistema não deve efetuar raspagem de conteúdo completo ou leitura de páginas web (`s.jina.ai`) durante a execução do endpoint de planejamento.
- NG-02: 🟡 O sistema não deve executar buscas paralelas nem acionar personas especializadas (historiador, visionario, cetico, futurista), reservadas para a etapa de busca.
- NG-03: 🟡 O sistema não deve realizar auditoria de qualidade ou gerar o relatório em prosa final nesta etapa.
- NG-04: 🟡 O sistema não deve aplicar fallback hardcoded para o parâmetro N caso as variáveis de ambiente ou configurações estejam ausentes.

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
1. 🟡 O usuário submete o payload contendo o tema para `POST /api/v1/plan`.
2. 🟡 O sistema registra a pesquisa no SQLite permanente e consulta a SERP via Jina.
3. 🟡 O sistema retorna o identificador único da pesquisa e os N pontos formulados prontos para a etapa de busca.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | 🟡 O sistema deve receber uma requisição HTTP POST no endpoint `/api/v1/plan` contendo o campo obrigatório `tema` em formato JSON. | Must | 🟡 Dado envio de payload com tema válido, Quando o sistema processa a requisição, Então o sistema retorna código HTTP 201 com objeto contendo `id_pesquisa` e `pontos`. |
| RF-02 | 🟡 O sistema deve criar e persistir o registro da nova pesquisa na tabela `pesquisa` com identificador UUID único e timestamp de criação. | Must | 🟡 Dado o recebimento de requisição válida, Quando o sistema persiste o registro, Então o sistema armazena `id_pesquisa` e `tema` no banco de dados SQLite. |
| RF-03 | 🟡 O sistema deve consultar a variável de ambiente `N_PONTOS` ou tabela de credenciais para obter o valor de N, interrompendo o fluxo com código HTTP 500 caso a configuração esteja ausente. | Must | 🟡 Dado a ausência da variável `N_PONTOS` e sem registro configurado, Quando o sistema recebe a chamada, Então o sistema recusa a execução sem assumir valor implícito padrão em código. |
| RF-04 | 🟡 O sistema deve acionar o modelo LLM OpenAI-compatible com a persona `planejador` e disponibilizar a ferramenta Jina SERP para formulação de queries exploratórias. | Must | 🟡 Dado o acionamento do LLM, Quando a ferramenta de busca é invocada pelo sistema, Então o sistema restringe a chamada à consulta SERP sem efetuar downloads de corpo de páginas. |
| RF-05 | 🟡 O sistema deve processar a resposta do LLM através de parser estruturado e persistir os N pontos na tabela `pontos` com os campos `tema`, `id_pesquisa`, `ponto_id`, `ponto_n`, `ponto` e status inicial `pendente`. | Must | 🟡 Dado o plano gerado pelo LLM, Quando o sistema conclui a extração, Então o sistema persiste exatamente N registros vinculados ao `id_pesquisa`. |
| RF-06 | 🟡 O sistema deve retornar ao cliente a lista completa com os N pontos ordenados numericamente com seus respectivos identificadores e status. | Must | 🟡 Dado a persistência dos pontos concluída, Quando o sistema serializa a resposta, Então o sistema exibe a coleção de pontos e contagem exata igual a N. |

### 6.2 Fluxo Principal (Happy Path)

1. 🟡 O usuário envia uma requisição `POST /api/v1/plan` com payload JSON informando o `tema`.
2. 🟡 O sistema valida o payload, gera um identificador único `id_pesquisa` e persiste o registro na tabela `pesquisa`.
3. 🟡 O sistema recupera a configuração de `N_PONTOS` e invoca o LLM OpenAI-compatible configurado com a persona `planejador`.
4. 🟡 O modelo invoca a ferramenta Jina SERP enviando query derivada do tema e recebe títulos e resumos da SERP.
5. 🟡 O modelo seleciona os N pontos mais investigativos e relevantes, formatando em estrutura JSON estrita.
6. 🟡 O sistema realiza o parsing dos pontos gerados e grava cada registro na tabela `pontos` do SQLite.
7. 🟡 O sistema retorna resposta HTTP 201 contendo `id_pesquisa`, `tema`, `n_pontos` e a lista detalhada dos pontos criados.

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Tema com identificador de pesquisa pré-existente fornecido:**
1. 🟡 O usuário envia o campo opcional `id_pesquisa` no payload para reaproveitar cadastro administrativo existente.
2. 🟡 O sistema verifica a existência prévia na tabela `pesquisa` e vincula a geração dos novos pontos ao identificador informado.

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Performance | Latência total < 120s por requisição | Envolve chamada externa à SERP e inferência LLM |
| RNF-02 | 🟡 Timeout operacional | Limite de 600s por chamada externa | Conforme especificado na seção de restrições do PRD |
| RNF-03 | 🟡 Resiliência de chamadas externas | 1 tentativa inicial + 3 retries com backoff | Aplicado a requisições HTTP para Jina SERP e endpoint LLM |
| RNF-04 | 🟡 Persistência | Banco de dados SQLite permanente | Os dados devem persistir entre reinicializações do contêiner |
| RNF-05 | 🟡 Isolamento modular | Monolito modular sem dependência de outros endpoints | O endpoint executa de forma autônoma sem exigir chamadas ativas a outros serviços |

---

## 8. Design e Interface

**Componentes afetados:**
- 🟡 Rota FastAPI `POST /api/v1/plan`
- 🟡 Módulo de orquestração `core/planner.py`
- 🟡 Cliente de ferramentas `tools/jina_serp.py`
- 🟡 Repositório de dados `db/repository.py`

**Comportamento esperado:**
🟡 O endpoint opera como interface REST assíncrona, validando contratos via Pydantic e gerando códigos de status HTTP semânticos (201 para criação bem-sucedida, 400 para payload inconsistente, 502/504 para falhas externas).

**Estados da UI/API:**
- Estado vazio: 🟡 Payload com tema vazio ou ausente retorna código HTTP 422 com detalhamento do campo faltante.
- Estado de carregamento: 🟡 Processamento das chamadas externas de SERP e inferência mantido sob conexão HTTP ativa até conclusão ou timeout.
- Estado de erro: 🟡 Resposta estruturada com mensagem descritiva do erro, código interno e detalhe de falha externa.
- Estado de sucesso: 🟡 Código HTTP 201 contendo objeto JSON completo com identificador de pesquisa e array de pontos.

---

## 9. Modelo de Dados

**Entidades novas ou modificadas:**

```
pesquisa {
  id_pesquisa: string (UUID)       // identificador canônico da investigação
  tema: string                     // tema submetido pelo usuário
  criado_em: timestamp             // data e hora de registro no formato ISO 8601
}

pontos {
  ponto_id: string (UUID)          // identificador exclusivo do ponto
  id_pesquisa: string (UUID)       // chave estrangeira referenciando pesquisa.id_pesquisa
  tema: string                     // cópia do tema para desnormalização e consulta
  ponto_n: integer                 // número sequencial do ponto (1 até N)
  ponto: string                    // descrição textual do ponto de investigação
  status: string                   // pendente | em_andamento | aprovado | reprovado
  pontos_fracos: string (opcional) // lacunas identificadas em etapas posteriores
}
```

**Migrações necessárias:** 🟡 Não há migrações legadas; o esquema deve ser inicializado pelo SQLAlchemy no SQLite permanente na inicialização do serviço.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 Jina SERP Tool | Obrigatória | Erro HTTP 502 retornado após esgotamento de 1 tentativa + 3 retries; geração do plano abortada sem gravação parcial |
| 🟡 LLM OpenAI-compatible | Obrigatória | Erro HTTP 502 ou 504 caso o provedor LLM não responda em 600s; transação desfeita |
| 🟡 SQLite Permanente | Obrigatória | Falha crítica de inicialização da API ou erro HTTP 500 caso o arquivo em disco esteja inacessível |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Tema excessivamente curto ou ambíguo | 🟡 Entrada com menos de 5 caracteres | O sistema retorna código HTTP 400 informando que o tema deve conter descrição suficiente |
| EC-02: Indisponibilidade de rede com Jina SERP | 🟡 Jina retorna erro 503 ou conexão recusa | O sistema executa 3 retries com backoff exponencial; persistindo o erro, retorna HTTP 502 com detalhes |
| EC-03: Timeout de chamada externa do LLM | 🟡 Inferência atinge o limite de 600s | O sistema cancela a conexão, registra log estruturado e retorna HTTP 504 de timeout |
| EC-04: Falha no parser de pontos gerados | 🟡 LLM responde texto livre sem respeitar formato JSON | O sistema aciona rotina de correção sintática; persistindo a falha, descarta transação e retorna HTTP 500 |
| EC-05: Variável de ambiente N_PONTOS ausente | 🟡 Inicialização sem definição de N_PONTOS e sem registro configurado | O sistema emite alerta crítico no boot e recusa a operação sem aplicar fallback hardcoded |

---

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 Acesso restrito via token de API bearer validado pelo middleware FastAPI.
- **Autorização:** 🟡 Qualquer cliente com token de serviço válido pode submeter temas de pesquisa.
- **Dados sensíveis:** 🟡 O endpoint processa textos temáticos de pesquisa aberta; credenciais de acesso a Jina e LLM são mantidas em tabela criptografada ou variáveis de ambiente de contêiner.
- **Auditoria:** 🟡 O sistema registra logs estruturados de cada requisição contendo `id_pesquisa`, tempo decorrido, número de retries executados e códigos de status gerados.

---

## 13. Plano de Rollout

- **Estratégia:** 🟡 Implantação direta modular em contêiner Docker único com arquitetura monolito, validando os contratos de rota via testes automatizados.
- **Como reverter (rollback):** 🟡 Restauração da versão estável do contêiner Docker e retenção do arquivo de banco de dados SQLite permanente para integridade histórica.
- **Monitoramento pós-deploy:** 🟡 Acompanhamento durante as primeiras 48h das taxas de erro HTTP 5xx, latência média das requisições para a API Jina e consumo de tokens por pesquisa.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | 🟡 ⚠️ ABERTO: Qual o limite de caracteres máximo aceito para o campo `tema` a fim de evitar estouro de contexto no LLM? | Médio | dev-integrador | 21/10/2026 |
| OQ-02 | 🟡 ⚠️ ABERTO: Deve ser permitido ao usuário sobrescrever o valor padrão de N por requisição ou apenas via variável de ambiente global? | Alto | analista-research | 21/10/2026 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Utilização estrita de resultados SERP sem ler páginas | Efetuar download completo dos top 3 links | Evita latência desnecessária e consumo de tokens na fase de planejamento prévio |
| 🟡 Ausência de fallback hardcoded para N_PONTOS | Assumir valor fixo 5 diretamente no código | Força definição explícita do ambiente operacional conforme exigência do PRD |
| 🟡 Persistência imediata da pesquisa antes da chamada LLM | Gravar somente após retorno bem-sucedido | Garante rastreabilidade do identificador mesmo em cenários de falha na inferência |

---

## Apêndice

### Referências
- PRD Deep Research (`_reversa_sdd/prd.md`)
- Especificação de Personas (`_reversa_sdd/personas.md`)
- Documentação da API Jina SERP (`https://jina.ai`)

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 1.0 | 2026-10-21 | reversa-spec-sdd | Elaboração inicial da especificação formal do endpoint de plano de investigação |

---

## Relatório de Avaliação de Qualidade

```text
============================================================
  SPEC QUALITY REPORT
  Arquivo: /root/projects/deep-research/_reversa_sdd/sdd/endpoint-plano-de-investigacao.md
============================================================

  SCORE TOTAL: 100.0/100  —  ⭐ Excelente — Pronta para implementação

  BREAKDOWN POR DIMENSÃO:
  Dimensão             Score      Peso     Contribuição
  --------------------------------------------------
  Completude           100%       30%     30.0/pt
  Testabilidade        100%       25%     25.0/pt
  Clareza              100%       20%     20.0/pt
  Escopo               100%       15%     15.0/pt
  Edge Cases           100%       10%     10.0/pt

  ✅ PONTOS FORTES:
     ✅ Seção 1 (Resumo) presente e preenchida
     ✅ Seção 2 (Contexto) presente e preenchida
     ✅ Seção 3 (Goals) presente e preenchida
     ✅ Seção 4 (Non-Goals) presente e preenchida
     ✅ Seção 5 (Usuários) presente e preenchida

============================================================
```
