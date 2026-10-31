# Spec: Endpoint /api/v1/audit — Auditoria de Qualidade

**Versão:** 1.1
**Status:** Planejada (revisão normativa v2)
**Autor:** reversa-spec-sdd
**Data:** 2026-10-27 (original 2026-10-21)
**Reviewers:** Equipe Deep Research

---

## 1. Resumo

🟡 O endpoint `POST /api/v1/audit` constitui a terceira etapa do pipeline Deep Research, encarregado de validar a consistência analítica, veracidade factual e precisão do conteúdo coletado para cada um dos N pontos de investigação.

🟡 A funcionalidade recupera as coletas do ponto na base SQLite permanente, aciona a persona `auditor` via LLM forte OpenAI-compatible para responder a **12 perguntas de qualidade estruturadas**, atribui a cada ponto o status `aprovado` ou `reprovado` e persiste as fragilidades identificadas na tabela `pontos`.

🟡 **v1.1 (normativa):** a entrada do auditor passa a ser (a) a **visão consolidada das 4 personas** do ponto e (b) o **histórico integral de todas as rodadas de coleta** do ponto, sem truncamento e sem descarte de retries. Esta revisão **supera** o adendo v5 (2026-10-24), que determinava uso exclusivo da coleta mais recente como corpus de avaliação.

---

## 2. Contexto e Motivação

**Problema:**
🟡 Processos investigativos manuais e ferramentas automatizadas sem crivo crítico consolidam afirmações não verificadas, contradições lógicas e referências superficiais, gerando relatórios de baixa credibilidade e sem separação objetiva entre evidências comprovadas e lacunas de informação.

**Evidências:**
🟡 O PRD demonstra que soluções existentes operam como caixas-pretas que não inspecionam a integridade dos dados antes da redação, impossibilitando a detecção pontual de inconsistências ou o reprocessamento direcionado de eixos frágeis.

**Por que agora:**
🟡 A auditoria isolada por endpoint assegura que apenas informações verificadas avancem para a etapa de redação final, otimizando os custos com o LLM forte e prevenindo alucinações no dossiê definitivo.

**Motivação da revisão v1.1:**
🟡 Em execução real, um ponto com 3 retries era auditado apenas contra a última coleta: as evidências válidas das rodadas 1–3 — já pagas em chamadas Jina e LLM — desapareciam do parecer, e o auditor reprovava por "ausência de fonte" que existia em rodada anterior. Além disso, o corpus entregue ao LLM era montado apenas a partir de trechos citados na última rodada, reforçando o mesmo viés.

---

## 3. Goals (Objetivos)

- [ ] G-01: 🟡 Avaliar cada ponto de investigação através das 12 perguntas de qualidade predefinidas.
- [ ] G-02: 🟡 Classificar cada ponto com status `aprovado` ou `reprovado`, registrando `pontos_fracos` quando reprovado.
- [ ] G-03: 🟡 Atualizar os registros na tabela `pontos` do SQLite permanente com integridade relacional.
- [ ] G-04 (v1.1): 🟡 Avaliar cada ponto sobre a **visão consolidada das 4 personas** + **histórico integral das rodadas**.
- [ ] G-05 (v1.1): 🟡 Nunca truncar, resumir ou omitir material de evidência; volume excessivo gera insuficiência explícita.

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---|---|---|---|
| 🟡 Taxa de pontos avaliados com as 12 perguntas | 0% | = 100% | 2026-10-31 |
| 🟡 Tempo de resposta da auditoria completa | N/A | < 180s | 2026-10-31 |
| 🟡 Persistência de status em todos os N pontos | 0% | = 100% | 2026-10-31 |
| 🟡 Rodadas de coleta presentes no contexto de auditoria | 1 (última) | = 100% das rodadas | 2026-10-31 |
| 🟡 Caracteres de evidência truncados | > 0 | = 0 | 2026-10-31 |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: 🟡 O sistema não deve efetuar novas buscas web ou raspagem de páginas durante a etapa de auditoria, operando exclusivamente sobre o conteúdo já coletado.
- NG-02: 🟡 O sistema não deve gerar a redação final do dossiê nem despachar notificações para webhooks de callback nesta rota.
- NG-03: 🟡 O sistema não deve aplicar fallback hardcoded para credenciais, modelo ou instruções da persona `auditor`.
- NG-04: 🟡 O sistema não deve modificar ou apagar o conteúdo textual armazenado nas rodadas de `conteudo_coletado`; apenas acrescentar o parecer em `metadados_coleta.auditorias`.
- NG-05 (v1.1): 🟡 O sistema **não** deve escolher uma rodada "representativa" ou resumir o histórico para caber no contexto.
- NG-06 (v1.1): 🟡 O sistema **não** deve aprovar um ponto cujo corpus acumulado não tenha sido integralmente entregue ao modelo.

