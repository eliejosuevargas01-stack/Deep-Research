# Spec: Endpoint /api/v1/writer — Redação do Dossier

**Versão:** 1.0
**Status:** Planejada
**Autor:** reversa-spec-sdd
**Data:** 2026-10-21
**Reviewers:** Equipe Deep Research

---

## 1. Resumo

🟡 O endpoint `POST /api/v1/writer` constitui a quarta e última etapa do pipeline Deep Research, encarregado de sintetizar os achados investigativos e os pareceres de auditoria em um dossiê analítico abrangente, estruturado e com estrita rastreabilidade de fontes canônicas.
🟡 A funcionalidade recupera todos os dados consolidados da pesquisa, aciona a persona `redator final` via LLM forte OpenAI-compatible, persiste o documento final na tabela `pesquisa` da base SQLite permanente e despacha o resultado via requisição HTTP POST para o webhook de callback configurado.

---

## 2. Contexto e Motivação

**Problema:**
🟡 A redação manual de relatórios de inteligência a partir de fontes dispersas consome dias de trabalho, introduz viés de síntese e frequentemente perde a correspondência direta entre afirmações do texto e URLs originais verificadas.

**Evidências:**
🟡 O PRD demonstra que ferramentas existentes no mercado operam como caixas-pretas que não fornecem dossiês auditados ponto a ponto, impedindo a verificação de fontes primárias e dificultando a integração automatizada com sistemas legados de publicação.

**Por que agora:**
🟡 Concluir o pipeline com geração automática de dossiê auditado e entrega via webhook permite que analistas e desenvolvedores recebam pesquisas finalizadas em menos de 10 minutos, integrando o resultado diretamente aos seus fluxos de trabalho.

---

## 3. Goals (Objetivos)

- [ ] G-01: 🟡 O sistema deve gerar um dossiê completo estruturado em Markdown a partir de todos os pontos auditados da pesquisa.
- [ ] G-02: 🟡 O sistema deve associar e citar explicitamente fontes canônicas verificadas em 100% dos tópicos abordados no documento.
- [ ] G-03: 🟡 O sistema deve persistir o dossiê na tabela `pesquisa` e despachar o documento para o webhook de callback configurado.

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---|---|---|---|
| 🟡 Proporção de pontos com fontes canônicas citadas | 0% | = 100% | 21/10/2026 |
| 🟡 Tempo de resposta da geração e despacho | N/A | < 240s | 21/10/2026 |
| 🟡 Taxa de sucesso no disparo do webhook | 0% | = 100% | 21/10/2026 |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: 🟡 O sistema não deve processar requisições de redação para pesquisas que contenham pontos ainda pendentes de auditoria.
- NG-02: 🟡 O sistema não deve executar novas consultas de busca web ou chamadas ao Jina SERP e Scrapper durante a fase de redação.
- NG-03: 🟡 O sistema não deve aplicar fallback hardcoded para a URL do webhook de callback ou para parâmetros do modelo LLM forte.
- NG-04: 🟡 O sistema não deve alterar as notas, deliberações ou dados brutos armazenados nas tabelas `pontos` e `conteudo_coletado`.

---

## 5. Usuários e Personas

**Usuário primário:** 🟡 Analista de Research: profissional de inteligência que consome o dossiê finalizado e necessita de conclusões fundamentadas com links diretos para cada fonte canônica.
**Usuário secundário:** 🟡 Redator/Dev integrador: desenvolvedor de software que automatiza a recepção do dossiê através do endpoint de webhook para ingestão em repositórios corporativos.
**Persona do sistema:** 🟡 Persona `redator final`: especialista em síntese narrativa analítica, ordenação lógica de argumentos, clareza expositiva e ancoragem estrita em evidências comprovadas.

**Jornada atual (sem a feature):**
1. 🟡 O analista copia fragmentos de texto coletados de dezenas de abas abertas no navegador.
2. 🟡 O analista gasta horas organizando citações bibliográficas e formatando parágrafos em processadores de texto.
3. 🟡 O analista envia o relatório estático por e-mail sem rastreabilidade de entrega nem integração programática.

