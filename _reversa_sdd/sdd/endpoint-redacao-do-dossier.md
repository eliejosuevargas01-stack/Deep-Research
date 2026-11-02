# Spec: Endpoint /api/v1/writer — Redação do Dossier

**Versão:** 1.2
**Status:** Planejada (revisão normativa v3 — resumos acumulados, sem bruto)
**Autor:** reversa-spec-sdd
**Data:** 2026-11-02 (original 2026-10-21)
**Reviewers:** Equipe Deep Research

---

## 1. Resumo

🟡 O endpoint `POST /api/v1/writer` constitui a quarta e última etapa do pipeline Deep Research, encarregado de sintetizar os achados investigativos e os pareceres de auditoria em um dossiê analítico abrangente, estruturado e com estrita rastreabilidade de fontes canônicas.

🟡 A funcionalidade recupera todos os dados consolidados da pesquisa, aciona a persona `redator final` via LLM forte OpenAI-compatible, persiste o documento final na tabela `pesquisa` e despacha o resultado via HTTP POST para o webhook de callback configurado.

🟡 **v1.1 (normativa):** o contexto de redação contém **todas as rodadas de coleta** de cada ponto, com a visão consolidada das 4 personas, sem truncamento e sem descarte de retries.

🟡 **v1.2 (normativa, v3):** o contexto do redator é composto pelos **resumos densos** (`analise`) das 4 personas de todas as rodadas de cada ponto, mais as listas de URLs `utilizadas` e `lidas_nao_utilizadas` e o catálogo com uso. Não há corpo de página, excertos nem chunks no contexto, e não há truncamento. Precedência: [`prd.md`](../prd.md) I-2 v3 > [`app/CRITERIA.md`](../../app/CRITERIA.md) > esta spec.

---

## 2. Contexto e Motivação

**Problema:**
🟡 A redação manual de relatórios de inteligência a partir de fontes dispersas consome dias de trabalho, introduz viés de síntese e frequentemente perde a correspondência direta entre afirmações do texto e URLs originais verificadas.

**Evidências:**
🟡 Ferramentas existentes operam como caixas-pretas que não fornecem dossiês auditados ponto a ponto, impedindo a verificação de fontes primárias e dificultando a integração automatizada com sistemas legados de publicação.

**Por que agora:**
🟡 Concluir o pipeline com geração automática de dossiê auditado e entrega via webhook permite que analistas e desenvolvedores recebam pesquisas finalizadas em menos de 10 minutos.

**Motivação da revisão v1.1:**
🟡 O writer montava o contexto apenas a partir da coleta mais recente de cada ponto. Em pesquisas com retries, isso descartava material já coletado e pago — o dossiê saía mais pobre que a evidência disponível, e afirmações sustentadas em rodadas anteriores desapareciam sem qualquer registro.

**Motivação da revisão v1.2 (v3):**
🟡 O bruto das páginas deixou de ser persistido: o Search entrega resumo denso e catálogo de URLs. O writer não precisa de mais que isso — a redação cita URL, não excerto, e o valor analítico está no resumo. O contexto fica menor, estável e sem risco de carregar páginas que nenhum estágio a jusante pode reabrir ou verificar. A v1.2 remove do contrato de redação os campos de corpo, excertos e chunks que só existiam para alimentar o antigo corpus.

---

## 3. Goals (Objetivos)

