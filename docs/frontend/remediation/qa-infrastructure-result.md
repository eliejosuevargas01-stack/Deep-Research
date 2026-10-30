# Relatório de Infraestrutura de QA e Aceitação

## 1. Identificação da Tarefa e Correção Direcionada

- **Papel:** Hermes QA Infrastructure Worker (`ag/gemini-3.8-flash-high`, reasoning high).
- **Escopo restrito:** Criação e correção da infraestrutura de aceitação determinística e gravação transparente de payloads (`docs/frontend/remediation/serve_acceptance_app.py` e `docs/frontend/remediation/qa-infrastructure-result.md`).
- **Diretriz de Revisão (`qa-infra-review-notes.md`):**
  - Removido o fallback sintético que montava rotas `/` e `/assets` em `build_acceptance_app`.
  - A aplicação real `app.main` é servida exclusivamente pelas suas próprias rotas nativas (em especial a rota SPA catch-all `/{full_path:path}` e a rota de sessão `/app/session`).
  - O harness não adiciona, substitui nem emula qualquer rota, handler ou dependência de autenticação.
  - Caso rotas de SPA ou sessão estivessem ausentes em `app.main`, `build_acceptance_app` lança imediatamente um `RuntimeError` explícito para que a integração real seja feita pelo backend worker.
  - O código do fixture server foi simplificado, eliminando duplicações estáticas de dicionários de eixos através de recuperação dinâmica a partir do `MockNetwork` original.

Nenhum arquivo em `app/**`, `frontend/**`, `tests/mocks/**`, `scripts/**` ou `.env` foi alterado, respeitando integralmente as fronteiras de propriedade dos workers de backend e frontend.

---

## 2. Resultados da Autoverificação Offline (`--self-check`)

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

A auto-verificação testa:
1. Prompts literais reais emitidos por `app/core/planner.py` para contagens 1, 2, 3 e 5.
2. Prompt real de retry (`Gere novamente o objeto JSON completo com exatamente {count} eixos.`).
3. Imunidade a números que pertençam ao tema formulado pelo usuário (ex: "Os 3 Grandes Pilares e 10 Leis da Automação em 2026").
4. Rejeição explícita com HTTP 400 (`unsupported_fixture_count`) para contagens fora do intervalo 1..5.
5. Preservação do avaliador semântico para N=1 (retornando lista vazia) e N=3 (retornando 3 pares de eixos).
6. Preservação das personas do searcher e do redator final.
7. Validação estrita do schema Pydantic via `app.core.plan_validator.validate_and_parse_plan`.
8. Verificação de inalterabilidade de rotas: as 9 rotas originais de `app.main` permanecem exatamente idênticas antes e depois de envolver a aplicação com o `Recorder`.
9. Sanitização profunda de dados sensíveis e envoltórios no gravador transparente.

---

## 3. Arquitetura do Simulador de Provedores (`AcceptanceMockNetwork`)

- **Classe:** `AcceptanceMockNetwork(tests.mocks.http_mock.MockNetwork)`
- **Patch de Transporte:** Aplicado via `patch_mock_transport()` em `tests.mocks.http_mock` antes da importação de `app.main`, garantindo que todas as chamadas internas de `_get_transport()` recebam a instância aprimorada durante `PYTEST_CURRENT_TEST`.
- **Inspeção de Diretrizes do Planner:** Expressões regulares inspecionam apenas as frases estruturadas de diretriz emitidas por `app/core/planner.py`:
  - `decomponha a investigação em exatamente (\d+) eixos`
  - `formule o plano investigativo estruturado em json com exatamente (\d+) eixos`
  - `gere novamente o objeto json ... com exatamente (\d+) eixos`
  - `lista com exatamente (\d+) objetos`
- **Faixa de Suporte e Rejeição Honesta:** Suporta deterministicamente de 1 a 5 pontos. Pedidos fora dessa faixa retornam HTTP 400 imediato em vez de gerar dados corrompidos ou respostas parciais.
- **Ramos Preservados Intocados:**
  - Avaliador semântico de sobreposição de eixos (`avaliador_semantico`, `sobreposição de eixos`).
  - Searcher / personas investigativas (`protocolo de ações em json`, `historiador`, `visionario`, `cetico`, `futurista`).
  - Auditor de redação e auditor factual de 12 perguntas (`auditor_redacao`, `auditor`).
  - Redator final do dossiê (`redator final`, `dossiê analítico final`).
  - Consultas Jina SERP (`s.jina.ai`) e Jina Reader (`r.jina.ai`).
  - Despacho de Webhooks (`callback_webhook_url`).

---

## 4. Servidor de Aceitação Integrado (`localhost:8011`)