**Jornada futura (com a feature):**
1. 🟡 O usuário ou rotina automatizada executa requisição `POST /api/v1/writer` informando o `id_pesquisa`.
2. 🟡 O sistema consolida os pontos auditados e invoca a persona `redator final` com o LLM forte.
3. 🟡 O sistema persiste o dossiê na base SQLite permanente e realiza a entrega via POST no webhook cadastrado.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | 🟡 O sistema deve receber uma requisição HTTP POST no endpoint `/api/v1/writer` contendo o campo obrigatório `id_pesquisa` em formato JSON. | Must | 🟡 Dado o envio de payload com identificador válido, Quando o sistema processa a requisição, Então o sistema retorna código HTTP 200 contendo o dossiê e metadados de entrega. |
| RF-02 | 🟡 O sistema deve verificar na tabela `pontos` se todos os N registros associados ao `id_pesquisa` possuem status concluído (`aprovado` ou `reprovado`), rejeitando o processamento com código HTTP 400 caso haja pontos pendentes. | Must | 🟡 Dado pesquisa com pontos sem deliberação de auditoria, Quando o sistema valida o estado no banco, Então o sistema interrompe a execução indicando os identificadores pendentes. |
| RF-03 | 🟡 O sistema deve recuperar e concatenar o tema, os enunciados dos pontos, os pareceres de auditoria e o conteúdo coletado com as respectivas `urls_fonte` canônicas para montar o contexto de redação. | Must | 🟡 Dado o conjunto de pontos finalizados, Quando o sistema consolida as informações, Então o sistema estrutura o contexto textual completo sem omissão de referências. |
| RF-04 | 🟡 O sistema deve invocar o modelo LLM forte OpenAI-compatible parametrizado com a persona `redator final`, recuperando configurações da variável `PERSONAS_CONFIG` ou tabela de credenciais sem fallback hardcoded. | Must | 🟡 Dado o início da síntese, Quando o sistema carrega o prompt da persona, Então o sistema aplica instruções formais de densidade informacional e citação de fontes canônicas. |
| RF-05 | 🟡 O sistema deve processar a saída do LLM forte através de parser estruturado, validando a presença de sumário executivo, desenvolvimento dos eixos temáticos e seção final de referências canônicas. | Must | 🟡 Dado o retorno do modelo, Quando o parser valida o documento, Então o sistema confirma a integridade das seções obrigatórias e extrai o texto do dossiê. |
| RF-06 | 🟡 O sistema deve persistir o dossiê final e a data de conclusão no registro correspondente da tabela `pesquisa` da base SQLite permanente. | Must | 🟡 Dado o dossiê validado, Quando a transação de persistência é confirmada, Então o sistema grava o documento gerado e atualiza o timestamp de encerramento da pesquisa. |
| RF-07 | 🟡 O sistema deve despachar uma requisição HTTP POST contendo o payload estruturado do dossiê para a URL de webhook de callback configurada, registrando status de sucesso ou detalhes de falha. | Must | 🟡 Dado o dossiê persistido em banco, Quando o sistema aciona o webhook de callback, Então o sistema executa o envio com política de retries e registra a resposta HTTP obtida. |

### 6.2 Fluxo Principal (Happy Path)