- [ ] G-01: 🟡 Gerar um dossiê completo estruturado em Markdown a partir de todos os pontos auditados da pesquisa.
- [ ] G-02: 🟡 Associar e citar explicitamente fontes canônicas verificadas em 100% dos tópicos abordados.
- [ ] G-03: 🟡 Persistir o dossiê na tabela `pesquisa` e despachar o documento para o webhook de callback configurado.
- [ ] G-04 (v1.1): 🟡 Consumir todas as rodadas de coleta de cada ponto, sem perda.
- [ ] G-05 (v1.1): 🟡 Nunca truncar resumo; volume excessivo gera estado honesto (`incompleto`/falha técnica), nunca dossiê parcial apresentado como final.
- [ ] G-06 (v1.2): 🟡 Redigir exclusivamente a partir de resumos e listas de URLs; nenhum corpo de página entra no contexto.

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---|---|---|---|
| 🟡 Proporção de pontos com fontes canônicas citadas | 0% | = 100% | 2026-10-31 |
| 🟡 Tempo de resposta da geração e despacho | N/A | < 240s | 2026-10-31 |
| 🟡 Taxa de sucesso no disparo do webhook | 0% | = 100% | 2026-10-31 |
| 🟡 Rodadas de coleta presentes no contexto de redação | 1 (última) | = 100% das rodadas | 2026-10-31 |
| 🟡 Resumo truncado no dossiê | > 0 | = 0 | 2026-10-31 |
| 🟡 Campos de corpo bruto no contexto do redator (v1.2) | não medido | = 0 | 2026-11-02 |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: 🟡 O sistema não deve processar redação para pesquisas com pontos pendentes de auditoria.
- NG-02: 🟡 O sistema não deve executar novas consultas de busca ou chamadas ao Jina durante a redação.
- NG-03: 🟡 O sistema não deve aplicar fallback hardcoded para a URL do webhook ou parâmetros do modelo.
- NG-04: 🟡 O sistema não deve alterar notas, deliberações, resumos ou o catálogo de URLs armazenados em `pontos` e `conteudo_coletado`.
- NG-05 (v1.1): 🟡 O sistema **não** deve escolher "a melhor rodada" por ponto; todas compõem o contexto.
- NG-06 (v1.1): 🟡 O sistema **não** deve publicar dossiê parcial como `concluido` quando o contexto não pôde ser integralmente considerado.
- NG-07 (v1.2): 🟡 O sistema **não** deve ler, solicitar ou reconstruir corpo de página, excertos ou chunks para "enriquecer" a redação. A ausência desses campos é o contrato.

---

## 5. Usuários e Personas

**Usuário primário:** 🟡 Analista de Research: profissional de inteligência que consome o dossiê finalizado e necessita de links diretos para cada fonte canônica.
**Usuário secundário:** 🟡 Redator/Dev integrador: desenvolvedor que automatiza a recepção do dossiê via webhook para ingestão em repositórios corporativos.
**Persona do sistema:** 🟡 Persona `redator final`: especialista em síntese narrativa analítica, ordenação lógica de argumentos, clareza expositiva e ancoragem estrita em evidências comprovadas.

**Jornada atual (sem a feature):**
1. 🟡 O analista copia fragmentos de texto de dezenas de abas.
2. 🟡 O analista gasta horas organizando citações e formatando parágrafos.
3. 🟡 O analista envia o relatório estático por e-mail, sem rastreabilidade de entrega.

**Jornada futura (com a feature):**
1. 🟡 O usuário ou rotina executa `POST /api/v1/writer` informando o `id_pesquisa`.
2. 🟡 O sistema consolida os **resumos de todas as rodadas auditadas** e o catálogo de URLs, e invoca a persona `redator final`.
3. 🟡 O sistema persiste o dossiê no SQLite permanente e entrega via POST no webhook.

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | 🟡 O sistema deve receber `POST /api/v1/writer` contendo o campo obrigatório `id_pesquisa`. | Must | 🟡 HTTP 200 com dossiê e metadados de entrega. |
| RF-02 | 🟡 O sistema deve verificar que todos os N pontos estão concluídos (`aprovado` ou `reprovado`), rejeitando com HTTP 400 se houver pendentes. | Must | 🟡 Pesquisa com pontos sem deliberação ⇒ interrupção indicando os pendentes. |
| RF-02a (v1.3) | 🟡 Ponto `reprovado` **não** bloqueia a redação: o dossiê é gerado com ressalvas explícitas (`## Ressalvas da auditoria`) e publicado mesmo com autoavaliação abaixo do limiar (`status_pipeline=incompleto`). Ponto sem coleta utilizável é omitido e listado nas ressalvas. | Must | 🟡 Pesquisa com 1 ponto aprovado e 1 reprovado no teto ⇒ dossiê publicado citando o aprovado e declarando o reprovado nas ressalvas. |
| RF-03 | 🟡 O sistema deve recuperar e concatenar tema, enunciados dos pontos, pareceres de auditoria, **resumos das personas de todas as rodadas** e as listas de URLs `utilizadas`/`lidas_nao_utilizadas` com o catálogo do ponto. | Must | 🟡 Contexto textual completo, sem omissão de referências e sem corpo de página. |
| RF-04 | 🟡 O sistema deve invocar o LLM forte com a persona `redator final`, carregando configuração de `PERSONAS_CONFIG` ou tabela de credenciais sem fallback hardcoded. | Must | 🟡 Instruções formais de densidade informacional e citação de fontes canônicas aplicadas. |
| RF-05 | 🟡 O sistema deve processar a saída do LLM com parser estruturado, validando sumário executivo, desenvolvimento dos eixos e seção de referências canônicas. | Must | 🟡 Integridade das seções obrigatórias confirmada e texto extraído. |
| RF-06 | 🟡 O sistema deve persistir o dossiê e a data de conclusão no registro da tabela `pesquisa`. | Must | 🟡 Documento e timestamp de encerramento gravados. |
| RF-07 | 🟡 O sistema deve despachar POST com o payload estruturado do dossiê para a URL de webhook configurada, registrando sucesso ou falha. | Must | 🟡 Envio com política de retries e registro do status HTTP obtido. |

