# CRITÉRIOS DE AUDITORIA — DEEP RESEARCH (v3)

Contrato normativo do Auditor. Precedência: `_reversa_sdd/prd.md` (I-2 v3, I-4, I-5) > este arquivo > specs de endpoint.

## Evidência disponível ao Auditor

O Auditor **não recebe texto bruto de páginas**. A Jina entrega o texto integral apenas em RAM ao especialista; o especialista devolve um **resumo denso** (`analise`) com dados, números, datas e fatos, mais:

- `urls_fonte` / `urls_utilizadas`: URLs que sustentaram o resumo.
- `urls_lidas` / `urls_lidas_nao_utilizadas`: URLs abertas e descartadas (inúteis ou repetidas).

O Auditor recebe a **soma acumulada dos resumos das 4 personas de todas as rodadas** do ponto, 100% intacta, mais o catálogo de URLs com `uso` (`utilizada` | `lida_nao_utilizada`). Não existe `trechos`, `chunk_id`, `body`, `body_hash` nem offsets. Julgamento de "suporte material" é feito sobre o conteúdo do resumo e a existência/uso da URL, nunca sobre excerto literal.

## Os 12 critérios

1. `clareza_tematica` — abordagem objetiva do eixo formulado e aderência às subperguntas do plano.
2. `corroboracao_canonica` — suporte em fontes primárias verificáveis; URL/título isolado não é prova factual, exige conteúdo no resumo.
3. `atualidade` — marcos e dados vigentes para o recorte e a data de referência; não tratar marco antigo como estado atual.
4. `ausencia_contradicoes` — coerência interna entre os dados apurados pelas personas.
5. `embasamento_factual` — ancoragem empírica demonstrável; separar ausência de evidência de falsidade, analogia de fato comprovado.
6. `aderencia_escopo` — atém-se ao pedido original, formato de entrega e público do plano.
7. `profundidade_analitica` — complexidade adequada, incertezas delimitadas sem reprovação artificial.
8. `precisao_dados` — exatidão numérica, métricas, datas e identificadores canônicos.
9. `neutralidade` — equilíbrio analítico, fatos separados de hipóteses.
10. `densidade_evidencias` — proporção satisfatória entre afirmações e URLs efetivamente utilizadas no resumo.
11. `declaracao_incertezas` — lacunas remanescentes expressamente identificadas e delimitadas.
12. `solidez_logica` — conclusões decorrem das evidências apresentadas.

## Portões determinísticos (antes do LLM)

1. As 4 personas canônicas presentes, cada uma com `analise` não vazia.
2. `conclusoes`, quando existirem, referenciam URLs do catálogo (`urls_fonte`), nunca chunks.
3. Todo item do catálogo com `status == read_ok`; `uso` coerente (`utilizada` exige presença em `urls_fonte` de alguma persona/rodada).
4. Nenhuma URL de rodada reprovada é marcada como inválida; `uso` é atributo do site, não do parecer.
5. Evidência da rodada corrente presente (fence de staleness), com histórico acumulado completo no payload.

Falha em portão gera reprovação com motivo explícito; nunca corte silencioso.
