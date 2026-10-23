# Spec: Endpoint /api/v1/search — Busca com Personas

**Versão:** 1.0
**Status:** Planejada
**Autor:** reversa-spec-sdd
**Data:** 2026-10-21
**Reviewers:** Equipe Deep Research

---

## 1. Resumo

🟡 O endpoint `POST /api/v1/search` constitui a segunda etapa do pipeline Deep Research, encarregado de executar a varredura aprofundada na web para os pontos de investigação previamente gerados na etapa de plano.
🟡 A execução opera em paralelo para todos os N pontos cadastrados, aplicando quatro personas especializadas do sistema (`historiador`, `visionario`, `cetico`, `futurista`) acionadas via LLM leve OpenAI-compatible, com chamadas de ferramenta ao Jina SERP e Jina Scrapper (`s.jina.ai`), filtragem de URLs previamente lidas e consolidação sem truncamento na base SQLite permanente.

---

## 2. Contexto e Motivação

**Problema:**
🟡 A busca manual por fontes e conteúdos aprofundados demanda tempo excessivo e gera leituras repetitivas das mesmas páginas, além de carecer de diversidade analítica na formulação de consultas.

**Evidências:**
🟡 No diagnóstico do PRD, ferramentas concorrentes tratam a busca como etapa opaca sem desduplicação de URLs e sem separação de perspectivas analíticas, inflando custos de processamento com scraping redundante.

**Por que agora:**
🟡 O processamento concorrente dos N pontos associado ao filtro de URLs por pesquisa assegura varredura abrangente com economia de chamadas externas e rastreabilidade total das fontes canônicas.

---

## 3. Goals (Objetivos)

- [ ] G-01: 🟡 O sistema deve processar em paralelo todos os N pontos de uma pesquisa identificada por `id_pesquisa`.
- [ ] G-02: 🟡 O sistema deve aplicar o filtro deduplicador de URLs por `id_pesquisa` evitando requisições repetidas a páginas já consultadas.
- [ ] G-03: 🟡 O sistema deve concatenar integralmente o conteúdo coletado e as listas de URLs de origem sem truncar a resposta.

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---|---|---|---|
| 🟡 Taxa de pontos processados em paralelo com sucesso | 0% | = 100% | 21/10/2026 |
| 🟡 Deduplicação de URLs já consultadas por pesquisa | 0% | = 100% | 21/10/2026 |
| 🟡 Tempo de resposta total da busca por ponto | N/A | < 300s | 21/10/2026 |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: 🟡 O sistema não deve efetuar a avaliação crítica das 12 perguntas de qualidade, que compete privativamente ao endpoint `/api/v1/audit`.
- NG-02: 🟡 O sistema não deve redigir o dossiê final consolidado nem despachar notificações para webhooks, responsabilidades exclusivas de `/api/v1/writer`.
- NG-03: 🟡 O sistema não deve redefinir nem recriar os pontos de investigação na tabela `pontos`, consumindo estritamente os registros existentes.
- NG-04: 🟡 O sistema não deve reter histórico conversacional completo na memória do LLM entre chamadas de ferramenta distintas, operando sob memória transitória focada em chamadas de ferramentas.

---

## 5. Usuários e Personas

**Usuário primário:** 🟡 Analista de Research: profissional que acompanha a coleta factual por ponto temático e necessita de integridade nas fontes extraídas.
**Usuário secundário:** 🟡 Redator/Dev integrador: desenvolvedor que integra a coleta automatizada e consome os dados estruturados de URLs e conteúdo.
**Personas do sistema:** 🟡 Quatro personas analíticas ativas (`historiador`, `visionario`, `cetico`, `futurista`), cada uma orientando a formulação de buscas e a interpretação sob seu respectivo viés temático.

**Jornada atual (sem a feature):**
1. 🟡 O analista abre dezenas de abas no navegador e copia trechos manualmente para blocos de notas.
2. 🟡 O analista revisita involuntariamente as mesmas páginas para diferentes pontos do tema gerando retrabalho.
3. 🟡 As fontes primárias perdem o vínculo com as passagens transcritas comprometendo a rastreabilidade.