### 6.2 Requisitos das revisões v1.1 e v1.2/v3 (normativos)

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-08 | 🟡 O contexto de redação deve conter **todas as rodadas** de coleta de cada ponto (`rodada` 1..R), cada uma com os **resumos das 4 personas** (`resultados_personas`), o catálogo de URLs com uso e o parecer de auditoria aplicável. | Must | 🟡 Ponto com 3 retries ⇒ contexto contém 4 rodadas identificadas; teste falha se alguma faltar. |
| RF-09 | 🟡 Nenhum campo textual pode ser truncado no contexto de redação. Proibido `slice`, cap de caracteres ou resumo automático sobre `analise`. | Must | 🟡 Resumo de 40.000 caracteres entra íntegro no contexto. |
| RF-10 | 🟡 O dossiê deve distinguir, quando relevante, evidência da rodada corrente e evidência histórica de rodadas anteriores (datação explícita), sem descartar as anteriores. | Should | 🟡 Afirmação sustentada apenas em rodada anterior traz marcação de origem/rodada. |
| RF-11 | 🟡 Se o acervo acumulado de resumos exceder o limite operacional do LLM, o sistema deve retornar estado honesto (`incompleto` ou falha técnica) com diagnóstico; nunca publicar dossiê parcial como `concluido`. | Must | 🟡 Acervo acima do limite ⇒ resposta não publica `concluido`; diagnóstico registrado; nada truncado silenciosamente. |
| RF-12 | 🟡 O `input_hash` do contexto de redação deve cobrir os resumos e as listas de URLs de todas as rodadas, de modo que uma nova rodada invalide corretamente um dossiê anterior. | Must | 🟡 Nova rodada ⇒ recomputação fresca diverge do hash publicado anteriormente. |
| RF-13 (v3) | 🟡 O contexto de redação não deve conter corpo de página, excertos, offsets nem chunks. Toda citação do dossiê referencia URL do catálogo; nenhum campo tenta reconstruir passagem literal. | Must | 🟡 Inspeção do contexto não encontra campos de bruto; citação sem URL do catálogo é rejeitada pelo parser. |

### 6.3 Fluxo Principal (Happy Path)

1. 🟡 O usuário/serviço envia `POST /api/v1/writer` com `id_pesquisa`.
2. 🟡 O sistema confirma que todos os N pontos estão finalizados.
3. 🟡 O sistema carrega, por ponto, **todas** as rodadas de coleta (resumos das 4 personas), os pareceres e o catálogo de URLs.
4. 🟡 O sistema monta o contexto estruturado (plano, pontos, rodadas de resumos, catálogo de URLs, pareceres) e calcula o `input_hash`.
5. 🟡 O modelo produz o dossiê em Markdown com citações explícitas das fontes canônicas.
6. 🟡 O sistema valida o documento e grava o texto integral na tabela `pesquisa`.
7. 🟡 O sistema envia POST ao webhook e retorna HTTP 200.

### 6.4 Fluxos Alternativos