---

## 5. Usuários e Personas

**Usuário primário:** 🟡 Analista de Research: profissional de pesquisa que monitora o rigor metodológico da investigação e exige justificativas detalhadas para cada aprovação ou rejeição.
**Usuário secundário:** 🟡 Redator/Dev integrador: desenvolvedor que orquestra o pipeline e automatiza decisões operacionais baseando-se no status de aprovação de cada ponto.
**Persona do sistema:** 🟡 Persona `auditor`: agente rigoroso encarregado de aplicar ceticismo metodológico, triangulação de afirmações e verificação de evidências nas 12 perguntas estruturadas.

**Jornada atual (sem a feature):**
1. 🟡 O analista lê extensos blocos de texto não estruturados coletados manualmente da internet.
2. 🟡 O analista busca manualmente contradições sem um checklist padronizado de validação.
3. 🟡 O analista gasta horas tentando verificar se cada fonte apoia as afirmações descritas.

**Jornada futura (com a feature):**
1. 🟡 O usuário submete requisição `POST /api/v1/audit` com o identificador `id_pesquisa`.
2. 🟡 O sistema resgata a visão consolidada das 4 personas e todas as rodadas de coleta do ponto, e aplica o checklist das 12 perguntas com a persona `auditor`.
3. 🟡 O sistema persiste a deliberação na tabela `pontos` e devolve relatório detalhado de conformidade.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | 🟡 O sistema deve receber uma requisição HTTP POST no endpoint `/api/v1/audit` contendo o campo obrigatório `id_pesquisa` em formato JSON. | Must | 🟡 Dado payload com identificador válido, o sistema retorna HTTP 200 com array de avaliações dos pontos. |
| RF-02 | 🟡 O sistema deve validar a existência prévia de registros em `conteudo_coletado` vinculados ao `id_pesquisa`, retornando 404 se a pesquisa não existir ou 400 se o conteúdo ainda não tiver sido coletado. | Must | 🟡 Identificador sem conteúdo coletado ⇒ recusa informando pendência da etapa de busca. |
| RF-03 | 🟡 O sistema deve carregar as instruções da persona `auditor` a partir de variável de ambiente ou tabela criptografada, interrompendo com erro HTTP 500 se não houver configuração explícita. | Must | 🟡 Ausência de configuração ⇒ rejeição sem valores embutidos em código. |
| RF-04 | 🟡 O sistema deve submeter o conteúdo de cada ponto ao LLM forte para avaliação das 12 perguntas: clareza temática, corroboração em fontes canônicas, atualidade temporal, ausência de contradições internas, embasamento factual, aderência ao escopo do plano, profundidade analítica, precisão de números citados, neutralidade de tom, densidade de evidências, declaração de incertezas e solidez lógica. Com múltiplos pontos, processamento concorrente via `asyncio.gather`, isolamento estrito de `AsyncSession` por corrotina e barreira final sem SSE. | Must | 🟡 Lote de conteúdos ⇒ respostas pontuais para os 12 critérios em paralelo com sessões isoladas. |
| RF-05 | 🟡 O sistema deve executar parser estruturado sobre a resposta da persona `auditor`, extraindo `id_pesquisa`, `tema`, `id_ponto`, `ponto`, `status` (`aprovado`/`reprovado`) e `pontos_fracos`. | Must | 🟡 Parser valida campos obrigatórios e sanitiza fragilidades. |
| RF-06 | 🟡 O sistema deve persistir `status` e `pontos_fracos` na tabela `pontos` para cada `ponto_id`. | Must | 🟡 Transação atômica atualiza a tabela `pontos`. |
| RF-07 | 🟡 O sistema deve retornar payload JSON consolidado com `id_pesquisa`, total de pontos avaliados, contagem de aprovados, contagem de reprovados e as deliberações. | Must | 🟡 Payload com contagem precisa de cada categoria. |

