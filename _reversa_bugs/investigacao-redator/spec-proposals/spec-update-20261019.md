# Relatório de Atualização de Especificações e Reconciliação Normativa (2026-10-19)

> **Sprint:** DOC-SPEC-01  
> **Data:** 2026-10-19  
> **Status:** CONCLUÍDO (Documentação atualizada e reconciliada)  

---

## 1. Escopo das Ações Executadas

Conforme autorização explícita do operador para atualização documental transversal de requisitos existentes sem alteração de código nem reabertura de ciclo de desenvolvimento:

1. **Adendo Normativo Aprovado Criado:**
   - Arquivo: `_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md` (rotulado como **DIRETRIZES APROVADAS**, com precedência normativa declarada).

2. **Reconciliação e Ajuste de Requisitos Existentes:**
   - **Feature 001 (`_reversa_forward/001-modulo-briefing/requirements.md`):**
     - Nota de vigência e histórico atualizados (Criação e Revisão do Briefing estritamente síncrona HTTP 200/201, sem 202/polling; restrição mantida de SERP-only sem leitura de 10 páginas integrais).
     - RN-02 e RF-02 ajustadas com delimitação explícita de escopo (Jina SERP apenas, sem Reader).
   - **Feature 002 (`_reversa_forward/002-investigacao-personas/requirements.md`):**
     - RN-05 ajustada para exigir 10 páginas integrais em texto limpo (corpo completo expurgando header, footer, nav, scripts, anúncios e lixo institucional).
     - RN-06 reafirmada com regra de teto de 3 queries por persona/ponto/rodada e decisão interna de suficiência (proibição de síntese analítica vazia).
     - RN-15 criada: Barreira de persistência individual das 4 personas antes do merge, mantendo status `SCRAPER_IN_PROGRESS` até todas persistirem.
     - Máquina de estados consolidada (4.3): removida regra contraditória que permitia transição parcial para `AUDIT_PENDING` com apenas 1 worker concluído; alinhada à RN-15 exigindo que o merge só ocorra após as 4 respostas persistidas do mesmo ponto e rodada.
     - Gherkin "Conclusão bem-sucedida da investigação global" atualizado para refletir a barreira das 4 personas e o merge pós-persistência.
   - **Feature 003 (`_reversa_forward/003-modulo-auditoria/requirements.md`):**
     - RN-301 alinhada com a barreira de persistência e merge pré-auditoria da RN-15.
     - RN-305 reafirmada: Teto de 4 tentativas totais (1 inicial + 3 retries) por ponto; quarta reprovação encerra busca e encaminha ao Redator sem reabrir loop.
3. **Adendo Normativo (`_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md`):**
   - 2.3: Removida redação absurda "sem inventar entidades, funções migrações não suportadas pelas evidências"; substituída por "sem inventar fatos nem perder rastreabilidade de origem"; schema/mecanismo de merge não prescrito.
   - 4.3: Removida exclusividade de implementação "via BackgroundTasks"; o mecanismo de assíncrono para disparo da investigação não é prescrito.
   - Adicionada seção 5 com 8 cenários verificados documentalmente (10 páginas texto integral + limpeza; 3 queries/parada cedo; resultado não vazio persistido por persona; nenhum audit antes 4 persistidas; merge preserva origens/contradições/lacunas; briefing síncrono SERP-only; investigação pode background; quarta reprovação continua Writer).
   - Pendências externas removidas (upstream <10 resultados, página ilegível, janela de contexto, falha fatal de persona, protocolo efetivo Jina); estes não são gaps do adendo normativo vigente.

---

## 2. Comandos de Verificação e Resultados

- **`git diff --check`:** Executado. Retornou código de saída `0` (sem erros de espaço em branco ou formatação).
- **Verificação de Links Internos:** Ancoragem verificada entre `requirements.md` das Features 001, 002 e 003 apontando para `_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md`.

---

## 3. Estado dos Artefatos Modificados/Criados

- `_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md` (Criado — normativo, precedência declarada)
- `_reversa_forward/001-modulo-briefing/requirements.md` (Modificado - Reconciliado)
- `_reversa_forward/002-investigacao-personas/requirements.md` (Modificado - Reconciliado + máquina de estados corrigida + Gherkin alinhado)
- `_reversa_forward/003-modulo-auditoria/requirements.md` (Modificado - Reconciliado)
- `_reversa_bugs/investigacao-redator/spec-proposals/spec-update-20261019.md` (Atualizado - Este relatório)

---

## 4. O que NÃO foi alterado/verificado

- **Nenhum código-fonte em `app/`, `frontend/`, `tests/` foi alterado** (preservados diffs pré-existentes).
- **Sem execução de testes operacionais ou deploys** (sprint estritamente documental).