1. 🟡 O usuário ou serviço orquestrador envia uma requisição `POST /api/v1/writer` contendo o payload com `id_pesquisa`.
2. 🟡 O sistema consulta a tabela `pontos` e confirma que todos os N pontos encontram-se finalizados com status `aprovado` ou `reprovado`.
3. 🟡 O sistema carrega os conteúdos coletados e a lista de URLs canônicas associadas a cada ponto investigado.
4. 🟡 O sistema invoca o LLM forte OpenAI-compatible com as instruções e tom analítico da persona `redator final`.
5. 🟡 O modelo produz o dossiê consolidado em Markdown estruturado, incluindo citações explícitas e notas de rodapé das fontes canônicas.
6. 🟡 O sistema grava o texto integral do dossiê na tabela `pesquisa` da base SQLite permanente.
7. 🟡 O sistema envia requisição HTTP POST contendo o dossiê e metadados para a URL de webhook configurada, retornando código HTTP 200 ao solicitante.

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Presença de pontos reprovados na auditoria:**
1. 🟡 O sistema identifica pontos com status `reprovado` e respectivas anotações no campo `pontos_fracos`.
2. 🟡 O LLM forte redige seção específica de ressalvas metodológicas no dossiê, explicando as limitações factuais encontradas sem descartar o restante da pesquisa.

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Performance | Latência total < 240s por dossiê de 5 pontos | Contempla o raciocínio sintético do LLM forte e despacho de rede |
| RNF-02 | 🟡 Timeout operacional | Limite de 600s por chamada externa | Conforme especificado na seção de restrições do PRD |
| RNF-03 | 🟡 Resiliência de chamadas externas | 1 tentativa inicial + 3 retries com backoff | Aplicado tanto à inferência LLM quanto à chamada ao webhook de callback |
| RNF-04 | 🟡 Persistência | Banco de dados SQLite permanente | O documento gerado deve permanecer consultável mesmo após reinício |
| RNF-05 | 🟡 Isolamento modular | Monolito modular sem dependência de outros endpoints | O endpoint executa de forma autônoma lendo diretamente a base |

---

## 8. Design e Interface

**Componentes afetados:**
- 🟡 Rota FastAPI `POST /api/v1/writer`
- 🟡 Módulo de redação `core/writer.py`
- 🟡 Cliente de webhook `services/webhook_client.py`
- 🟡 Repositório de dados `db/repository.py`

**Comportamento esperado:**
🟡 O endpoint opera como interface REST assíncrona, validando contratos via Pydantic e gerando códigos de status HTTP semânticos (200 para geração bem-sucedida, 400 para pontos incompletos, 404 para pesquisa inexistente, 502/504 para falhas no provedor LLM).

**Estados da UI/API:**
- Estado vazio: 🟡 Requisição sem identificador `id_pesquisa` resulta em código HTTP 422 informando erro de validação.
- Estado de carregamento: 🟡 Conexão ativa durante a inferência sintética e durante as tentativas de entrega no webhook.
- Estado de erro: 🟡 Resposta estruturada com mensagem descritiva do erro, código interno e detalhe de falha externa.
- Estado de sucesso: 🟡 Código HTTP 200 com documento consolidado, contagem de caracteres e status de entrega no webhook.

---

## 9. Modelo de Dados

**Entidades novas ou modificadas:**

```
pesquisa {
  id_pesquisa: string (UUID)       // identificador canônico da investigação
  tema: string                     // tema submetido pelo usuário
  criado_em: timestamp             // data e hora de registro no formato ISO 8601
  dossier_final: string (Markdown) // texto consolidado do dossiê com fontes canônicas
  concluido_em: timestamp          // data e hora da finalização da redação
  webhook_status: string           // entregue | pendente_reenvio | falha_definitiva
}

pontos {
  ponto_id: string (UUID)          // identificador do ponto
  id_pesquisa: string (UUID)       // chave estrangeira referenciando pesquisa
  tema: string                     // tema de referência
  ponto_n: integer                 // número de ordem
  ponto: string                    // enunciado do ponto
  status: string                   // aprovado | reprovado
  pontos_fracos: string (opcional) // fragilidades avaliadas na auditoria
}
```