### 6.2 Requisitos da revisão v1.1 (normativos)

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-08 | 🟡 A entrada do auditor deve ser a **visão consolidada das 4 personas** do ponto (`resultados_personas`: análise integral, conclusões, lacunas, motivo de parada, diário, ledger), nunca uma persona isolada. | Must | 🟡 Para cada ponto auditado, o payload do LLM contém as 4 personas ativas com análise não vazia. |
| RF-09 | 🟡 A entrada do auditor deve conter o **histórico integral de todas as rodadas** de coleta do ponto (rodada 1..R), cada uma com suas análises, conclusões, fontes, trechos e pareceres anteriores. Proibido usar apenas a última rodada. | Must | 🟡 Ponto com 3 retries ⇒ payload contém 4 rodadas identificadas por `rodada` e `coleta_id`; teste falha se qualquer rodada estiver ausente. |
| RF-10 | 🟡 A entrada do auditor não pode sofrer truncamento de conteúdo. Nenhum `slice`, cap de caracteres ou resumo automático sobre o material de evidência. | Must | 🟡 Fonte com 50.000 caracteres entra no payload com 50.000 caracteres. |
| RF-11 (v1.2) | 🟡 Quando o volume acumulado exceder `AUDIT_EVIDENCE_BUDGET_CHARS`, a evidência é lida **integralmente em N passes** sequenciais (cada passe dentro do orçamento, nenhum trecho fatiado) e o parecer final decide os 12 critérios com as notas citáveis de todos os passes. Recusar o ponto por volume é proibido: equivale a truncamento disfarçado. | Must | 🟡 Corpus acima do orçamento ⇒ `passes_evidencia > 1` no parecer, `notas_evidencia` de todos os passes no payload de decisão e nenhum trecho ausente da leitura. |
| RF-12 | 🟡 O julgamento dos 12 critérios deve considerar o corpus acumulado (todas as rodadas), mas a **aprovação** continua exigindo evidência válida e verificável da rodada corrente (fence de staleness). Evidência exclusivamente de rodada antiga pode fundamentar um critério, mas não substitui a ausência total de evidência atual sem que o parecer declare isso explicitamente. | Must | 🟡 Ponto cuja rodada corrente não leu nenhuma URL permanece `reprovado`, mesmo com rodadas anteriores ricas; o parecer cita a rodada antiga e explica a insuficiência atual. |
| RF-13 | 🟡 O parecer deve registrar quais rodadas foram efetivamente consideradas (`rodadas_consideradas`), para auditoria posterior. | Should | 🟡 `metadados_coleta.auditorias[-1].rodadas_consideradas` = `[1,2,3,4]`. |

### 6.3 Fluxo Principal (Happy Path)

1. 🟡 O usuário envia `POST /api/v1/audit` com `id_pesquisa`.
2. 🟡 O sistema valida o identificador e recupera os pontos e **todas** as coletas de cada ponto.
3. 🟡 O sistema monta o pacote do ponto: visão consolidada das 4 personas (rodada corrente) + histórico integral das rodadas anteriores + corpus canônico (fontes com corpo/hash, trechos com offset/hash).
4. 🟡 O sistema invoca o LLM forte parametrizado com a persona `auditor`.
5. 🟡 O modelo avalia o ponto frente às 12 perguntas e emite parecer técnico estruturado em JSON.
6. 🟡 O sistema faz o parsing, calcula deterministicamente `atendidos`/`percentual`, determina aprovação/reprovação e as falhas.
7. 🟡 O sistema persiste o parecer em `metadados_coleta.auditorias` (append) e atualiza `status`/`pontos_fracos` na tabela `pontos`.
8. 🟡 O sistema retorna HTTP 200 com resumo quantitativo e detalhamento de cada ponto auditado.