**Fluxo Alternativo A — Ponto reprovado na auditoria:**
1. 🟡 O sistema identifica pontos `reprovado` com `pontos_fracos`.
2. 🟡 O LLM redige seção de ressalvas metodológicas, sem descartar o restante da pesquisa; as rodadas daquele ponto permanecem no contexto.

**Fluxo Alternativo B — Ponto com retries acumulados (v1.1):**
1. 🟡 O ponto tem rodadas 1..R, sendo a R a que recebeu o parecer aplicado.
2. 🟡 Todas entram no contexto; o parecer aplicado refere-se à rodada R.
3. 🟡 O dossiê pode citar evidência de rodadas anteriores, com datação.

**Fluxo Alternativo C — Contexto acima do limite (v1.1):**
1. 🟡 O contexto acumulado excede o limite do provedor.
2. 🟡 O sistema retorna `incompleto` com diagnóstico acionável e **não** publica dossiê parcial.

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Performance | Latência total < 240s por dossiê de 5 pontos | Inclui raciocínio do LLM forte e despacho |
| RNF-02 | 🟡 Timeout operacional | 600s por chamada externa | Conforme PRD |
| RNF-03 | 🟡 Resiliência | 1 tentativa inicial + 3 retries com backoff | LLM e webhook |
| RNF-04 | 🟡 Persistência | SQLite permanente | Documento consultável após reinício |
| RNF-05 | 🟡 Isolamento modular | Monolito modular sem dependência de outros endpoints | Lê diretamente a base |
| RNF-06 (v1.1) | 🟡 Zero truncamento | 0 caracteres cortados | Insuficiência explícita no lugar de corte |
| RNF-07 (v1.1) | 🟡 Determinismo do `input_hash` | Recomputação fresca idêntica para o mesmo acervo de resumos | Cobre todas as rodadas |

---

## 8. Design e Interface

**Componentes afetados:**
- 🟡 Rota FastAPI `POST /api/v1/writer`
- 🟡 Módulo de redação `core/writer.py`
- 🟡 Cliente de webhook `services/webhook_client.py`
- 🟡 Repositório de dados `db/research_repository.py`

**Comportamento esperado:**
🟡 Interface REST assíncrona com validação Pydantic e códigos semânticos (200 sucesso, 400 pontos incompletos, 404 inexistente, 502/504 falhas do LLM).

### 8.1 Contrato do contexto de redação (v1.2)

```json
{
  "plano": { "pedido_original": "...", "publico": "...", "recorte_temporal": "...", "eixos": [] },
  "recencia_global": { "data_referencia": "YYYY-MM-DD", "politica": "auto", "data_mais_recente_fonte": "YYYY-MM-DD" },
  "pontos": [
    {
      "ponto_n": 1,
      "ponto_id": "uuid",
      "pergunta": "...",
      "status": "aprovado",
      "eixo": {},
      "auditoria_atual": { "id_auditoria": "...", "status": "aprovado", "criterios_aprovados": 11, "pontuacao_percentual": 91.67, "pontos_fracos": null, "tarefas": [], "criterios_reprovados": [] },
      "urls_utilizadas": [],
      "urls_lidas_nao_utilizadas": [],
      "rodadas": [
        {
          "rodada": 1,
          "coleta_id": "uuid",
          "criado_em": "ISO-8601",
          "resultados_personas": {
            "historiador": {
              "analise": "resumo denso com dados, números, datas e fatos",
              "conclusoes": [],
              "lacunas": [],
              "urls_utilizadas": [],
              "urls_lidas_nao_utilizadas": []
            }
          },
          "catalogo_urls": [
            { "url": "https://...", "titulo": "...", "status": "read_ok", "uso": "utilizada", "data_fonte": "YYYY-MM-DD" }
          ],
          "auditoria_da_rodada": { "id_auditoria": "...", "status": "reprovado", "criterios": [] }
        }
      ],
      "recencia": {}
    }
  ]
}
```

🟡 Regras:
- 🟡 `pontos[*].rodadas` contém **todas** as rodadas, ordem crescente, sem omissão.
- 🟡 `urls_utilizadas` e `urls_lidas_nao_utilizadas` no nível do ponto consolidam todas as rodadas; `catalogo_urls` por rodada preserva a origem e a `data_fonte`.
- 🟡 Nenhum campo de corpo, excerto, offset ou chunk existe no contexto. Não há flag de "corpus integral entregue" porque não há corpus a omitir.
- 🟡 Nenhum texto é cortado; `analise` vai na íntegra em todas as rodadas.