**Migrações necessárias:** 🟡 Atualização do registro na tabela `pesquisa` preenchendo os campos `dossier_final`, `concluido_em` e `webhook_status` já delimitados no esquema relacional.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 LLM Forte OpenAI-compatible | Obrigatória | Erro HTTP 502 retornado após esgotamento de 1 tentativa + 3 retries; geração do dossiê abortada |
| 🟡 Webhook de Callback do Cliente | Obrigatória | O sistema grava o dossiê no banco com webhook_status igual a falha_definitiva e retorna alerta no HTTP 200 |
| 🟡 SQLite Permanente | Obrigatória | Falha crítica de inicialização da API ou erro HTTP 500 caso o volume esteja inacessível |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Pesquisa com pontos não auditados | 🟡 Presença de registros com status pendente na tabela pontos | O sistema retorna código HTTP 400 informando que todos os pontos devem ser auditados previamente |
| EC-02: Timeout de resposta na inferência do LLM forte | 🟡 Geração textual atinge o limite de 600s | O sistema interrompe o processamento, executa 3 retries com backoff e caso persista retorna HTTP 504 |
| EC-03: Indisponibilidade de rede ou erro 503 no webhook | 🟡 Servidor de destino do webhook retorna código 503 ou recusa conexão | O sistema tenta 3 retries com espera exponencial; se persistir a falha, persiste o dossiê e registra status de falha de envio |
| EC-04: Falha no parser estruturado do dossiê | 🟡 LLM forte emite saída corrompida sem estrutura de seções | O sistema tenta rotina de recuperação sintática; persistindo o problema, cancela gravação e retorna HTTP 500 |
| EC-05: URL de webhook não configurada ou com formato inválido | 🟡 Variável ou registro de configuração do webhook ausente | O sistema recusa o processamento informando ausência de configuração sem aplicar fallback hardcoded |

---

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 Acesso restrito via token de API bearer validado pelo middleware FastAPI.
- **Autorização:** 🟡 Qualquer cliente com token de serviço válido pode solicitar a redação de pesquisas auditadas.
- **Dados sensíveis:** 🟡 O endpoint sintetiza informações públicas; URLs de webhook e credenciais de modelo são preservadas em tabela criptografada ou variáveis de ambiente de contêiner.
- **Auditoria:** 🟡 O sistema registra logs estruturados contendo `id_pesquisa`, tempo total de geração, código HTTP retornado pelo webhook de destino e quantidade de caracteres produzidos.

---

## 13. Plano de Rollout

- **Estratégia:** 🟡 Implantação modular no contêiner padrão da aplicação, validando integração ponta a ponta com endpoints anteriores através de suíte de testes automatizados.
- **Como reverter (rollback):** 🟡 Restauração da versão anterior do contêiner Docker mantendo a integridade do banco SQLite persistido em volume permanente.
- **Monitoramento pós-deploy:** 🟡 Acompanhamento durante as primeiras 48h das taxas de status HTTP 5xx, tempo médio de resposta do webhook de destino e integridade das referências canônicas geradas.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | 🟡 ⚠️ ABERTO: Deve o payload enviado ao webhook de callback incluir assinatura criptográfica HMAC SHA-256 no cabeçalho HTTP? | Médio | dev-integrador | 21/10/2026 |
| OQ-02 | 🟡 ⚠️ ABERTO: Qual política de reenvio deve ser adotada caso o webhook retorne código de rate limit HTTP 429? | Médio | dev-integrador | 21/10/2026 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Exigência de 100% dos pontos finalizados | Permitir redação com pontos parciais pendentes | Assegura que o dossiê reflita a integridade analítica planejada e auditada sem deixar lacunas |
| 🟡 Persistência do dossiê mesmo com falha no webhook | Cancelar a gravação caso o webhook falhe | Preserva o resultado da inferência no banco de dados SQLite permanente para permitir reenvio posterior |
| 🟡 Emprego de Markdown estruturado com notas canônicas | Gerar arquivos binários em formato PDF | Facilita a ingestão por sistemas terceiros e garante legibilidade direta via API |

---

## Apêndice

### Referências
- PRD Deep Research (`_reversa_sdd/prd.md`)
- Especificação de Personas (`_reversa_sdd/personas.md`)
- Documentação da API OpenAI-compatible

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 1.0 | 2026-10-21 | reversa-spec-sdd | Elaboração da especificação formal do endpoint de redação do dossiê |

---

## Relatório de Avaliação de Qualidade

```text
============================================================
  SPEC QUALITY REPORT
  Arquivo: /root/projects/deep-research/_reversa_sdd/sdd/endpoint-redacao-do-dossier.md
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