### 6.4 Fluxos Alternativos

**Fluxo Alternativo A — Ponto reprovado por carência de fontes canônicas na rodada corrente:**
1. 🟡 O LLM constata que a rodada corrente não sustenta as conclusões.
2. 🟡 O sistema classifica como `reprovado`, registra a explicação em `pontos_fracos` incluindo referência às rodadas anteriores que já cobriam o tema, e prossegue com os demais pontos.

**Fluxo Alternativo B — Ponto com retries acumulados (v1.1):**
1. 🟡 O ponto possui rodadas 1..R.
2. 🟡 O sistema entrega todas as rodadas ao modelo.
3. 🟡 O parecer pode aprovar citando evidência de qualquer rodada, desde que a rodada corrente satisfaça o fence de validade (RF-12).

**Fluxo Alternativo C — Corpus acima do orçamento (v1.1):**
1. 🟡 O volume acumulado excede `AUDIT_EVIDENCE_BUDGET_CHARS`.
2. 🟡 O sistema **não** corta e **não** recusa: divide os trechos em passes que cabem no orçamento, lê cada passe por inteiro e entrega ao parecer final as notas citáveis de todos eles. O parecer resultante registra `passes_evidencia` e `trechos_lidos_integralmente` para auditoria.

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Performance | Latência total < 180s por pesquisa de 5 pontos | Depende do tempo de inferência do LLM forte |
| RNF-02 | 🟡 Timeout operacional | Limite de 600s por chamada externa | Conforme restrição do PRD |
| RNF-03 | 🟡 Resiliência de chamadas externas | 1 tentativa inicial + 3 retries com backoff | Aplicado ao endpoint LLM forte |
| RNF-04 | 🟡 Persistência | SQLite permanente | Registros sobrevivem a reinicializações |
| RNF-05 | 🟡 Isolamento modular | Monolito modular sem dependência de outros endpoints | Lê diretamente o banco |
| RNF-06 (v1.2) | 🟡 Zero truncamento | 0 caracteres cortados | Orçamento excedido ⇒ leitura em N passes, nada descartado |
| RNF-07 (v1.1) | 🟡 Determinismo da decisão | Cálculo no backend | `atendidos = sum(aprovado)`, `percentual = round(100*atendidos/12, 2)`; nunca aceitar nota do modelo |
| RNF-08 (v1.1) | 🟡 Auditabilidade do corpus | 100% das rodadas identificadas | `rodadas_consideradas` no parecer |

---

## 8. Design e Interface

**Componentes afetados:**
- 🟡 Rota FastAPI `POST /api/v1/audit`
- 🟡 Módulo de auditoria `core/auditor.py`
- 🟡 Esquema de validação `schemas/audit.py`
- 🟡 Repositório de dados `db/research_repository.py`

**Comportamento esperado:**
🟡 Interface REST assíncrona, contratos validados via Pydantic, códigos semânticos (200 sucesso, 400 conteúdo ausente, 404 pesquisa inexistente, 502/504 falhas do LLM forte).

### 8.1 Contrato HTTP de entrada

```json
{ "id_pesquisa": "uuid", "ponto_id": "uuid | null", "criterios_minimos": 11 }
```

🟡 `criterios_minimos` inteiro estrito em `[1..12]`, default 11; inválido ⇒ 422 sem troca silenciosa.

### 8.2 Contrato do payload enviado ao LLM forte (v1.1)

```json
{
  "plano_geral": { "pedido_original": "...", "publico": "...", "recorte_temporal": "..." },
  "eixo_corrente": { "pergunta_principal": "...", "subperguntas": [] },
  "resultados_personas": { "historiador": { "...": "rodada corrente" } },
  "historico_rodadas": [
    {
      "rodada": 1,
      "coleta_id": "uuid",
      "criado_em": "ISO-8601",
      "conteudo_coletado": "texto integral da rodada",
      "resultados_personas": { "historiador": { "analise": "...", "conclusoes": [], "lacunas": [] } },
      "fontes": { "src_1": { "url": "...", "status": "read_ok", "body_hash": "...", "length": 12345 } },
      "trechos": { "chk_1": { "text": "...", "text_hash": "...", "start_offset": 0, "end_offset": 1500 } },
      "auditorias": [ { "id_auditoria": "...", "status": "reprovado", "criterios": [] } ]
    }
  ],
  "diario_acoes": {},
  "fontes": {},
  "trechos": {},
  "recencia": {},
  "rodadas_consideradas": [1, 2, 3, 4]
}
```

