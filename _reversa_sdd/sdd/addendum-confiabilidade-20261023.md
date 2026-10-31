# Adendo Normativo de SDD — Atualização dos Contratos de Confiabilidade
**Referência:** Backlog DR-001 a DR-015 / Inspeção `confiabilidade-20261023`  
**Data da Aprovação:** 23/10/2026  
**Status:** Veredito Normativo e Vinculante (Preserva as specs originais e formaliza os deltas aprovados pelo usuário)

---

## 1. Contexto e Motivação

As especificações originais em `_reversa_sdd/sdd/` foram elaboradas na fase inicial do projeto. O ensaio real da pesquisa `12fea1e2-76bb-4693-958e-327146c4fdbd` ("falha do php exposta esta semana explicada para uma criança de 5 anos") e a auditoria de confiabilidade de 23/10/2026 identificaram que determinados comportamentos tolerados pelas specs anteriores (como aceitar eixos reprovados como `concluido` na redação, aceitar notas subjetivas na auditoria e misturar raciocínio interno com resposta pública) geravam falsos sucessos.

Este adendo normativo formaliza a evolução dos contratos do sistema sem modificar o texto histórico das specs originais.

---

## 2. Deltas Normativos por Componente

### 2.1. Redação do Dossiê (`endpoint-redacao-do-dossier.md`) — DR-003, DR-011, DR-012
1. **Política de Eixos Reprovados (DR-012):**
   - *Spec original:* Permitia que pontos com status `reprovado` fossem redigidos e entregues com `status: "concluido"`, adicionando ressalvas na seção 3.
   - *Contrato atualizado:* Pesquisas que contiverem qualquer ponto com status `reprovado` após o término de retentativas não podem receber status `"concluido"`. Devem retornar obrigatoriamente `status: "parcial"` (ou `"incompleto"`), destacando claramente a incompletude na entrega.
2. **Validação Estrutural e Truncamento (DR-003):**
   - *Spec original:* Validava apenas se `len(dossier_final) >= 100`.
   - *Contrato atualizado:* O Writer deve validar deterministicamente a presença substantiva das quatro seções em ordem estrita:
     1. `## 1. Sumário Executivo`
     2. `## 2. Desenvolvimento dos Eixos Temáticos`
     3. `## 3. Ressalvas e Limitações Metodológicas`
     4. `## 4. Referências e Fontes Canônicas`
   - Seções ausentes, cercas de código abertas (``` ímpar) ou encerramento com `finish_reason == "length"` impedem conclusão e resultam em `status: "incompleto"`, independentemente de o texto possuir mais de 10.000 caracteres.
3. **Idempotência com Validação de Integridade (DR-003):**
   - Antes de retornar um dossiê em cache no banco de dados, o Writer deve executar a validação estrutural. Se o artefato em cache estiver incompleto ou corrompido, não pode ser devolvido como `concluido`.

### 2.2. Auditoria de Qualidade (`endpoint-auditoria-de-qualidade.md`) — DR-002, DR-010, DR-015
1. **Deliberação Programática via Vetor 12 (DR-002):**
   - *Spec original:* Confiava no campo `status` e na nota percentual subjetiva fornecida pelo LLM.
   - *Contrato atualizado:* A deliberação é estritamente programática no backend, calculada por `sum(1 for c in criterios if c.get("aprovado") is True)`. O LLM deve retornar obrigatoriamente um vetor estruturado de 12 itens com IDs `1..12` e booleanos reais.
2. **Meta 85%+ e Thresholds (DR-002):**
   - *Spec original:* Mencionava corte em 85% de forma genérica.
   - *Contrato atualizado:* Sob a meta 85%+, o default é **11/12 critérios atendidos (91,67%)**. O limiar de 10/12 (83,33%) é rejeitado por padrão na meta 85%+. É oferecido suporte a limiar explícito configurável `criterios_minimos: int = 11` (aceitando 10 ou 11). É expressamente proibido arredondar 83,33% para 85%.
3. **Falha Fechada por Ausência de Vetor:**
   - Vetores corrompidos, com cardinalidade diferente de 12, com IDs repetidos ou booleanos em texto (`"sim"`) reprovam deterministicamente com pontuação 0.0.

### 2.3. Busca com Personas e Agregação (`endpoint-busca-com-personas.md`) — DR-001, DR-004, DR-007, DR-008
1. **Segregação Estrita de Canais (DR-001):**
   - Eliminação completa de fallbacks do tipo `content or reasoning_content`. Se `content` for nulo, a ausência de resposta final é respeitada e o raciocínio interno nunca é promovido para análise pública.
2. **Proveniência de Leitura (DR-008):**
   - Apenas páginas lidas integralmente (`reader_full`) ou via cache válido (`cache`) incrementam `total_urls_lidas`.
   - Resultados de SERP que retornarem apenas resumo/descrição são classificados como `snippet_only` e NÃO contam como páginas lidas.
3. **Verdade de Estados (DR-004):**
   - Um ponto só é `coletado` se todas as 4 personas obtiverem evidências. Se 3 de 4 personas falharem, o status do ponto é `parcial`.
   - O status da pesquisa reflete a realidade agregada dos pontos (`coletado`, `parcial`, `falha`), eliminando valores fixos hardcoded.
4. **Isolamento de Segurança (Prompt Injection Defense):**
   - Todo conteúdo externo raspado da web deve ser encapsulado em tags passivas `<untrusted_evidence source="..." type="...">` para impedir que instruções de páginas sobreponham as diretrizes do sistema.

### 2.4. Planejamento Investigativo (`endpoint-plano-de-investigacao.md`) — DR-006
1. **Resiliência e Contrato de Tipo:**
   - Validação prévia de que a resposta do LLM é um dicionário JSON antes de acessar `.get("pontos")`. Respostas em array ou null geram erro semântico de contrato (`ValueError`), prevenindo `AttributeError` e persistência inválida.
2. **Pistas vs. Fatos:**
   - Metadados SERP são delimitados em tags passivas e tratados formalmente como hipóteses/pistas exploratórias, nunca fatos provados.