**Jornada futura (com a feature):**
1. 🟡 O usuário submete requisição `POST /api/v1/search` informando o `id_pesquisa`.
2. 🟡 O sistema executa os trabalhadores em paralelo aplicando as personas analíticas e a ferramenta Jina.
3. 🟡 O sistema persiste todo o conteúdo consolidado e as listas de fontes na base SQLite permanente.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | 🟡 O sistema deve receber requisições HTTP POST no endpoint `/api/v1/search` contendo obrigatoriamente o campo `id_pesquisa` em formato JSON. | Must | 🟡 Dado envio de payload com `id_pesquisa` válido, Quando o sistema processa a requisição, Então o sistema inicia a varredura paralela dos pontos pendentes. |
| RF-02 | 🟡 O sistema deve recuperar todos os pontos com status `pendente` associados ao `id_pesquisa` na tabela `pontos`, retornando código HTTP 404 caso nenhum ponto seja localizado. | Must | 🟡 Dado um `id_pesquisa` inexistente no banco, Quando o sistema consulta a tabela `pontos`, Então o sistema responde código HTTP 404 informando ausência de registros. |
| RF-03 | 🟡 O sistema deve orquestrar a execução concorrente em paralelo de todos os pontos recuperados utilizando instâncias de LLM leve OpenAI-compatible. | Must | 🟡 Dado um conjunto de N pontos pendentes, Quando a rotina de busca é disparada, Então o sistema processa os N pontos em threads ou tarefas assíncronas paralelas. |
| RF-04 | 🟡 O sistema deve injetar os prompts diretivos das personas (`historiador`, `visionario`, `cetico`, `futurista`) configuradas via variáveis de ambiente para diversificar os ângulos de busca. | Must | 🟡 Dado o acionamento de cada trabalhador, Quando o LLM recebe o contexto, Então o sistema fornece as instruções da persona atribuída sem recorrer a fallback hardcoded. |
| RF-05 | 🟡 O sistema deve fornecer às instâncias do LLM a ferramenta Jina SERP e Scrapper (`s.jina.ai`), interceptando cada URL antes da requisição para descartar links já catalogados na tabela de URLs lidas para a pesquisa corrente. | Must | 🟡 Dado o retorno de links pela SERP, Quando uma URL já existente é identificada pelo filtro, Então o sistema descarta o scrap redundante e preserva a cota de requisições. |
| RF-06 | 🟡 O sistema deve persistir em segundo plano as novas URLs consultadas na tabela `conteudo_coletado` e manter memória restrita ao ciclo de chamadas de ferramentas. | Must | 🟡 Dado o término de leitura de uma página web, Quando o trabalhador conclui a iteração, Então o sistema registra a URL lida de forma assíncrona. |
| RF-07 | 🟡 O sistema deve consolidar o texto completo retornado pelas ferramentas sem truncamento sintático, gravando na tabela `conteudo_coletado` os campos `tema`, `id_pesquisa`, `ponto`, `ponto_id`, `conteudo_coletado`, `urls_lidas` e `urls_fonte`. | Must | 🟡 Dado o encerramento da busca de um ponto, Quando o parser finaliza o empacotamento, Então o sistema persiste o texto integral e as coleções de URLs associadas. |
| RF-08 | 🟡 O sistema deve atualizar o status dos pontos correspondentes para `coletado` na tabela `pontos` e responder código HTTP 200 com o sumário de processamento. | Must | 🟡 Dado o processamento bem-sucedido de todos os pontos, Quando a resposta é emitida, Então o sistema entrega código HTTP 200 contendo total de pontos e URLs processadas. |

### 6.2 Fluxo Principal (Happy Path)