🟡 Regras do payload:
- 🟡 `fontes` (topo) é o **catálogo completo** de fontes da rodada corrente, sem `body`; todo `source_id` listado ali é citável. Enviar apenas o subconjunto citado pelas personas fazia o modelo classificar fontes legítimas como "desconhecidas" e reprovar `corroboracao_canonica` — proibido.
- 🟡 `trechos` (topo) são os excertos citados nas conclusões, com offsets/hash; a validação estrita de corpo/hash incide sobre as fontes efetivamente usadas como evidência, não sobre o catálogo inteiro.
- 🟡 `historico_rodadas` contém **todas** as rodadas do ponto, inclusive a corrente, em ordem crescente de `rodada`. A rodada corrente aparece marcada com `corrente: true` e traz `resultados_personas`/`trechos`/`fontes` completos; o parecer **da própria rodada corrente** não entra neste bloco (ele é reescrito a cada auditoria e invalidaria o cache de entrada idêntica) — os pareceres das rodadas anteriores entram integralmente em `auditorias`.
- 🟡 Nenhum campo de texto é cortado; `conteudo_coletado` e `trechos[*].text` vão na íntegra.
- 🟡 `fontes[*].body` pode ser omitido do JSON para economizar contexto **se e somente se** `trechos[*].text` carregar o material citado integral e os offsets/hashes permitirem recomposição; a omissão deve constar no parecer (`corpus_integral_entregue: false` + motivo) e impede aprovação automática de critérios factuais que dependam do corpo não entregue.
- 🟡 Conteúdo web é dado não confiável, delimitado no JSON.

### 8.3 Estados da API

- Estado vazio: 🟡 `id_pesquisa` ausente ⇒ 422; `criterios_minimos` inválido ⇒ 422.
- Estado de carregamento: 🟡 Conexão aberta durante consulta ao banco e inferência.
- Estado de erro: 🟡 Resposta estruturada com mensagem, código interno e detalhe da falha externa.
- Estado de sucesso: 🟡 HTTP 200 com resumo analítico completo, listagem dos pontos auditados e `rodadas_consideradas`.

---

## 9. Modelo de Dados

```
pontos {
  ponto_id: string (UUID)
  id_pesquisa: string (UUID)
  tema: string
  ponto_n: integer
  ponto: string
  status: string                   // aprovado | reprovado
  pontos_fracos: string (opcional)
  tentativas: integer              // rodadas de search já realizadas
  tentativas_auditoria: integer    // tentativas de auditoria (máx. 3)
}

conteudo_coletado {                // uma linha por rodada; append-only
  id: string (UUID)
  id_pesquisa: string (UUID)
  ponto_id: string (UUID)
  rodada: integer
  tema: string
  ponto: string
  conteudo_coletado: string
  urls_lidas: string (JSON)
  urls_fonte: string (JSON)
  metadados_coleta: string (JSON)  // fontes, trechos, resultados_personas, auditorias
}
```

**Persistência do parecer:** `metadados_coleta.auditorias` (append), com `id_auditoria`, `coleta_id`, `rodada`, `input_hash`, `criterios` (12), `criterios_aprovados`, `pontuacao_percentual`, `criterios_minimos`, `status`, `pontos_fracos`, `diagnostico`, `tarefas`, `rodadas_consideradas`, `valido`, `aplicado`.

**Migrações necessárias:** 🟡 Nenhuma alteração estrutural. `rodada` já existe; o novo campo `rodadas_consideradas` vive no JSON de auditoria.

---

## 9-A. Regra de staleness × acúmulo (resolução de conflito)

🟡 O adendo v5 determinava: *"Audit usa ... a coleta mais recente do ponto. Coletas antigas servem ao histórico e à comparação de avaliações; não são concatenadas como se todas as versões fossem fatos atuais."* Esta spec v1.1 **substitui** essa regra por:

