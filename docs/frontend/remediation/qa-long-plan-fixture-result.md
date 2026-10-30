# Relatório de Implementação da Fixture de Plano Longo para QA

## 1. Escopo e Fronteiras de Propriedade

- **Papel:** Hermes QA Infrastructure Worker (`ag/gemini-3.8-flash-high`, reasoning high via 9router).
- **Escopo restrito desta tarefa:**
  1. `docs/frontend/remediation/fixtures/long-plan-public.json` (Novo): Extração pública e sanitizada do plano estruturado de 2 eixos a partir da captura de navegador real.
  2. `docs/frontend/remediation/serve_acceptance_app.py` (Aprimorado): Suporte ao opt-in do tema marcador `"Energia solar: plano extenso para verificação visual"`, exigência estrita de contagem 2 (com rejeição HTTP 400 para contagens incorretas) e novos testes no `--self-check`.
  3. `docs/frontend/remediation/long-plan-fixture-contract.md` (Novo): Contrato de integração para uso do frontend worker em cenários Gherkin/Cucumber.
  4. `docs/frontend/remediation/qa-long-plan-fixture-result.md` (Este documento).

**Preservação estrita:** Nenhum arquivo em `frontend/**`, `app/**`, `tests/mocks/**`, `scripts/**`, `.env` ou histórico git foi modificado. Nenhuma rota da aplicação foi criada ou substituída. Nenhum serviço externo foi reiniciado.

---

## 2. Contexto do Defeito e Solução

Durante testes com navegador real na aplicação integrada, a formulação de um plano real com 2 pontos extensos revelou um defeito visual e de usabilidade:
- Ambos os pontos ficavam abertos simultaneamente;
- O Ponto 1 continha 6 subperguntas e o Ponto 2 continha 7 subperguntas, além de hipóteses e critérios extensos;
- O botão "Iniciar pesquisa" ficava deslocado para fora da visão imediata, tornando a progressão do fluxo confusa para o usuário.

As fixtures determinísticas curtas anteriores ("IA na Educação") não possuíam volume textual suficiente para detectar esse problema de layout. A solução implementada provê uma fixture determinística com **o volume textual e a estrutura exatos da resposta real capturada**, atuando exclusivamente na camada de transporte do modelo simulado.

---

## 3. Dados Extraídos e Proveniência

- **Arquivo de Fixture:** `docs/frontend/remediation/fixtures/long-plan-public.json`
- **Origem dos Dados:** Linha 1 de `docs/frontend/remediation/evidence/live-payloads.jsonl` (chamada `/api/v1/plan` com código HTTP 201).
- **Hash SHA-256 da Resposta Original Bruta:**
  ```text
  a6585a72d75d89495bfae81e29b8bbe798313d8325825d38bdb979a2f64e706a
  ```
- **Sanitização de Privacidade:**
  - Preservados apenas os campos públicos do plano (`pedido_original`, `pedido_normalizado`, `publico`, `formato_entrega`, `recorte_temporal`, `pressupostos`, `ambiguidades`, `pergunta_de_esclarecimento`, `eixos`, `pontos`).
  - O campo `pedido_original` foi atualizado para o tema marcador: `"Energia solar: plano extenso para verificação visual"`.
  - O Eixo 1 preserva todas as suas 6 subperguntas, 4 hipóteses, 6 consultas iniciais e 5 fontes primárias.
  - O Eixo 2 preserva todas as suas 7 subperguntas, 4 hipóteses, 9 consultas iniciais e 6 fontes primárias.
  - O volume textual das subperguntas ultrapassa 2.000 caracteres e o das hipóteses ultrapassa 1.400 caracteres.
  - Raciocínios privados (`reasoning`, `reasoning_planejamento`), envelopes e credenciais foram 100% omitidos.

---

## 4. Integração no `AcceptanceMockNetwork`

No arquivo `docs/frontend/remediation/serve_acceptance_app.py`:
1. **Detecção do Tema Marcador:**
   - O método `extract_topic(messages)` inspeciona o prompt do usuário enviado pelo `Planner` (`app/core/planner.py`), localizando a linha `Tema da Investigação: <tema>`.
   - Se o tema for exatamente `"Energia solar: plano extenso para verificação visual"`, ativa-se o fluxo de plano longo.
