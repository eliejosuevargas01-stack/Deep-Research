# Requirements: Pesquisa Profunda MVP

> Identificador: `001-pesquisa-profunda-mvp`
> Data: `2026-10-21`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

O sistema entrega um pipeline modular de pesquisa profunda na internet composto por quatro etapas independentes: planejamento, busca, auditoria e redação. A solução atende analistas de pesquisa e desenvolvedores integradores, eliminando o processo manual de múltiplos dias em investigações sem auditoria e relatórios sem rastreabilidade. O fluxo assegura a produção de um dossiê analítico completo com fontes canônicas verificadas e pontos investigados auditados em menos de dez minutos com baixo custo operacional.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/prd.md#1-visao-geral` | Visão geral do pipeline de pesquisa profunda composto por quatro etapas em monólito modular | 🟡 |
| `_reversa_sdd/prd.md#2-problema` | Dores operacionais de pesquisas manuais demoradas, ausência de auditoria e relatórios sem rastreabilidade | 🟡 |
| `_reversa_sdd/prd.md#3-personas-alvo` | Definição das personas Analista de Research e Redator/Dev integrador e das sete personas do sistema | 🟡 |
| `_reversa_sdd/prd.md#4-metricas-de-sucesso` | Metas de 100% de fontes canônicas rastreadas, N pontos aprovados e tempo de execução inferior a 10 minutos | 🟡 |
| `_reversa_sdd/prd.md#5-escopo-in` | Delimitação do escopo MVP com quatro endpoints operacionais principais e suporte a credenciais e configurações | 🟡 |
| `_reversa_sdd/prd.md#6-nao-objetivos-out` | Diretrizes de não complicar a pesquisa, independência entre etapas e ausência de compliance regulatório no MVP | 🟡 |
| `_reversa_sdd/prd.md#7-requisitos-funcionais` | Especificação funcional dos estágios de plano, busca, auditoria, redação e administração | 🟡 |
| `_reversa_sdd/prd.md#8-modelo-de-dados-tabelas` | Definição das tabelas pesquisa, pontos, conteudo_coletado e credenciais criptografadas | 🟡 |
| `_reversa_sdd/prd.md#9-variaveis-de-ambiente` | Configuração estrita de N pontos, personas e credenciais por variáveis de ambiente sem fallback implícito | 🟡 |
| `_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais` | Restrições de timeout de 600s, 1+3 retentativas e persistência relacional permanente | 🟡 |
| `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md#3-goals-objetivos` | Metas operacionais do endpoint de planejamento e geração estruturada de N pontos | 🟡 |
| `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md#4-non-goals-fora-do-escopo` | Proibição de raspagem completa de páginas web na etapa de plano | 🟡 |
| `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md#61-requisitos-principais` | Especificação funcional do endpoint POST /api/v1/plan e restrição estrita a metadados da SERP | 🟡 |
| `_reversa_sdd/sdd/endpoint-busca-com-personas.md#3-goals-objetivos` | Metas de processamento paralelo dos N pontos, desduplicação de URLs e integridade sem truncamento | 🟡 |
| `_reversa_sdd/sdd/endpoint-busca-com-personas.md#61-requisitos-principais` | Especificação funcional do endpoint POST /api/v1/search e orquestração de quatro personas analíticas | 🟡 |
| `_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md#3-goals-objetivos` | Metas de validação analítica através de doze perguntas estruturadas e atualização relacional | 🟡 |
| `_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md#61-requisitos-principais` | Especificação funcional do endpoint POST /api/v1/audit, checklist de doze critérios e deliberação | 🟡 |
| `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#3-goals-objetivos` | Metas de consolidação do dossiê em Markdown com fontes canônicas e despacho via webhook | 🟡 |
| `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#4-non-goals-fora-do-escopo` | Bloqueio de redação para pesquisas com pontos não auditados e ausência de buscas adicionais | 🟡 |
| `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#61-requisitos-principais` | Especificação funcional do endpoint POST /api/v1/writer e envio do relatório final ao webhook de callback | 🟡 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Analista de Research | Obter investigações aprofundadas e auditadas com fontes canônicas em menos de 10 minutos | O analista envia o tema da pesquisa via interface ou API, acompanha os pontos formulados e recebe o dossiê com total rastreabilidade |
| Redator/Dev integrador | Integrar o pipeline modular de pesquisa em serviços externos e automatizar a recepção do dossiê | O desenvolvedor cadastra configurações, invoca cada endpoint sequencialmente e consome o resultado final via webhook de callback |
| Persona do sistema: Planejador | Formular consultas e decompor o tema em N eixos focais de investigação | O agente de planejamento lê metadados da SERP (Search Engine Results Page) e seleciona os N pontos mais relevantes sem abrir páginas |
| Personas do sistema: Historiador, Visionário, Cético, Futurista | Executar busca aprofundada na web sob quatro perspectivas conceituais distintas | Os agentes buscam conteúdos em paralelo, descartam URLs já consultadas na pesquisa e consolidam o texto coletado integralmente |
| Persona do sistema: Auditor | Avaliar a consistência factual e metodológica do conteúdo coletado | O auditor submete o conteúdo de cada ponto a doze perguntas de qualidade, emitindo deliberação de aprovação ou reprovação |
| Persona do sistema: Redator final | Redigir o dossiê estruturado com síntese analítica e marcação de fontes canônicas | O redator final sintetiza os pontos aprovados e reprovados em Markdown e prepara a entrega para o webhook cadastrado |