- **Comando de inicialização:**
  ```bash
  .venv/bin/python docs/frontend/remediation/serve_acceptance_app.py --port 8011
  ```
- **Comando de parada:** Envio de sinal `SIGINT` (Ctrl+C) ou `SIGTERM`.
- **Rotas Reais Servidas:**
  A aplicação é executada com suas 9 rotas nativas:
  - `GET /health` (status 200)
  - `GET /app/session` (emissão/renovação de cookie de sessão local SameSite=Strict HttpOnly)
  - `GET /{full_path:path}` (rota catch-all SPA nativa servindo `frontend/dist/index.html`)
  - `GET /assets/{file_path:path}` (serviço de assets estáticos compilados com 404 estrito)
  - Rotas de API `/api/v1/*`, documentação `/docs` e `/openapi.json`
- **Ausência de Rotas Sintéticas:** O harness valida que não existem rotas artificiais (`synthetic_routes_added: false`) e que `app.dependency_overrides` tem tamanho zero.
- **Ciclo de vida do banco SQLite isolado:**
  - Criado sob diretório temporário gerenciado (`tempfile.TemporaryDirectory(prefix="deep-research-acceptance-")`).
  - Caminho: `{temp_dir}/acceptance.db`.
  - Destruído e limpo automaticamente no bloco `finally` ao término do processo.
- **Credenciais de Fixture Públicas:**
  - `CREDENTIALS_MASTER_KEY`: Chave Fernet gerada dinamicamente por inicialização.
  - `API_SECRET_KEY`: `fixture-acceptance-secret-key-public` (pública, não é credencial de produção).
  - `OPENAI_API_KEY`: `fixture-openai-key-simulated`
  - `JINA_API_KEY`: `fixture-jina-key-simulated`
  - `WEBHOOK_HMAC_SECRET`: `fixture-webhook-secret-simulated`
  - `PYTEST_CURRENT_TEST`: `tests/integration/acceptance_test_harness (call)`

---

## 5. Gravação Transparente de Payloads (`Recorder`)

- **Modo do Gravador:** `provider_mode = "deterministic_external_provider_fixtures"`
- **Destino da Evidência:** `docs/frontend/remediation/evidence/fixture-payloads.jsonl`
- **Sanitização de Privacidade:**
  - Nenhum header HTTP ou cookie é registrado.
  - Segredos e chaves de fixture adicionados a `SENSITIVE_VALUES` são mascarados recursivamente como `[REDACTED]`.
  - Campos sensíveis internos (`reasoning`, `reasoning_planejamento`, `envelopes`, chaves com sufixos/prefixos `_envelope`, `_reasoning`, `_prompt`, `master_key`, `secret`, `credential`) são omitidos recursivamente como `[OMITTED]`.
  - Nenhuma mutação de request ou response é realizada pelo gravador.

---

## 6. Prova de Runtime (`fixture-runtime-proof.json`)

Arquivo gerado em `docs/frontend/remediation/evidence/fixture-runtime-proof.json` durante teste de inicialização real:
- **Porta:** 8011
- **Rotas:** 9 rotas nativas de `app.main` registradas
- **SHA-256 `app/main.py`:** `caf4404d3b2594dd917e843c10d65799892b541cfc44e67083e1dbd19a6f2514`
- **SHA-256 `frontend/dist/index.html`:** `cf6aa643d78f6e3ef536df3e588dec65daba05d472cdf73735d1510d6ea17779`
- **Overrides de Dependência:** 0
- **Rotas Sintéticas Adicionadas:** `false`

---

## 7. Limitações e Fronteiras

1. **Simulação vs. Execução Real:** Este ambiente de aceitação utiliza transporte determinístico simulado (`AcceptanceMockNetwork`). Ele é projetado para testes de integração reproduzíveis e verificação da interface do usuário. Não substitui a execução com modelos reais, a qual é conduzida separadamente via `capture_app.py` com credenciais válidas e provedores configurados.
2. **Faixa da Fixture:** A fixture determinística suporta contagens de 1 a 5 pontos. Para pesquisas com mais de 5 pontos, deve ser utilizada a execução com modelos reais.
3. **Escopo Operacional:** Nenhuma automação de navegador (Playwright/Cucumber) nem reinício de serviços externos foi executado nesta etapa, respeitando estritamente o protocolo pré-auditoria.

---

## 8. Próximas Ações de Orquestração

1. Conclusão dos ajustes do worker de backend e do worker de frontend.
2. Execução da auditoria independente dos 9 requisitos e gates de qualidade.
3. Execução da suíte Cucumber visual e testes de contrato e integração na aplicação integrada.