| Aspecto | Regra v1.1 |
|---|---|
| Corpus entregue ao modelo | 🟡 **Todas** as rodadas, identificadas por `rodada`/`coleta_id`, sem truncamento |
| Fonte da verdade para aprovação | 🟡 Rodada **corrente** (fence de staleness preservado) |
| Uso das rodadas antigas | 🟡 Evidência complementar, histórico de pareceres e contexto de continuidade — nunca "fato atual" sem datação |
| Rótulo temporal | 🟡 Cada rodada traz `criado_em`; o modelo deve tratar dados antigos como históricos, sujeitos a atualidade (critério 3) |
| Desempate | 🟡 Em conflito entre rodadas, prevalece a mais recente, e o parecer deve declarar o conflito (critério 4) |

🟡 Justificativa: retries existem para **ampliar** a evidência. Descartar rodadas anteriores joga fora coleta já paga e produz reprovações falsas por "ausência de fonte" que existia em rodada anterior. O risco de tratar dado antigo como atual é mitigado pela datação explícita por rodada e pelo critério de atualidade (3) — não pela supressão do dado.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 LLM Forte OpenAI-compatible | Obrigatória | Erro 502 após 1+3 retries; auditoria abortada sem persistir deliberações |
| 🟡 SQLite Permanente | Obrigatória | Falha crítica de inicialização ou erro 500 |
| 🟡 Tabela de Credenciais Criptografada | Obrigatória | Erro 500 se chave/base URL não puder ser recuperada |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Pesquisa sem conteúdo coletado | 🟡 `conteudo_coletado` vazio para o `id_pesquisa` | HTTP 400 informando que a busca deve ser concluída antes |
| EC-02: Timeout do LLM forte | 🟡 Inferência acima do limite | Interrompe, 3 retries com backoff; persistindo, HTTP 504 |
| EC-03: LLM indisponível | 🟡 503 ou conexão recusada | Retries com espera exponencial; persistindo, HTTP 502 |
| EC-04: Falha no parser do JSON da auditoria | 🟡 Texto livre sem estrutura | Rotina de parsing corretivo; persistindo, aborta gravação e retorna HTTP 500 |
| EC-05: Conteúdo coletado vazio/corrompido na rodada corrente | 🟡 `conteudo_coletado` vazio ou ilegível | `reprovado` com anotação de falha de coleta, citando as rodadas anteriores disponíveis |
| EC-06 (v1.1): Nenhuma URL lida na rodada corrente, mas rodadas anteriores ricas | 🟡 `urls_lidas` vazio na rodada R | `reprovado` por ausência de evidência atual; parecer cita explicitamente as rodadas anteriores |
| EC-07 (v1.2): Corpus acumulado acima do orçamento | 🟡 `total_evidence_chars > AUDIT_EVIDENCE_BUDGET_CHARS` | Leitura em N passes com notas de todos eles; **sem corte e sem recusa por volume** |
| EC-08 (v1.1): Rodada anterior com esquema antigo | 🟡 `metadados_coleta` sem `resultados_personas` | Rodada entra no histórico marcada `legado: true`; não conta como persona satisfeita |
| EC-09 (v1.1): Retry focado em subconjunto de personas | 🟡 Rodada corrente com menos de 4 personas | Pacote recompõe personas ausentes das rodadas anteriores; `rodadas_consideradas` registra a origem |

---

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 Bearer token validado em middleware FastAPI.
- **Autorização:** 🟡 Qualquer cliente com token de serviço válido pode solicitar auditoria de pesquisas existentes.
- **Dados sensíveis:** 🟡 Dados públicos coletados da web; chaves do LLM forte em tabela criptografada com override por variáveis de ambiente.
- **Auditoria:** 🟡 Logs estruturados com `id_pesquisa`, `rodada`, tempo total de inferência, contagem de aprovados/reprovados e identificador das chamadas externas.

---

## 13. Plano de Rollout