## 4. Regras de negócio novas ou alteradas

1. **RN-01: Modularidade e Independência Operacional dos Endpoints** 🟡
   - Origem no legado: `_reversa_sdd/prd.md#6-nao-objetivos-out`
   - Tipo: nova
   - O sistema deve operar como monólito modular composto por quatro endpoints principais (`/api/v1/plan`, `/api/v1/search`, `/api/v1/audit`, `/api/v1/writer`), onde cada endpoint executa sua etapa de forma independente e assíncrona, persistindo o estado intermediário na base de dados relacional.

2. **RN-02: Configuração Estrita de Parâmetros sem Fallback Implícito** 🟡
   - Origem no legado: `_reversa_sdd/prd.md#9-variaveis-de-ambiente`
   - Tipo: nova
   - O sistema deve carregar a quantidade N de pontos por pesquisa (padrão operacional 5) e a definição das sete personas exclusivamente a partir de variáveis de ambiente ou tabela de configuração; a ausência dessas definições deve resultar em erro explícito de configuração sem assunção de valores embutidos em código.

3. **RN-03: Restrição de Acesso Exclusivo à SERP na Etapa de Planejamento** 🟡
   - Origem no legado: `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md#4-non-goals-fora-do-escopo`
   - Tipo: nova
   - O endpoint de planejamento (`/api/v1/plan`) deve utilizar a ferramenta de busca externa estritamente para leitura de metadados da SERP (Search Engine Results Page), sendo vedado o download ou a raspagem do conteúdo integral de páginas web durante esta fase.

4. **RN-04: Deduplicação Obrigatória de URLs por Identificador de Pesquisa** 🟡
   - Origem no legado: `_reversa_sdd/sdd/endpoint-busca-com-personas.md#3-goals-objetivos`
   - Tipo: nova
   - A etapa de busca (`/api/v1/search`) deve validar previamente toda URL candidata contra o histórico de endereços já lidos para o respectivo `id_pesquisa`, descartando requisições repetidas de raspagem de páginas já consultadas.

5. **RN-05: Preservação Integral de Conteúdo Coletado sem Truncamento** 🟡
   - Origem no legado: `_reversa_sdd/sdd/endpoint-busca-com-personas.md#61-requisitos-principais`
   - Tipo: nova
   - O sistema deve armazenar na tabela `conteudo_coletado` a totalidade do texto retornado pela ferramenta de raspagem, sendo vedado o truncamento sintático ou corte artificial de tamanho, associando todas as URLs canônicas de origem.

6. **RN-06: Avaliação Crítica Baseada em Doze Perguntas de Qualidade** 🟡
   - Origem no legado: `_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md#61-requisitos-principais`
   - Tipo: nova
   - O endpoint de auditoria (`/api/v1/audit`) deve submeter o conteúdo de cada ponto de investigação a um checklist estruturado de doze critérios de qualidade (clareza temática, corroboração canônica, atualidade, ausência de contradições, embasamento factual, aderência ao escopo, profundidade, precisão numérica, neutralidade, densidade de evidências, declaração de incertezas e solidez lógica), definindo o status como `aprovado` ou `reprovado` e registrando os pontos fracos identificados.