### 8.2 Estados da API

- Estado vazio: 🟡 `id_pesquisa` ausente ⇒ 422.
- Estado de carregamento: 🟡 Conexão ativa durante inferência e tentativas de webhook.
- Estado de erro: 🟡 Resposta estruturada com mensagem, código interno e detalhe da falha externa.
- Estado de sucesso: 🟡 HTTP 200 com documento consolidado, contagem de caracteres, `rodadas_consideradas` e status de entrega.

---

## 9. Modelo de Dados

```
pesquisa {
  id_pesquisa: string (UUID)
  tema: string
  criado_em: timestamp
  dossier_final: string (Markdown)
  concluido_em: timestamp
  webhook_status: string           // entregue | pendente_reenvio | falha_definitiva
}

pontos {
  ponto_id: string (UUID)
  id_pesquisa: string (UUID)
  tema: string
  ponto_n: integer
  ponto: string
  status: string                   // aprovado | reprovado
  pontos_fracos: string (opcional)
  tentativas: integer
}

conteudo_coletado {                // uma linha por rodada; append-only
  id: string (UUID)
  id_pesquisa: string (UUID)
  ponto_id: string (UUID)
  rodada: integer
  conteudo_coletado: string
  urls_lidas: string (JSON)
  urls_fonte: string (JSON)
  metadados_coleta: string (JSON)  // fontes (catálogo com uso), resultados_personas, auditorias
}
```

**Migrações necessárias:** 🟡 Nenhuma alteração estrutural; o writer apenas lê todas as rodadas.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 LLM Forte OpenAI-compatible | Obrigatória | HTTP 502 após 1+3 retries; geração abortada |
| 🟡 Webhook de Callback | Obrigatória | Dossiê gravado com `webhook_status=falha_definitiva` e alerta no HTTP 200 |
| 🟡 SQLite Permanente | Obrigatória | Falha crítica de inicialização ou HTTP 500 |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Pontos não auditados | 🟡 Status pendente | HTTP 400 informando que todos devem ser auditados |
| EC-02: Timeout do LLM | 🟡 Geração atinge o limite | 3 retries com backoff; persistindo, HTTP 504 |
| EC-03: Webhook indisponível | 🟡 503 ou recusa | 3 retries; persistindo, dossiê gravado e status de falha registrado |
| EC-04: Parser do dossiê falha | 🟡 Saída corrompida | Recuperação sintática; persistindo, cancela gravação e retorna HTTP 500 |
| EC-05: Webhook não configurado | 🟡 Configuração ausente | Recusa informando ausência, sem fallback |
| EC-06 (v1.1): Ponto com 4 rodadas | 🟡 Retries acumulados | Todas as 4 no contexto; dossiê pode citar qualquer uma com datação |
| EC-07 (v1.1): Contexto acima do limite | 🟡 Volume acumulado excede o provedor | Estado `incompleto` com diagnóstico; nada truncado; nada publicado como `concluido` |
| EC-08 (v1.1): Rodada antiga sem `resultados_personas` | 🟡 Esquema legado | Rodada entra marcada `legado: true`; não satisfaz a prontidão de personas |
| EC-09 (v1.2): Rodada anterior à v3 com corpo bruto persistido | 🟡 `metadados_coleta` contém campos de bruto | O bruto legado não é lido nem serializado; a redação usa apenas `analise` e URLs do catálogo |

---

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 Bearer token validado em middleware.
- **Autorização:** 🟡 Clientes com token de serviço válido podem solicitar a redação de pesquisas auditadas.
- **Dados sensíveis:** 🟡 Dados públicos coletados; URLs de webhook e credenciais de modelo em tabela criptografada ou variáveis de ambiente.
- **Auditoria:** 🟡 Logs com `id_pesquisa`, tempo total, código HTTP do webhook, quantidade de caracteres e rodadas consideradas.

---

## 13. Plano de Rollout

