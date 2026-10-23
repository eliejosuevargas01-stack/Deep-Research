# Spec: Endpoint /api/v1/audit — Auditoria de Qualidade

**Versão:** 1.0
**Status:** Planejada
**Autor:** reversa-spec-sdd
**Data:** 2026-10-21
**Reviewers:** Equipe Deep Research

---

## 1. Resumo

🟡 O endpoint `POST /api/v1/audit` constitui a terceira etapa do pipeline Deep Research, encarregado de validar a consistência analítica, veracidade factual e precisão do conteúdo coletado para cada um dos N pontos de investigação.
🟡 A funcionalidade recupera os registros da tabela `conteudo_coletado` na base SQLite permanente, acionando a persona `auditor` através de LLM forte OpenAI-compatible para responder a 12 perguntas de qualidade estruturadas, atribuindo a cada ponto o status de `aprovado` ou `reprovado` e persistindo as eventuais fragilidades identificadas na tabela `pontos`.

---

## 2. Contexto e Motivação

**Problema:**
🟡 Processos investigativos manuais e ferramentas automatizadas sem crivo crítico consolidam afirmações não verificadas, contradições lógicas e referências superficiais, gerando relatórios de baixa credibilidade e sem separação objetiva entre evidências comprovadas e lacunas de informação.

**Evidências:**
🟡 O PRD demonstra que soluções existentes operam como caixas-pretas que não inspecionam a integridade dos dados antes da redação, impossibilitando a detecção pontual de inconsistências ou o reprocessamento direcionado de eixos frágeis.

**Por que agora:**
🟡 A auditoria isolada por endpoint assegura que apenas informações verificadas avancem para a etapa de redação final, otimizando os custos com o LLM forte e prevenindo alucinações no dossiê definitivo.

---

## 3. Goals (Objetivos)

- [ ] G-01: 🟡 O sistema deve avaliar cada ponto de investigação através de 12 perguntas de qualidade predefinidas.
- [ ] G-02: 🟡 O sistema deve classificar cada ponto com o status `aprovado` ou `reprovado`, registrando `pontos_fracos` quando reprovado.
- [ ] G-03: 🟡 O sistema deve atualizar os registros na tabela `pontos` do SQLite permanente com integridade relacional.

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---|---|---|---|
| 🟡 Taxa de pontos avaliados com as 12 perguntas | 0% | = 100% | 21/10/2026 |
| 🟡 Tempo de resposta da auditoria completa | N/A | < 180s | 21/10/2026 |
| 🟡 Persistência de status em todos os N pontos | 0% | = 100% | 21/10/2026 |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: 🟡 O sistema não deve efetuar novas buscas web ou raspagem de páginas (`s.jina.ai`) durante a etapa de auditoria, operando exclusivamente sobre o conteúdo já coletado.
- NG-02: 🟡 O sistema não deve gerar a redação final do dossiê nem despachar notificações para webhooks de callback nesta rota.
- NG-03: 🟡 O sistema não deve aplicar fallback hardcoded para credenciais, modelo ou instruções da persona `auditor`.
- NG-04: 🟡 O sistema não deve modificar o conteúdo textual armazenado na tabela `conteudo_coletado`.

---

## 5. Usuários e Personas

**Usuário primário:** 🟡 Analista de Research: profissional de pesquisa que monitora o rigor metodológico da investigação e exige justificativas detalhadas para cada aprovação ou rejeição de ponto investigado.
**Usuário secundário:** 🟡 Redator/Dev integrador: desenvolvedor que orquestra o pipeline e automatiza decisões operacionais baseando-se no status de aprovação de cada ponto.
**Persona do sistema:** 🟡 Persona `auditor`: agente rigoroso encarregado de aplicar ceticismo metodológico, triangulação de afirmações e verificação de evidências nas 12 perguntas estruturadas.

**Jornada atual (sem a feature):**
1. 🟡 O analista lê extensos blocos de texto não estruturados coletados manualmente da internet.
2. 🟡 O analista busca manualmente contradições sem um checklist padronizado de validação.
3. 🟡 O analista gasta horas tentando verificar se cada fonte apoia as afirmações descritas.