1. 🟡 O usuário submete requisição `POST /api/v1/search` com payload contendo `id_pesquisa`.
2. 🟡 O sistema consulta e valida a existência dos pontos associados na tabela `pontos` no SQLite.
3. 🟡 O sistema distribui cada ponto para um trabalhador assíncrono em paralelo, configurado com a persona atribuída e modelo LLM leve.
4. 🟡 O trabalhador formula requisição de busca via Jina SERP e seleciona URLs relevantes para aprofundamento.
5. 🟡 O sistema valida as URLs contra o histórico da pesquisa corrente, descartando itens duplicados e despachando as novas para o Jina Scrapper (`s.jina.ai`).
6. 🟡 O modelo analisa o texto extraído, decide se necessita de buscas adicionais ou finaliza a síntese de coleta daquele ponto.
7. 🟡 O sistema persiste os dados integrais na tabela `conteudo_coletado`, atualiza o status na tabela `pontos` e retorna resposta HTTP 200 com resumo das fontes catalogadas.

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Reprocessamento de ponto específico falhado:**
1. 🟡 O usuário submete `POST /api/v1/search` informando `id_pesquisa` e o parâmetro opcional `ponto_id`.
2. 🟡 O sistema restringe o processamento concorrente exclusivamente ao ponto selecionado preservando as coletas anteriores.

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Performance de busca paralela | Tempo total < 300s para conjunto de N pontos | Processamento paralelo com LLM leve e raspagem assíncrona |
| RNF-02 | 🟡 Timeout operacional | Limite de 600s por chamada externa | Conforme restrição técnica do PRD para chamadas HTTP |
| RNF-03 | 🟡 Resiliência de requisições externas | 1 tentativa inicial + 3 retries com backoff | Aplicado a requisições HTTP para Jina e endpoint LLM |
| RNF-04 | 🟡 Persistência | Banco de dados SQLite permanente | Sobrevivência de dados a redeploys de contêineres |
| RNF-05 | 🟡 Isolamento de memória | Memória conversacional restrita à chamada de ferramenta | Evita degradação de contexto e vazamento entre pontos |

---

## 8. Design e Interface

**Componentes afetados:**
- 🟡 Rota FastAPI `POST /api/v1/search`
- 🟡 Orquestrador concorrente `core/searcher.py`
- 🟡 Cliente Jina SERP e Scrapper `tools/jina_client.py`
- 🟡 Repositório de persistência `db/repository.py`

**Comportamento esperado:**
🟡 Interface REST assíncrona que executa o pool de busca, persistindo os resultados intermediários e devolvendo relatório estruturado com contagem de fontes e status de cada ponto investigado.

**Estados da UI/API:**
- Estado vazio: 🟡 Requisição sem `id_pesquisa` retorna código HTTP 422 detalhando a pendência contratual.
- Estado de carregamento: 🟡 Conexão mantida enquanto os N trabalhadores realizam as chamadas aos serviços externos.
- Estado de erro: 🟡 Resposta estruturada com detalhes da exceção, código interno e pontos que demandam reprocessamento.
- Estado de sucesso: 🟡 Código HTTP 200 contendo lista de pontos atualizados, volume de URLs lidas e total de conteúdo persistido.

---

## 9. Modelo de Dados

**Entidades novas ou modificadas:**

```
conteudo_coletado {
  id: string (UUID)                // identificador exclusivo do registro de coleta
  id_pesquisa: string (UUID)       // referência à pesquisa raiz
  ponto_id: string (UUID)          // referência ao ponto de investigação
  tema: string                     // tema de pesquisa associado
  ponto: string                    // descrição textual do ponto
  conteudo_coletado: text          // conteúdo textual integral extraído sem truncamento
  urls_lidas: text (JSON array)    // lista de todas as URLs consultadas durante o processo
  urls_fonte: text (JSON array)    // lista de URLs canônicas selecionadas como referência
  criado_em: timestamp             // data e hora de registro no formato ISO 8601
}
```