2. **Exigência Estrita de Contagem (`n_pontos == 2`):**
   - Se o tema marcador for enviado com contagem **2**: retorna a fixture com os 2 eixos longos.
   - Se o tema marcador for enviado com qualquer contagem **diferente de 2** (ex: 1, 3, 5): retorna erro HTTP 400 (`invalid_marker_count`). Não há truncamento silencioso nem fallback enganoso.
3. **Preservação de Outras Rotas e Provedores:**
   - Outros temas continuam usando o gerador parametrizável padrão de 1 a 5 pontos.
   - O ramo do avaliador semântico avalia os 2 eixos normalmente e retorna `aprovado: True`.
   - Os ramos de Searcher, Auditor e Writer permanecem intocados.
   - As 9 rotas nativas de `app.main` permanecem estritamente preservadas antes e depois de envolver a aplicação com o `Recorder`.

---

## 5. Resultados da Autoverificação Offline (`--self-check`)

Comando executado:
```bash
.venv/bin/python docs/frontend/remediation/serve_acceptance_app.py --self-check
```

Saída real de execução:
```text
=== Acceptance QA Infrastructure Self-Check ===
[OK] Real planner prompt count 1: 1 eixos, 1 pontos
[OK] Real planner prompt count 2: 2 eixos, 2 pontos
[OK] Real planner prompt count 3: 3 eixos, 3 pontos
[OK] Real planner prompt count 5: 5 eixos, 5 pontos
[OK] Real planner retry prompt count 3: correctly recognized and returned 3 eixos
[OK] Topic number immunity (3/10/2026 ignored, count=2 respected): 2 eixos
[OK] Unsupported count rejection (7 -> HTTP 400): correctly rejected
[OK] Long plan fixture: 2 axes (subquestions 6/7), realistic volume (2004 subq chars, 1437 hyp chars)
[OK] Long plan Pydantic schema validation: passes validate_and_parse_plan
[OK] Long plan semantic evaluator: aprovado=True, 1 complement pair preserved
[OK] Long plan wrong count rejection: counts 1, 3, 5 explicitly rejected with HTTP 400
[OK] Semantic evaluator preserved for N=1: aprovado=True, sobreposicao_eixos=[]
[OK] Semantic evaluator preserved for N=3: aprovado=True, pairs=3
[OK] Searcher persona branch preserved: returns action JSON
[OK] Writer dossier branch preserved: returns markdown dossier
[OK] Pydantic validate_and_parse_plan passes for counts 1, 2, 3, 5
[OK] Route preservation: 9 routes identical before and after wrapping
[OK] Recorder privacy sanitization: all private envelopes and keys recursively omitted
=== All self-check assertions passed successfully! ===
```
Código de saída: `0`.

---

## 6. Prova de Integração de Ponta a Ponta com Sessão Real

Executado teste com a aplicação FastAPI real (`app.main`), banco SQLite temporário isolado e autenticação por cookie de sessão de navegador (`dr_local_session` HttpOnly SameSite=Strict):

1. `GET /app/session` -> Status 200, cookie de sessão emitido, autenticação local confirmada.
2. `POST /api/v1/plan` com tema `"Energia solar: plano extenso para verificação visual"` e `n_pontos: 2` (com cookie de sessão e header `Origin` local):
   - Status retornado: **201 Created**.
   - Pontos retornados: **2 pontos**.
   - Ponto 1: **6 subperguntas**.
   - Ponto 2: **7 subperguntas**.
   - Persistência em banco e validação de schema Pydantic executadas com sucesso pelo código de produção.

---

## 7. Limitações e Fronteiras

1. **Simulação Determinística vs. Pesquisa Real:** Esta fixture destina-se a testes de regressão de interface, responsividade e layout (Cucumber / Playwright). Ela não substitui uma pesquisa real de ponta a ponta. Na execução ao vivo anterior, a etapa de busca (`/api/v1/search`) sofreu timeout no provedor externo e está sob correção pelo worker de backend.
2. **Contagem Rígida da Fixture Marcadora:** O tema marcador suporta estritamente 2 pontos. Pedidos com contagem divergente são rejeitados com HTTP 400 para evitar que testes de interface utilizem acidentalmente dados incompatíveis com o cenário.
3. **Escopo de Operação:** Nenhuma automação de navegador (Cucumber) e nenhum reinício de serviços foi executado nesta tarefa. O reinício do servidor de aceitação para testes integrados deve ser conduzido pelo orquestrador após a conclusão das tarefas dos workers.