7. **RN-07: Bloqueio de Redação com Pontos Pendentes de Auditoria** 🟡
   - Origem no legado: `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#4-non-goals-fora-do-escopo`
   - Tipo: nova
   - O endpoint de redação (`/api/v1/writer`) deve recusar o processamento para pesquisas que possuam qualquer ponto com status pendente de auditoria, exigindo que todos os N pontos cadastrados possuam parecer definitivo registrado no banco de dados.

8. **RN-08: Rastreabilidade Total de Fontes Canônicas no Dossiê Final** 🟡
   - Origem no legado: `_reversa_sdd/prd.md#4-metricas-de-sucesso`
   - Tipo: nova
   - O dossiê final gerado pelo redator deve referenciar explicitamente URLs de fontes canônicas em 100% dos tópicos temáticos abordados, incorporando sumário executivo, desenvolvimento analítico dos pontos investigados e listagem canônica de referências.

9. **RN-09: Despacho Automático para Webhook de Notificação** 🟡
   - Origem no legado: `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#61-requisitos-principais`
   - Tipo: nova
   - Após persistir o dossiê final na base de dados, o endpoint de redação deve realizar uma requisição HTTP POST transmitindo o documento estruturado para a URL de webhook de callback configurada para a pesquisa.

10. **RN-10: Criptografia de Credenciais com Precedência de Ambiente** 🟡
    - Origem no legado: `_reversa_sdd/prd.md#8-modelo-de-dados-tabelas`
    - Tipo: nova
    - Chaves de API, endereços de base URL e parâmetros sensíveis gravados na base relacional devem permanecer criptografados em repouso; variáveis de ambiente configuradas no contêiner possuem precedência de leitura imediata sobre os registros do banco.

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Receber requisições em `POST /api/v1/plan` com o campo obrigatório `tema` e gerar N pontos de investigação | Must | Retorna HTTP 201 com `id_pesquisa` e lista contendo exatamente N pontos formulados via SERP sem raspar páginas web | 🟡 |
| RF-02 | Gravar o registro inicial da pesquisa e os pontos gerados na base relacional SQLite permanente | Must | Registra `id_pesquisa` e `tema` na tabela `pesquisa`, e grava N registros na tabela `pontos` com status inicial `pendente` | 🟡 |
| RF-03 | Executar varredura profunda web em paralelo para todos os pontos pendentes via `POST /api/v1/search` | Must | Processa concorrentemente os N pontos aplicando as personas analíticas e retorna HTTP 200 com sumário de processamento | 🟡 |
| RF-04 | Filtrar e desduplicar URLs consultadas por `id_pesquisa` durante a etapa de busca | Must | Impede chamadas redundantes ao serviço de raspagem para endereços já registrados no histórico da pesquisa | 🟡 |
| RF-05 | Persistir texto integral coletado e lista de URLs na tabela `conteudo_coletado` | Must | Grava os campos `tema`, `id_pesquisa`, `ponto`, `ponto_id`, `conteudo_coletado`, `urls_lidas` e `urls_fonte` sem truncamento textual | 🟡 |
| RF-06 | Submeter cada ponto coletado à avaliação das doze perguntas de qualidade via `POST /api/v1/audit` | Must | Processa o lote de pontos, atribui status `aprovado` ou `reprovado`, grava `pontos_fracos` na tabela `pontos` e retorna HTTP 200 | 🟡 |
| RF-07 | Rejeitar processamento de auditoria para pesquisas sem conteúdo previamente coletado | Must | Retorna código HTTP 400 ou 404 quando a pesquisa não possui registros vinculados na tabela `conteudo_coletado` | 🟡 |
| RF-08 | Consolidar os pontos investigados e gerar dossiê estruturado em Markdown via `POST /api/v1/writer` | Must | Gera dossiê com sumário executivo, desenvolvimento analítico e 100% de fontes canônicas rastreadas, persistindo o texto na tabela `pesquisa` | 🟡 |
| RF-09 | Rejeitar a geração do dossiê caso existam pontos com status pendente de auditoria | Must | Retorna código HTTP 400 indicando a lista de pontos que ainda não receberam deliberação na auditoria | 🟡 |
| RF-10 | Despachar o dossiê concluído via requisição HTTP POST para webhook de callback cadastrado | Must | Envia payload estruturado com o dossiê para a URL de webhook configurada e registra o status de entrega | 🟡 |
| RF-11 | Disponibilizar rotas administrativas para gestão de credenciais e parâmetros operacionais | Should | Permite cadastrar, atualizar e consultar configurações de chaves de API, base URLs e preferências | 🟡 |
| RF-12 | Criptografar credenciais em repouso e aplicar precedência de variáveis de ambiente do contêiner | Must | Armazena dados sensíveis cifrados no SQLite e aplica substituição automática por variáveis presentes no ambiente | 🟡 |