**Jornada futura (com a feature):**
1. 🟡 O usuário submete requisição `POST /api/v1/audit` com o identificador `id_pesquisa`.
2. 🟡 O sistema resgata o conteúdo coletado e aplica o checklist das 12 perguntas com a persona `auditor`.
3. 🟡 O sistema persiste a deliberação na tabela `pontos` e devolve relatório detalhado de conformidade.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | 🟡 O sistema deve receber uma requisição HTTP POST no endpoint `/api/v1/audit` contendo o campo obrigatório `id_pesquisa` em formato JSON. | Must | 🟡 Dado o envio de payload com identificador válido, Quando o sistema processa a requisição, Então o sistema retorna código HTTP 200 com array de avaliações dos pontos. |
| RF-02 | 🟡 O sistema deve validar a existência prévia de registros na tabela `conteudo_coletado` vinculados ao `id_pesquisa`, retornando código HTTP 404 caso a pesquisa não exista ou código HTTP 400 caso o conteúdo ainda não tenha sido coletado. | Must | 🟡 Dado identificador sem conteúdo coletado, Quando o sistema consulta a base relacional, Então o sistema recusa o processamento informando a pendência da etapa de busca. |
| RF-03 | 🟡 O sistema deve carregar as instruções da persona `auditor` a partir da variável de ambiente `PERSONAS_CONFIG` ou tabela criptografada, interrompendo com erro HTTP 500 se não houver configuração explícita. | Must | 🟡 Dado ausência de configuração da persona, Quando o endpoint é acionado, Então o sistema rejeita a operação sem recorrer a valores embutidos em código. |
| RF-04 | 🟡 O sistema deve submeter o conteúdo de cada ponto investigativo ao LLM forte para avaliação das 12 perguntas de qualidade: clareza temática, corroboração em fontes canônicas, atualidade temporal, ausência de contradições internas, embasamento factual, aderência ao escopo do plano, profundidade analítica, precisão de números citados, neutralidade de tom, densidade de evidências, declaração de incertezas e solidez lógica. | Must | 🟡 Dado o lote de conteúdos de uma pesquisa, Quando o LLM forte avalia os itens, Então o sistema obtém respostas pontuais para os 12 critérios preestabelecidos. |
| RF-05 | 🟡 O sistema deve executar parser estruturado sobre a resposta da persona `auditor`, extraindo para cada ponto os atributos canônicos `id_pesquisa`, `tema`, `id_ponto`, `ponto`, `status` (`aprovado` ou `reprovado`) e `pontos_fracos`. | Must | 🟡 Dado o término da inferência do LLM forte, Quando o parser analisa a resposta, Então o sistema valida a presença dos campos obrigatórios e sanitiza as descrições de fragilidades. |
| RF-06 | 🟡 O sistema deve persistir os campos `status` e `pontos_fracos` na tabela `pontos` do SQLite permanente para cada registro correspondente ao identificador `ponto_id`. | Must | 🟡 Dado a validação dos atributos auditados, Quando a transação de persistência é executada, Então o sistema atualiza a tabela `pontos` no banco relacional. |
| RF-07 | 🟡 O sistema deve retornar ao cliente um payload JSON consolidado contendo `id_pesquisa`, total de pontos avaliados, contagem de aprovados, contagem de reprovados e a listagem estruturada das deliberações. | Must | 🟡 Dado o sucesso da gravação em banco, Quando o sistema finaliza a resposta, Então o sistema envia payload estruturado com contagem precisa de cada categoria. |

### 6.2 Fluxo Principal (Happy Path)