- **Estratégia:** 🟡 Implantação modular no contêiner único, com testes de integração cobrindo múltiplas rodadas.
- **Como reverter (rollback):** 🟡 Restauração da versão anterior do contêiner, preservando o SQLite em volume permanente.
- **Monitoramento pós-deploy:** 🟡 Taxas 5xx, latência do LLM forte, distribuição aprovado/reprovado e **distribuição de `passes_evidencia`** (indicador de custo e de corpus grande).

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | 🟡 ⚠️ ABERTO: Deve o endpoint permitir auditoria individual por `ponto_id` além do lote completo? | Médio | dev-integrador | 2026-10-31 |
| OQ-02 | 🟡 ✅ RESOLVIDA: reprovação automática não depende de contagem fixa de respostas negativas; o corte é `criterios_minimos` (default 11/12) calculado no backend. | Alto | analista-research | 2026-10-27 |
| OQ-03 (v1.1) | 🟡 ⚠️ ABERTO: qual janela de contexto real será provisionada para o LLM forte, dado o corpus acumulado de até 4 rodadas? | Alto | dev-integrador | 2026-10-31 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Emprego de LLM forte para as 12 perguntas | Usar o LLM leve da busca | Discernimento conceitual superior e menos alucinação na triagem |
| 🟡 Atualização in-place do status na tabela `pontos` | Tabela separada de histórico | Esquema simples; histórico completo vive em `metadados_coleta.auditorias` |
| 🟡 Checklist fixo de 12 perguntas no prompt | Checklist dinâmico via payload | Padroniza a barra de qualidade |
| 🟡 (v1.1) Corpus = todas as rodadas | Corpus = última rodada (adendo v5) | Descartar retries produz reprovação falsa e desperdiça coleta paga |
| 🟡 (v1.1) Fence de aprovação permanece na rodada corrente | Aprovar com qualquer rodada | Evita aprovar ponto sem evidência atual |
| 🟡 (v1.2) Orçamento gera leitura em passes | Cortar para caber OU recusar o ponto | Corte oculto contamina o parecer; recusa por volume é truncamento disfarçado |
| 🟡 (v1.1) `rodadas_consideradas` no parecer | Não registrar | Permite auditar depois o que o modelo realmente viu |

---

## Apêndice

### Referências
- PRD Deep Research (`_reversa_sdd/prd.md` v2.0 — invariantes I-2, I-4, I-5)
- Spec do Search (`_reversa_sdd/sdd/endpoint-busca-com-personas.md` v1.1)
- Adendo v5 (2026-10-24) — **parcialmente superado** por §9-A
- Documentação da API OpenAI-compatible

### Mapa de conformidade do código

| Requisito | Arquivo | Ponto | Estado |
|---|---|---|---|
| RF-08 | `app/core/auditor.py` | `payload_context["resultados_personas"]` (~907) | ✅ consolidado por ponto |
| RF-09 | `app/core/auditor.py` | `ultima_coleta = coletas_ponto[-1]` (~562) | ❌ usa apenas a última rodada |
| RF-10 | `app/core/auditor.py` | `fontes_para_prompt` sem body (~901) | ⚠️ corpo omitido do prompt (ver §8.2) |
| RF-11 | `app/core/auditor.py` | `AUDIT_EVIDENCE_BUDGET_CHARS`, `AUDIT_JSON_BUDGET_CHARS`, `AUDIT_POINT_TIMEOUT_SECONDS`, `AUDIT_POINT_LEASE_SECONDS`, `_dividir_trechos_em_passes`, `_ler_evidencias_em_passes`, `_compactar_historico_para_prompt` | ✅ leitura integral em passes (sem corte, sem recusa); teto da decisão 600s + 120s por passe e lease 1800s; `TimeoutError` vira `AUDIT_TIMEOUT` (HTTP 504), nunca detalhe vazio |
| RF-13 | `app/core/auditor.py` | parecer em `metadados_coleta.auditorias` | ❌ `rodadas_consideradas` inexistente |

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 1.0 | 2026-10-21 | reversa-spec-sdd | Elaboração inicial da especificação do endpoint de auditoria |
| 1.1 | 2026-10-27 | reversa-spec-sdd | RF-08..RF-13; corpus acumulado de todas as rodadas; §9-A resolvendo conflito com o adendo v5; zero truncamento com insuficiência explícita |