## 6. Requisitos Não Funcionais

| ID | Tipo | Requisito | Evidência ou justificativa | Confidência |
|----|------|-----------|----------------------------|-------------|
| RNF-01 | Desempenho | Tempo total de execução do ciclo completo inferior a 10 minutos (600 segundos) | Métrica estipulada no PRD para ciclo ponta a ponta (`_reversa_sdd/prd.md#4-metricas-de-sucesso`) | 🟡 |
| RNF-02 | Desempenho | Latência de processamento do endpoint `/api/v1/plan` inferior a 120 segundos | Meta de resposta estabelecida na especificação técnica (`_reversa_sdd/sdd/endpoint-plano-de-investigacao.md#3-goals-objetivos`) | 🟡 |
| RNF-03 | Desempenho | Latência de processamento da busca paralela `/api/v1/search` inferior a 300 segundos | Meta de resposta concorrente para N pontos (`_reversa_sdd/sdd/endpoint-busca-com-personas.md#3-goals-objetivos`) | 🟡 |
| RNF-04 | Desempenho | Latência de processamento da auditoria `/api/v1/audit` inferior a 180 segundos | Meta de tempo para avaliação das doze perguntas (`_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md#3-goals-objetivos`) | 🟡 |
| RNF-05 | Desempenho | Latência de processamento da redação e webhook `/api/v1/writer` inferior a 240 segundos | Meta para geração de texto extenso e envio HTTP (`_reversa_sdd/sdd/endpoint-redacao-do-dossier.md#3-goals-objetivos`) | 🟡 |
| RNF-06 | Resiliência | Política de 1 tentativa inicial mais 3 retentativas automáticas com backoff para integrações externas | Requisito de robustez para falhas de rede (`_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais`) | 🟡 |
| RNF-07 | Confiabilidade | Limite de tempo de espera (timeout) operacional de 600 segundos por chamada externa | Diretriz técnica contra travamento de requisições (`_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais`) | 🟡 |
| RNF-08 | Persistência | Base de dados SQLite permanente configurada em volume que sobrevive a reinicializações | Garantia de sobrevivência de dados sem perda de estado (`_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais`) | 🟡 |
| RNF-09 | Segurança | Tabela de credenciais criptografada em repouso com prioridade para variáveis de ambiente | Proteção de credenciais contra acesso indevido (`_reversa_sdd/prd.md#8-modelo-de-dados-tabelas`) | 🟡 |
| RNF-10 | Arquitetura | Monólito modular com quatro endpoints operacionais principais e acoplamento fraco | Diretriz do PRD para isolamento de responsabilidades (`_reversa_sdd/prd.md#6-nao-objetivos-out`) | 🟡 |
| RNF-11 | Compatibilidade | Chamadas de modelos de linguagem restritas a APIs compatíveis com o padrão OpenAI | Padrão técnico para modelos leves e fortes (`_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais`) | 🟡 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Geração do plano de investigação com restrição à SERP (Happy Path)
  Dado que o usuário envia uma requisição POST para "/api/v1/plan" com o tema "Impacto da IA na Educação"
  E que a variável de ambiente define N igual a 5
  Quando o sistema processa a requisição consultando exclusivamente metadados da SERP
  Então o sistema retorna código HTTP 201
  E o corpo da resposta contém "id_pesquisa" no formato UUID
  E a lista "pontos" contém exatamente 5 itens persistidos no banco de dados com status "pendente"

Cenário: Falha no planejamento por ausência de configuração de N pontos (Negative Path)
  Dado que a variável de ambiente de N pontos está ausente e não há valor cadastrado na tabela de configuração
  Quando o usuário envia uma requisição POST para "/api/v1/plan" informando um tema válido
  Então o sistema rejeita a operação com código HTTP 500
  E o sistema não assume valor padrão implícito em código