1. 🟡 O usuário envia uma requisição `POST /api/v1/audit` com payload JSON informando o identificador `id_pesquisa`.
2. 🟡 O sistema valida o identificador e recupera da base SQLite os pontos e os conteúdos coletados correspondentes.
3. 🟡 O sistema invoca o LLM forte OpenAI-compatible parametrizado com a persona `auditor`.
4. 🟡 O modelo avalia cada ponto frente às 12 perguntas de qualidade e emite parecer técnico estruturado em JSON.
5. 🟡 O sistema realiza o parsing das respostas, determinando a aprovação ou reprovação e as falhas de cada ponto.
6. 🟡 O sistema atualiza os status e campos `pontos_fracos` na tabela `pontos` do SQLite permanente.
7. 🟡 O sistema retorna resposta HTTP 200 com resumo quantitativo e detalhamento de cada ponto auditado.

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Ponto reprovado por carência de fontes canônicas:**
1. 🟡 O LLM forte constata ausência de fontes com autoridade suficiente para sustentar as conclusões do ponto.
2. 🟡 O sistema classifica o ponto como `reprovado`, registra a explicação no campo `pontos_fracos` e prossegue na auditoria dos pontos subsequentes.

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Performance | Latência total < 180s por pesquisa de 5 pontos | Depende do tempo de inferência e raciocínio do LLM forte |
| RNF-02 | 🟡 Timeout operacional | Limite de 600s por chamada externa | Conforme especificado na seção de restrições do PRD |
| RNF-03 | 🟡 Resiliência de chamadas externas | 1 tentativa inicial + 3 retries com backoff | Aplicado a requisições HTTP para o endpoint de inferência LLM forte |
| RNF-04 | 🟡 Persistência | Banco de dados SQLite permanente | Os registros da auditoria devem persistir entre reinicializações |
| RNF-05 | 🟡 Isolamento modular | Monolito modular sem dependência de outros endpoints | O endpoint executa de forma autônoma lendo diretamente o banco |

---

## 8. Design e Interface

**Componentes afetados:**
- 🟡 Rota FastAPI `POST /api/v1/audit`
- 🟡 Módulo de auditoria `core/auditor.py`
- 🟡 Esquema de validação `schemas/audit.py`
- 🟡 Repositório de dados `db/repository.py`

**Comportamento esperado:**
🟡 O endpoint opera como interface REST assíncrona, validando contratos via Pydantic e gerando códigos de status HTTP semânticos (200 para sucesso, 400 para conteúdo ausente, 404 para pesquisa não encontrada, 502/504 para falhas no LLM forte).

**Estados da UI/API:**
- Estado vazio: 🟡 Payload com `id_pesquisa` ausente retorna código HTTP 422 informando validação de schema.
- Estado de carregamento: 🟡 Conexão mantida aberta durante as etapas de consulta ao banco e inferência profunda.
- Estado de erro: 🟡 Resposta estruturada com mensagem descritiva do erro, código interno e detalhe de falha externa.
- Estado de sucesso: 🟡 Código HTTP 200 com resumo analítico completo e listagem dos pontos auditados.

---

## 9. Modelo de Dados

**Entidades novas ou modificadas:**

```
pontos {
  ponto_id: string (UUID)          // identificador exclusivo do ponto
  id_pesquisa: string (UUID)       // chave estrangeira referenciando pesquisa.id_pesquisa
  tema: string                     // cópia do tema para desnormalização e consulta
  ponto_n: integer                 // número sequencial do ponto (1 até N)
  ponto: string                    // descrição textual do ponto de investigação
  status: string                   // atualizado para: aprovado | reprovado
  pontos_fracos: string (opcional) // registro textual detalhado das fraquezas apontadas
}

conteudo_coletado {
  id_pesquisa: string (UUID)       // chave estrangeira referenciando pesquisa
  ponto_id: string (UUID)          // chave estrangeira referenciando pontos
  tema: string                     // tema de referência
  ponto: string                    // enunciado do ponto
  conteudo_coletado: string        // texto consolidado lido na etapa de busca
  urls_lidas: string (JSON)        // lista de URLs consultadas
  urls_fonte: string (JSON)        // fontes canônicas identificadas
}
```

