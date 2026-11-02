# Adendo v9 — Bruto volátil e contrato de dados v3

> 🟡 PLANEJADO. Documento normativo. Data: 2026-11-02. Status: vigente.

**Precedência:** [`prd.md`](../prd.md) (I-2 v3, I-4, I-5) > [`app/CRITERIA.md`](../../app/CRITERIA.md) v3 > specs de endpoint > este adendo.

---

## 1. Declaração da norma v3

🟡 A v3 encerra o modelo de **corpus bruto persistido**. O texto integral devolvido pela Jina (SERP com `include_content` e Reader) é insumo **volátil de RAM**: existe apenas durante a rodada da persona que o leu e é descartado assim que o resumo é produzido.

🟡 O que atravessa estágios é conhecimento destilado:

| Artefato | Conteúdo | Persistência |
|---|---|---|
| `resultados_personas[*].analise` | Resumo denso com afirmações, números, métricas, datas, identificadores, tensões entre fontes e o que cada URL sustenta | SQLite, append-only por rodada |
| `resultados_personas[*].urls_utilizadas` | URLs que sustentaram o resumo | SQLite |
| `resultados_personas[*].urls_lidas_nao_utilizadas` | URLs abertas e descartadas por inutilidade ou repetição | SQLite |
| `metadados_coleta.fontes` | Catálogo do ponto: `url`, `titulo`, `status` (`read_ok`), `uso` (`utilizada` \| `lida_nao_utilizada`), `data_fonte` | SQLite, consolidado por rodada |
| `metadados_coleta.auditorias` | Pareceres das 12 perguntas | SQLite, append |

🟡 Nenhum desses artefatos é cópia, recorte ou hash de página. São anotações sobre páginas.

---

## 2. Regras superadas (histórico)

🟡 As regras abaixo deixam de valer na íntegra. Permanecem apenas como registro histórico; qualquer implementação que as aplique viola a v3.

| Documento | Regra superada | Regra vigente (v3) |
|---|---|---|
| Adendo v4 (Search) | Persistir corpos no mapa de fontes da coleta; excertos com hash e offsets verificáveis no corpo | Corpo só em RAM; persiste resumo + catálogo de URLs com uso |
| Adendo v5 (Audit) | Auditoria sobre a coleta mais recente, exigindo corpo Reader/cache e excertos com hash/offset | Auditoria sobre a soma dos resumos de todas as rodadas + catálogo de URLs |
| Adendo v6 (Writer) | Redação usando somente a coleta atual | Redação usando resumos de todas as rodadas + listas de URLs |
| Spec do Search v1.1 | `metadados_coleta` com `fontes[*].body`, `trechos`, `selecao_contexto` | `metadados_coleta.fontes` com `uso`; sem campos de corpo, excerto ou posição |
| Spec do Audit v1.1 | Corpus canônico no payload e leitura da evidência em N passes | Resumos acumulados + catálogo; volume acima da janela gera insuficiência explícita, sem passes |
| Spec do Writer v1.1 | Contexto com `fontes` e `trechos` por rodada | Contexto com `resultados_personas` e `catalogo_urls` por rodada |

🟡 Os invariantes I-1 (paridade Jina), I-3 (execution_mode), I-4 (agregação das 4 personas) e I-5 (histórico append-only) **não** são afetados. O I-2 permanece, com escopo deslocado: o zero truncamento incide sobre o resumo e as listas de URLs, não sobre um corpo que não é retido.

---

## 3. Contrato de dados do Search

🟡 Cada linha de `conteudo_coletado` representa **uma rodada** de um ponto e contém:

```
id, id_pesquisa, ponto_id, rodada, tema, ponto,
conteudo_coletado,      // síntese da rodada a partir dos resumos; nunca corpo de página
urls_lidas,             // todas as URLs consultadas na rodada
urls_fonte,             // URLs que sustentaram os resumos
metadados_coleta,       // JSON: versao=3, fontes, resultados_personas, diario_acoes, recencia, auditorias
criado_em
```

🟡 `metadados_coleta` na versão 3:

```json
{
  "versao": 3,
  "fontes": {
    "src_1": {
      "source_id": "src_1",
      "url": "https://...",
      "titulo": "...",
      "status": "read_ok",
      "uso": "utilizada",
      "data_fonte": "YYYY-MM-DD"
    }
  },
  "resultados_personas": {
    "historiador": {
      "analise": "resumo denso com dados, números, datas e fatos",
      "conclusoes": [],
      "lacunas": [],
      "motivo_parada": "...",
      "sucesso": true,
      "urls_utilizadas": [],
      "urls_lidas_nao_utilizadas": [],
      "queries_executadas": 3
    }
  },
  "diario_acoes": { "historiador": [] },
  "recencia": {},
  "auditorias": []
}
```

🟡 Regras de integridade:
- 🟡 `uso` é atributo da URL no ponto, não do parecer: `utilizada` quando citada por alguma persona/rodada; `lida_nao_utilizada` caso contrário.
- 🟡 `urls_utilizadas` e `urls_lidas_nao_utilizadas` são subconjuntos das URLs com `status=read_ok` no catálogo.
- 🟡 Rodada nova é **inserção**; nunca `UPDATE` que substitua resumo, catálogo ou lista de rodada anterior. Só `metadados_coleta.auditorias` recebe acréscimo.
- 🟡 Campo de corpo, excerto, offset, hash de corpo ou seleção de excertos por orçamento é **violação de schema**; a rodada é rejeitada na escrita.