Cenário: Busca paralela com filtragem de URLs duplicadas (Happy Path)
  Dado que existem 5 pontos associados a um "id_pesquisa" válido na tabela "pontos"
  Quando o usuário envia uma requisição POST para "/api/v1/search" informando o "id_pesquisa"
  Então o sistema executa a coleta dos 5 pontos em paralelo aplicando as personas do sistema
  E o sistema descarta requisições de raspagem para URLs já consultadas na pesquisa corrente
  E o sistema persiste o texto integral sem truncamento na tabela "conteudo_coletado"
  E o sistema retorna código HTTP 200 com o resumo das coletas

Cenário: Rejeição de busca para pesquisa inexistente (Negative Path)
  Dado que o identificador "id_pesquisa" informado não existe na base de dados
  Quando o usuário submete uma requisição POST para "/api/v1/search"
  Então o sistema responde com código HTTP 404
  E nenhuma tarefa de busca externa é disparada

Cenário: Auditoria de qualidade com aplicação das doze perguntas (Happy Path)
  Dado que o "id_pesquisa" informado possui registros concluídos na tabela "conteudo_coletado"
  Quando o usuário envia uma requisição POST para "/api/v1/audit"
  Então o sistema submete cada ponto à avaliação das doze perguntas de qualidade via modelo de linguagem
  E o sistema atualiza a tabela "pontos" com status "aprovado" ou "reprovado" para cada registro
  E o sistema persiste as descrições de fragilidades no campo "pontos_fracos" dos itens reprovados
  E o sistema retorna código HTTP 200 com a contagem de aprovações e reprovações

Cenário: Rejeição de auditoria para pesquisa sem conteúdo coletado (Negative Path)
  Dado que uma pesquisa foi cadastrada mas não possui registros na tabela "conteudo_coletado"
  Quando o usuário envia uma requisição POST para "/api/v1/audit" informando o "id_pesquisa"
  Então o sistema recusa a execução retornando código HTTP 400
  E o corpo da resposta informa a pendência da etapa de busca

Cenário: Redação de dossiê analítico com rastreabilidade canônica e despacho via webhook (Happy Path)
  Dado que todos os 5 pontos de uma pesquisa possuem parecer definitivo de auditoria
  Quando o usuário ou serviço envia uma requisição POST para "/api/v1/writer" informando o "id_pesquisa"
  Então o sistema gera o dossiê analítico em Markdown referenciando fontes canônicas em 100% dos tópicos
  E o sistema grava o texto integral do documento na tabela "pesquisa"
  E o sistema despacha o dossiê via requisição HTTP POST para a URL de webhook cadastrada
  E o sistema retorna código HTTP 200 com os dados de entrega

Cenário: Rejeição de redação quando existem pontos pendentes de auditoria (Negative Path)
  Dado que uma pesquisa possui pelo menos 1 ponto com status "pendente" na tabela "pontos"
  Quando o usuário envia uma requisição POST para "/api/v1/writer" informando o "id_pesquisa"
  Então o sistema rejeita a solicitação com código HTTP 400
  E o sistema não invoca o modelo de redação nem aciona o webhook de callback

Cenário: Gestão de credenciais e parâmetros operacionais via endpoint administrativo (Happy Path)
  Dado que o integrador submete novas chaves de API e URL base para o endpoint administrativo
  Quando a requisição administrativa é validada e processada
  Então o sistema armazena os valores criptografados na tabela "credenciais"
  E o sistema retorna código HTTP 200 confirmando a persistência