**Migrações necessárias:** 🟡 Não há alterações estruturais na tabela; o endpoint executa comandos UPDATE nos campos `status` e `pontos_fracos` já previstos na criação inicial do esquema.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 LLM Forte OpenAI-compatible | Obrigatória | Erro HTTP 502 retornado após esgotamento de 1 tentativa + 3 retries; auditoria abortada sem persistir deliberações |
| 🟡 SQLite Permanente | Obrigatória | Falha crítica de inicialização da API ou erro HTTP 500 caso o arquivo em disco esteja inacessível |
| 🟡 Tabela de Credenciais Criptografada | Obrigatória | Erro HTTP 500 caso a chave do modelo ou base URL configurada não possa ser recuperada |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Pesquisa informada sem conteúdo coletado | 🟡 Tabela conteudo_coletado sem linhas para o id_pesquisa | O sistema retorna código HTTP 400 informando que a etapa de busca deve ser concluída antes da auditoria |
| EC-02: Timeout de chamada externa do LLM forte | 🟡 Inferência analítica ultrapassa o limite de 600s | O sistema interrompe a conexão, executa 3 retries com backoff e caso persista retorna HTTP 504 |
| EC-03: Indisponibilidade de rede ou erro 503 do LLM | 🟡 Provedor LLM retorna código de erro 503 ou conexão recusada | O sistema executa política de retries com espera exponencial; persistindo a falha, retorna HTTP 502 com detalhes |
| EC-04: Falha no parser de JSON estruturado da auditoria | 🟡 LLM forte retorna texto livre sem respeitar o formato de atributos | O sistema aciona rotina de parsing corretivo; persistindo o erro, aborta a gravação e retorna HTTP 500 |
| EC-05: Conteúdo coletado com tamanho nulo ou corrompido | 🟡 Registro com campo conteudo_coletado vazio ou caracteres ilegíveis | O sistema atribui status reprovado com anotação de falha na coleta e prossegue para os outros pontos |

---

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 Acesso restrito via token de API bearer validado pelo middleware FastAPI.
- **Autorização:** 🟡 Qualquer cliente com token de serviço válido pode solicitar auditoria de pesquisas existentes.
- **Dados sensíveis:** 🟡 O endpoint processa dados públicos coletados da web; chaves de API do LLM forte são armazenadas em tabela criptografada com override por variáveis de ambiente.
- **Auditoria:** 🟡 O sistema registra logs estruturados contendo `id_pesquisa`, tempo total de inferência do LLM forte, quantidade de pontos aprovados/reprovados e identificador de chamadas externas.

---

## 13. Plano de Rollout

- **Estratégia:** 🟡 Implantação direta modular no contêiner único do projeto, mantendo compatibilidade de banco relacional e cobertura de testes de integração.
- **Como reverter (rollback):** 🟡 Restauração da versão anterior do contêiner Docker, preservando a integridade do banco SQLite persistido em volume permanente.
- **Monitoramento pós-deploy:** 🟡 Acompanhamento durante as primeiras 48h das taxas de status HTTP 5xx, latência média da inferência do LLM forte e distribuição entre pontos aprovados e reprovados.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | 🟡 ⚠️ ABERTO: Deve o endpoint permitir auditoria individual por `ponto_id` além do processamento do lote completo? | Médio | dev-integrador | 21/10/2026 |
| OQ-02 | 🟡 ⚠️ ABERTO: Quantas respostas negativas entre as 12 perguntas determinam a reprovação automática do ponto? | Alto | analista-research | 21/10/2026 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Emprego de LLM forte para avaliação das 12 perguntas | Utilizar o mesmo LLM leve da etapa de busca | Garante discernimento conceitual superior e reduz alucinações na triagem de consistência analítica |
| 🟡 Atualização in-place na tabela de pontos | Criar tabela separada para histórico de auditoria | Mantém o esquema relacional simples e centraliza o status operacional do pipeline |
| 🟡 Checklist fixo de 12 perguntas no prompt | Permitir checklist dinâmico enviado no payload | Padroniza a barra de qualidade em todas as execuções conforme requisito estrito do PRD |

---

## Apêndice

### Referências
- PRD Deep Research (`_reversa_sdd/prd.md`)
- Especificação de Personas (`_reversa_sdd/personas.md`)
- Documentação da API OpenAI-compatible

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 1.0 | 2026-10-21 | reversa-spec-sdd | Elaboração da especificação formal do endpoint de auditoria de qualidade |

---

## Relatório de Avaliação de Qualidade

```text
============================================================
  SPEC QUALITY REPORT
  Arquivo: /root/projects/deep-research/_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md
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