- **Estratégia:** 🟡 Implantação modular com testes de integração ponta a ponta incluindo múltiplas rodadas.
- **Como reverter (rollback):** 🟡 Restauração da versão anterior, preservando o SQLite em volume permanente.
- **Monitoramento pós-deploy:** 🟡 Taxas 5xx, tempo de resposta do webhook, integridade das referências e taxa de estado `incompleto`.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | 🟡 ⚠️ ABERTO: o payload do webhook deve incluir assinatura HMAC SHA-256? (implementado como opcional; validar obrigatoriedade) | Médio | dev-integrador | 2026-10-31 |
| OQ-02 | 🟡 ⚠️ ABERTO: política de reenvio em HTTP 429 do webhook | Médio | dev-integrador | 2026-10-31 |
| OQ-03 (v1.2) | 🟡 ⚠️ ABERTO: qual janela de contexto será provisionada para o redator com o acervo de resumos de 4 rodadas por ponto e N=5? | Alto | dev-integrador | 2026-11-02 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Exigência de 100% dos pontos finalizados | Redigir com pontos parciais | Assegura integridade analítica planejada e auditada |
| 🟡 Persistir o dossiê mesmo com falha no webhook | Cancelar gravação | Preserva o resultado para reenvio |
| 🟡 Markdown estruturado com notas canônicas | PDF binário | Facilita ingestão por terceiros |
| 🟡 (v1.1) Incluir todas as rodadas no contexto | Usar só a coleta mais recente | Descartar rodadas empobrece o dossiê e perde evidência paga |
| 🟡 (v1.1) Estado `incompleto` em vez de dossiê parcial | Truncar para caber e publicar | Publicar parcial como final é pior que falhar honestamente |
| 🟡 (v1.1) `input_hash` cobre todas as rodadas | Hash só da rodada corrente | Nova rodada deve invalidar dossiê anterior |
| 🟡 (v1.2) Contexto = resumos + catálogo de URLs | Corpo, excertos e chunks por rodada | O bruto não existe fora da RAM; o resumo carrega o valor analítico e a URL é a âncora |
| 🟡 (v1.2) Citação por URL do catálogo | Citação literal por offset | Offset não sobrevive ao descarte do bruto; URL é verificável por terceiros |

---

## Apêndice

### Referências
- PRD Deep Research (`_reversa_sdd/prd.md` — I-2 v3, I-4, I-5)
- Adendo v9 — bruto volátil e contrato de dados v3 (`_reversa_sdd/sdd/addendum-confiabilidade-20261102-v9-bruto-volatil.md`)
- Critérios de auditoria (`app/CRITERIA.md` v3)
- Spec do Search (`_reversa_sdd/sdd/endpoint-busca-com-personas.md` v1.2)
- Spec do Audit (`_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md` v1.2)
- Documentação da API OpenAI-compatible

### Mapa de conformidade do código

| Requisito | Arquivo | Ponto | Estado |
|---|---|---|---|
| RF-08 | `app/core/writer.py` | `_verificar_prontidao` (`ultima_coleta`, ~252) | ⚠️ anexa `historico_coletas` mas só usa a última |
| RF-08 | `app/core/writer.py` | `_montar_contexto_estruturado` (~369) | ❌ serializa apenas a rodada corrente |
| RF-09 | `app/core/writer.py` | `sintese_bruta_workers` (~452) | ✅ sem corte |
| RF-12 | `app/core/writer.py` | `_calcular_input_hash` (~532) | ❌ não cobre rodadas anteriores |
| RF-11 | `app/core/writer.py` | orçamento de avaliação (~1119) | ✅ bloqueia publicação sem resultado válido |
| RF-13 | `app/core/writer.py` | projeção de fontes/chunks (~276, ~596) | ❌ ainda serializa corpo/excertos no contexto; remover na migração v3 |

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 1.0 | 2026-10-21 | reversa-spec-sdd | Elaboração inicial da especificação do endpoint de redação |
| 1.1 | 2026-10-27 | reversa-spec-sdd | RF-08..RF-12; contexto com todas as rodadas; zero truncamento; `input_hash` sobre o corpus acumulado |
| 1.2 | 2026-11-02 | reversa-spec-sdd | Norma v3: contexto = resumos das 4 personas de todas as rodadas + listas de URLs + catálogo; remove corpo/excertos/chunks; RF-13; sem truncamento |