Cenário: Precedência de variáveis de ambiente sobre credenciais criptografadas (Happy Path)
  Dado que uma chave de API encontra-se gravada de forma criptografada na tabela "credenciais"
  E que o contêiner possui uma variável de ambiente definida para a mesma chave de API
  Quando qualquer endpoint do pipeline inicializa o cliente de integração externa
  Então o sistema utiliza o valor fornecido pela variável de ambiente do contêiner
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (Planejamento via `/api/v1/plan` com SERP) | Must | Funcionalidade essencial para estruturar o escopo investigativo inicial |
| RF-02 (Persistência relacional permanente de pontos) | Must | Garantia fundamental de sobrevivência de dados e rastreabilidade entre etapas |
| RF-03 (Busca paralela com personas analíticas) | Must | Núcleo de coleta informacional multifacetada do pipeline |
| RF-04 (Deduplicação de URLs por pesquisa) | Must | Controle indispensável para prevenir desperdício de requisições e custos de scraping |
| RF-05 (Armazenamento sem truncamento textual) | Must | Necessário para assegurar integridade de dados e auditoria factual |
| RF-06 (Auditoria crítica com doze perguntas) | Must | Diferencial central do produto contra ferramentas concorrentes tipo caixa-preta |
| RF-07 (Validação de pré-requisitos para auditoria) | Must | Garante consistência lógica e integridade de fluxo do monólito modular |
| RF-08 (Geração de dossiê com fontes canônicas) | Must | Principal entrega de valor final prometida ao Analista de Research |
| RF-09 (Bloqueio de redação com pendências) | Must | Impede a produção de relatórios parciais ou desprovidos de crivo de qualidade |
| RF-10 (Despacho HTTP POST para webhook de callback) | Must | Viabiliza a integração automatizada com pipelines externos de publicação |
| RF-12 (Criptografia de credenciais e precedência de env) | Must | Requisito indispensável de segurança para dados sensíveis em repouso e produção |
| RF-11 (Endpoints administrativos de configuração) | Should | Facilita a manutenção operacional e atualização de parâmetros em tempo de execução |
| RNF-01 a RNF-05 (Metas de tempo e latência) | Should | Diretrizes de qualidade de serviço para manter o ciclo completo abaixo de 10 minutos |
| RNF-06 (Resiliência 1+3 retentativas) | Must | Proteção contra intermitências transitórias de rede nas chamadas externas |
| RNF-07 (Timeout operacional 600s) | Must | Previne travamentos e bloqueios indefinidos de threads e conexões |
| RNF-08 (Persistência SQLite permanente) | Must | Sobrevivência de dados a redeploys de contêineres e falhas de processo |
| RNF-09 (Criptografia em repouso) | Must | Garantia de confidencialidade de segredos e chaves de API |
| RNF-10 (Monólito modular) | Must | Arquitetura isolada que permite evolução e testes autônomos por etapa |
| RNF-11 (Compatibilidade OpenAI) | Must | Padronização de protocolo de comunicação com modelos de linguagem |

## 9. Esclarecimentos

> Nenhuma sessão de dúvidas registrada ainda. Rode `/reversa-clarify` quando houver dúvida pendente.

## 10. Lacunas

### Resolvidas em 2026-10-21 via `/reversa-clarify` (respostas do usuário no chat)

- 🟡 **Teto de consumo de tokens/custo por pesquisa: não existe teto.** Resposta explícita do usuário: "não". Nenhum mecanismo de corte orçamentário automático é implementado nesta feature. Registrado como premissa de aceitação de risco, não como requisito ausente. O custo é controlado apenas pelos limites já definidos no PRD: no máximo 3 queries por ponto no endpoint `search` e no máximo 10 URLs lidas por query.
- 🟡 **Criptografia em repouso da tabela `credenciais`: Fernet.** Cifra reversível AES-128-CBC com etiqueta HMAC-SHA256 de integridade, pacote `cryptography`, chave mestra fornecida pela variável de ambiente `CREDENTIALS_MASTER_KEY`. Observação de correção de segurança: a resposta literal do usuário foi "hmac sha256 basico", porém HMAC-SHA256 é código de autenticação de mensagem, não cifra, e não é reversível. Se as chaves fossem gravadas como digest HMAC, o sistema seria incapaz de recuperá-las para as chamadas HTTP a Jina e aos modelos. O requisito do PRD ("toda a informação de chaves api salva em tabela criptografada") exige cifra reversível, logo Fernet. O padrão HMAC-SHA256 foi mantido onde é correto, na assinatura do webhook.
- 🟡 **Webhook de callback: assinatura HMAC-SHA256.** O POST do dossiê final para `CALLBACK_WEBHOOK_URL` carrega o cabeçalho `X-Signature: sha256=<hmac hexadecimal>`, calculado sobre o corpo cru da requisição com o segredo da variável de ambiente `WEBHOOK_HMAC_SECRET`. A comparação no receptor deve ser timing-safe (`hmac.compare_digest`). Ausência do cabeçalho ou assinatura divergente resulta em falha de entrega registrada, sem retry indefinido.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-21 | Versão inicial gerada por `/reversa-requirements` | reversa |