---

## 4. Ciclo de vida do bruto

🟡 Ordem obrigatória, por persona:

1. A tool lê a página e devolve o texto integral **em memória**.
2. O LLM consome o texto integral e produz `analise` + listas de URLs.
3. O buffer do bruto é liberado **antes** da consolidação do ponto.
4. A rodada persiste apenas resumo, listas e catálogo.

🟡 Proibições:
- 🟡 Gravar bruto em arquivo temporário, cache em disco, log, trace, artefato de teste, backup ou corpo de resposta HTTP.
- 🟡 Reter bruto "para o caso de retry". Retry que precise reler página refaz a chamada à Jina; não há reidratação a partir do banco.
- 🟡 Truncar o bruto para caber em contexto: ele não vai para contexto de estágio nenhum. O limite do provedor incide sobre o resumo, e o comportamento é insuficiência explícita.
- 🟡 Promover bruto parcial a registro quando a persona falha antes do resumo.

🟡 Diagnóstico registra metadados de leitura (URL, status, tamanho, latência), nunca conteúdo.

---

## 5. Handoff para o Audit

🟡 O auditor recebe:
- 🟡 Soma acumulada dos resumos das 4 personas de **todas** as rodadas do ponto, em ordem crescente de `rodada`.
- 🟡 Catálogo consolidado de URLs com `uso` e catálogo por rodada com `data_fonte`.
- 🟡 Pareceres anteriores (o da rodada corrente não entra, para preservar o cache de entrada idêntica).
- 🟡 Plano geral e eixo corrente.

🟡 O auditor **não** recebe corpo, excerto, offset ou hash. A ausência não é insuficiência de evidência; julgamento de suporte material usa o conteúdo do resumo e a existência/uso da URL.

🟡 Antes do LLM, rodam os cinco portões determinísticos de `app/CRITERIA.md`: personas canônicas com `analise` não vazia; conclusões citando URLs do catálogo; catálogo `read_ok` com `uso` coerente; URL de rodada reprovada não invalidada; evidência da rodada corrente presente com histórico completo. Portão violado ⇒ reprovação com motivo explícito, sem inferência.

🟡 Staleness preservado: a aprovação exige evidência da rodada corrente, ainda que o parecer possa citar rodada antiga com datação.

---

## 6. Handoff para o Writer

🟡 O redator recebe, por ponto:
- 🟡 `resultados_personas` das 4 personas em **todas** as rodadas.
- 🟡 `urls_utilizadas` e `urls_lidas_nao_utilizadas` consolidados no ponto.
- 🟡 `catalogo_urls` por rodada (origem e `data_fonte`).
- 🟡 Parecer aplicado e pareceres por rodada.

🟡 Citação do dossiê é por URL do catálogo, nunca por excerto ou offset. Nenhum corpo de página entra no contexto; não há flag de "corpus integral entregue" porque não há corpus a omitir.

🟡 Volume acima do limite do provedor ⇒ estado `incompleto` com diagnóstico; nunca dossiê parcial publicado como `concluido`.

---

## 7. Verificação de conformidade

🟡 Uma implementação está conforme a v3 quando:

1. 🟡 O schema de `metadados_coleta` não admite campos de corpo, excerto, offset ou hash de corpo; rodada com esses campos é rejeitada.
2. 🟡 Auditor e writer montam contexto a partir de `resultados_personas[*].analise` + listas de URLs + catálogo, sem consultar corpo.
3. 🟡 Nenhum caminho de código grava bruto em disco, log ou artefato após o resumo.
4. 🟡 Ponto com 3 retries entrega 4 rodadas de resumos ao audit e ao writer.
5. 🟡 Portões determinísticos de `app/CRITERIA.md` executam antes da chamada ao LLM.
6. 🟡 Volume de resumos acima da janela produz insuficiência explícita, não passes nem corte.
7. 🟡 Busca pelos nomes de campos do modelo antigo (listados no Apêndice — registros superados) retorna zero ocorrências fora das seções históricas.

---

## Apêndice — registros superados (histórico)

🟡 **SUPERADO.** Termos mantidos apenas para rastrear a decisão; não são normativos.

| Termo/regra | Onde vivia | Substituído por |
|---|---|---|
| `body` / `body_hash` no catálogo de fontes | Adendo v4, spec do Search v1.1 | `fontes` com `uso`; corpo só em RAM |
| `trechos` / `chunk_id` / offsets | Adendo v4, specs Search/Audit/Writer v1.1 | `analise` (resumo denso) + listas de URLs |
| `selecao_contexto` por orçamento de chars | Spec do Search v1.1 | Sem seleção de excertos; resumo integral |
| `passes_evidencia` / leitura em N passes | Spec do Audit v1.1 (RF-11) | Insuficiência explícita quando o acervo de resumos excede a janela |
| Corpus canônico de páginas no Audit | Adendo v5, spec do Audit v1.1 §8.2 | Resumos acumulados + catálogo de URLs |
| Coleta atual como único insumo do Writer | Adendo v6 | Resumos de todas as rodadas + listas de URLs |

---

## Histórico de Revisões

| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| v9 | 2026-11-02 | reversa-spec-sdd | Declara a norma v3; supera adendos v4/v5/v6 e seções de corpus das specs; fixa contrato de dados, ciclo de vida do bruto e handoffs de audit/writer |