**Migrações necessárias:** 🟡 Criação da tabela `conteudo_coletado` gerenciada pelo SQLAlchemy no banco SQLite permanente.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 Jina SERP e Scrapper (`s.jina.ai`) | Obrigatória | Erro HTTP 502 após 1 tentativa + 3 retries; gravação de coleta abortada |
| 🟡 LLM OpenAI-compatible (Leve) | Obrigatória | Erro HTTP 502 ou 504 por expiração do timeout de 600s; ponto permanece pendente |
| 🟡 SQLite Permanente | Obrigatória | Erro crítico HTTP 500 impedindo consulta de pontos e persistência de coletas |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Pesquisa não encontrada no banco | 🟡 `id_pesquisa` ausente na tabela `pesquisa` | O sistema retorna código HTTP 404 com detalhe informando identificador não localizado |
| EC-02: Indisponibilidade de rede ou falha do Jina Scrapper | 🟡 Jina retorna erro 500, 502 ou 503 | O sistema executa 3 retries com backoff exponencial; mantida a falha, preserva dados parciais da SERP |
| EC-03: Timeout de execução do LLM leve | 🟡 Inferência ultrapassa limite de 600s | O sistema cancela a conexão externa, registra log estruturado e assinala o ponto para retry posterior |
| EC-04: Todas as URLs da SERP já catalogadas | 🟡 Filtro deduplicador rejeita 100% dos links da página | O sistema sinaliza ao LLM para formular termos de busca alternativos sob novo prisma investigativo |
| EC-05: Variáveis de ambiente de personas ausentes | 🟡 Inicialização sem definição das 4 personas de busca | O sistema emite falha crítica e recusa o processamento sem recorrer a configurações hardcoded |

---

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 Acesso condicionado a bearer token validado em camada de middleware FastAPI.
- **Autorização:** 🟡 Requisições autorizadas para usuários e sistemas integradores autenticados.
- **Dados sensíveis:** 🟡 Credenciais de acesso à API do Jina e aos modelos LLM armazenadas em tabela criptografada ou variáveis de contêiner.
- **Auditoria:** 🟡 Registro de eventos com timestamps, `id_pesquisa`, URLs lidas, tempo de resposta por ponto e códigos HTTP gerados.

---

## 13. Plano de Rollout

- **Estratégia:** 🟡 Implantação direta modular em contêiner Docker com arquitetura monolito, validando os contratos de rota via testes automatizados.
- **Como reverter (rollback):** 🟡 Restauração da imagem anterior estável do contêiner e retenção do arquivo SQLite em volume persistente.
- **Monitoramento pós-deploy:** 🟡 Acompanhamento contínuo da latência de scraping, volume de URLs duplicadas descartadas e taxa de erro HTTP 5xx nas primeiras 48h.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | 🟡 ⚠️ ABERTO: Qual a quantidade máxima de iterações de busca que o LLM leve pode acionar por ponto investigativo? | Médio | dev-integrador | 21/10/2026 |
| OQ-02 | 🟡 ⚠️ ABERTO: Deve existir limite máximo em megabytes para o campo `conteudo_coletado` consolidado de cada ponto? | Baixo | analista-research | 21/10/2026 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Processamento concorrente em paralelo de todos os pontos | Execução sequencial ponto a ponto | Reduz o tempo de resposta total permitindo atender à meta de conclusão do pipeline em menos de 10 minutos |
| 🟡 Descarte de URLs lidas por pesquisa via filtro de histórico | Repetir a leitura de páginas já consultadas | Minimiza latência e previne desperdício desnecessário de cota da ferramenta externa Jina |
| 🟡 Memória transitória restrita a chamadas de ferramentas | Manter histórico conversacional completo acumulado | Previne saturação de contexto no LLM leve e evita contaminação analítica entre pontos |

---

## Apêndice

### Referências
- PRD Deep Research (`_reversa_sdd/prd.md`)
- Especificação de Personas (`_reversa_sdd/personas.md`)
- Documentação da API Jina Scrapper (`https://s.jina.ai`)

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 1.0 | 2026-10-21 | reversa-spec-sdd | Elaboração inicial da especificação formal do endpoint de busca com personas |

---

## Relatório de Avaliação de Qualidade

```text
============================================================
  SPEC QUALITY REPORT
  Arquivo: /root/projects/deep-research/_reversa_sdd/sdd/endpoint-busca-com-personas.md
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
