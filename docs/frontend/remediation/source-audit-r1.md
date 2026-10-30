# Auditoria Independente de Qualidade: Funcionalidade S01 (Separação Contábil de Fontes)

- **Data da Auditoria:** 2026-10-26T23:35:00-03:00
- **Auditor:** Hermes Quality Auditor (Perfil: `critique-native`)
- **Modelo:** `ag/gemini-3.8-flash-high` via `custom` (provider9router, reasoning high)
- **Escopo:** Funcionalidade S01 (Separação Contábil de Fontes: consultadas, utilizadas, não utilizadas). Módulos PlanView e Settings expressamente excluídos deste parecer.
- **Veredito:** `approve_for_visual_validation`

---

## 1. Hashes Criptográficos dos Arquivos Auditados (SHA-256)

| Arquivo | SHA-256 |
|---|---|
| `app/services/source_accounting_service.py` | `2f2452045a2436fb0ac939867b793ac1118eb1c15c780422e3a0cbb5d6dea323` |
| `app/schemas/sources.py` | `ad8a061ac8d511958bf27a9e5c5b9409fffcfef575b790f4edcb3634fdeed0b9` |
| `app/schemas/writer.py` | `7b0f771ab8d5c981de1a8a52ddf5030b588fd380b7bd6186ce62803f45dce1d0` |
| `app/api/v1/endpoints/pipeline.py` | `289e77afd21ce1477ab6a6043d7dcf94a409a597e4205bad68402fb03bd2b423` |
| `app/api/v1/endpoints/writer.py` | `f365172472895855c3ba8017afa854d24b923b26a49788f37673e9eccf35aba2` |
| `frontend/src/components/ReportView.tsx` | `77fb85d71468d208988dae66ce6817331469c2f0efd9d2cb8b8d93479a2a9681` |
| `frontend/src/components/SourceBreakdown.tsx` | `1a07de8bdb836f0ae94f9fc3a8feb92c75b985756a097e18917e2a1fc54895ed` |
| `frontend/src/components/SourceBreakdown.css` | `48a928380eed00f1246afd87dc25dad968fe7847c5454683ad93304dde65fde8` |
| `frontend/src/types/api.ts` | `cf555a8fbecc904da53f0d6b284aea230334bf65c2287d502bffe0393792f653` |
| `frontend/src/services/api.ts` | `4c50d977652fb19f0552b3035350759e2aae1102e2670c7851b679a699906b20` |
| `frontend/src/services/history.ts` | `a9dd3f3a01a0d531f631e2582885cc913c83061e4f3f5d702ce169f5a5dc6235` |
| `tests/unit/test_source_accounting.py` | `270920e3964bc6b59619a54d4a57925fcfedaf915e59c2d19a9299878d83bc97` |
| `tests/integration/test_sources_endpoint.py` | `194526a35d4846d410498af9f771b10401068db5a188568639b624f3e1f3c99d` |
| `frontend/src/tests/sources-accounting.test.ts` | `718c7cbb278812bb4e1313bc7aeec88b0228e18521fa9a7fda50db6371e3752c` |
| `frontend/features/05_sources_accounting.feature` | `ddb10545b72a81aa1cbb358e6eeb814e7b1f93c6b93121eafcc11694dd8b507c` |
| `frontend/features/step_definitions/steps.ts` | `2fa4addffc5d20ab95be8a3cfab85a9efb08390487d24fc8259df14083f6a74d` |

---

## 2. Proveniência e Evidências de Testes Verificados

1. **Linha de Base Backend Completa:**
   - Evidência prévia arquivada: `docs/frontend/remediation/evidence/backend-sources-root-verified.{json,txt}`.
   - 422 testes aprovados, 8 warnings em 64.72s (SHA256 log: `d8c488952eebae101864dcc66a3c7db7525a6b0602544ca671bbfbed4948221e`).

2. **Testes Focados do Serviço e Endpoint de Fontes:**
   - Comando executado: `.venv/bin/pytest tests/unit/test_source_accounting.py tests/integration/test_sources_endpoint.py`.
   - Resultado: **16 testes aprovados** em 1.60s (0 falhas).
   - Cobertura verificada:
     - Normalização e segurança de URL (rejeição de userinfo, portas padrão, portas inválidas, query params sensíveis como token/key preservando parâmetros legítimos).
     - Parser AST Markdown (parênteses Wikipédia balanceados, títulos de links, autolinks, referências bibliográficas usadas vs ignoradas quando não citadas).
     - Exclusão estrita de snippets, buscas preliminares e falhas de leitura (`status != "read_ok"` ou corpo vazio).
     - Exigência de corpus material comprovado.
     - Partição estrita e tratamento de relatórios legados e incompletos (sem falsos zeros).
     - Hidratação somente-leitura de relatório legado sem mutações ou chamadas de LLM.
     - Inclusão aditiva de `fontes` em `POST /api/v1/writer` tanto para execuções novas quanto respostas do cache.

3. **Testes Focados Frontend de Produção:**
   - Comando executado: `npx tsx src/tests/sources-accounting.test.ts` (no diretório `frontend`).
   - Resultado: **12 testes aprovados** com sucesso (0 falhas).
   - Cobertura verificada:
     - Extração AST Markdown via `unified`/`remark-gfm` sem falsos positivos em blocos de código ou código inline.
     - Cálculo de digest SHA-256 do artefato publicado em conformidade com Web Crypto e Node Crypto.
     - Estados de `SourceBreakdown`: carregamento sem falso rótulo de legado; estado completo com 3 contadores agrupados; estado legado sem zeros fabricados; estado de divergência (mismatch) com supressão de fontes alheias; estado de erro de rede com botão de retry exclusivo de fontes.
     - Integração em `ReportView` com preservação byte-a-byte do texto Markdown original, cópia para clipboard e download de arquivo.
     - Sanitização de histórico (`historyService`): expurgo de credenciais e parâmetros de segredo em queries; rejeição de tipos inválidos; retenção exclusiva de HTTP(S) públicos.
     - Validação de chamada de rede em `api.getSources` com `AbortSignal`.
     - Derivação síncrona sem vazamento de estado defasado ao alterar texto com mesmo ID.

4. **Verificação HTTP ao Vivo (Serviço Local 127.0.0.1:3002):**
   - Probe executado com CookieJar próprio isolado:
     - `GET /app/session` -> `200 OK`
     - `GET /api/v1/pipeline/dee9fa33-1205-4323-8715-ab388deb8747/sources` -> `200 OK`
     - Contagens verificadas: `total_consultadas = 11`, `total_utilizadas = 9`, `total_nao_utilizadas = 2` (status: `completo`).
     - Hash do artefato: `7dbf09a2686541721efeacd64533a0716fefc85e2de46da833fb81355dc893eb` (coincidência exata com o relatório publicado).
     - `generation_attempts` mantido inalterado em 24 tentativas (zero novas chamadas de modelos LLM ou pesquisas na web).
     - `GET /api/v1/pipeline/inexistente-id-404/sources` -> `404 NOT FOUND`.

5. **Rastreabilidade Gherkin 05:**
   - Arquivo `frontend/features/05_sources_accounting.feature` define 4 cenários de aceitação.
   - Step definitions implementadas em `frontend/features/step_definitions/steps.ts` (linhas 1225-1418).

---

## 3. Avaliação Semântica e Conformidade de Contrato

- **Fontes Consultadas (`consultadas`):**
  Definidas estritamente como URLs HTTP(S) únicas lidas com sucesso (`status == "read_ok"`), com corpus textual material comprovado (`length > 0` e texto presente). URLs candidatas da busca não lidas (`snippet_only`), leituras com erro HTTP (4xx/5xx/timeout) e leituras com corpo vazio são formalmente excluídas e marcadas em lista de desqualificação.
- **Fontes Utilizadas (`utilizadas`):**
  Definidas como fontes citadas no texto Markdown publicado (`dossier_final`) e vinculadas às evidências de leitura registradas. Código fonte, blocos de código cercados e definições de links não citadas no corpo são descartados pelo parser AST.
- **Fontes Não Utilizadas (`nao_utilizadas`):**
  Subconjunto de fontes consultadas com sucesso que não receberam citação direta (`consultadas - utilizadas`). Explicadas explicitamente na interface como material contextual e investigativo, e **não** como fontes rejeitadas ou inválidas.
- **Partição e Relatórios Legados:**
  Quando evidências brutas de leitura não estão disponíveis (`status: "indisponivel"`), os contadores desconhecidos retornam `null` no backend e são renderizados como travessão (`—`) no frontend. O sistema nunca inventa o valor `0` para fontes consultadas ou não utilizadas.
- **Endpoint Somente-Leitura (`GET /api/v1/pipeline/{id}/sources`):**
  Protegido pelo mecanismo de autenticação existente. Retorna `HTTP 404` para ID inexistente. Não efetua mutações no banco de dados, nem chamadas a provedores pagos, modelos LLM ou spiders de rede.
- **Proteção e Privacidade:**
  O esquema público projeta exclusivamente `url`, `titulo` e `dominio`. IDs internos (`claim_ids`, `source_ids`, `ponto_id`), trechos brutos de texto, prompts e credenciais em query strings são rigorosamente removidos.
- **Vinculação Estrita de Versão e Integridade:**
  O frontend calcula o SHA-256 local do texto publicado e valida a correspondência exata com o `artifact_hash` fornecido pela API. Se houver divergência (mesmo com o mesmo `id_pesquisa`), exibe banner de aviso e suprime fontes alheias para não induzir o usuário a erro. Mutações pendentes cancelam requisições em trânsito via `AbortSignal`.

---

## 4. Achados da Auditoria (Severidade P0 - P3)

- **Achados P0 (Bloqueantes):** **0**
- **Achados P1 (Graves / Violação de Contrato / WCAG AA):** **0**
- **Achados P2 (Médios / Regressão Funcional):** **0**
- **Achados P3 (Polimento / Craft Floor):** **2**

### Detalhamento dos Achados P3

1. **[P3] FINDING-P3-01: Estilos inline pontuais em subelementos de SourceBreakdown**
   - **Localização:** `frontend/src/components/SourceBreakdown.tsx:88`, `161`, `269`, `293`
   - **Categoria:** Theming / CSS Craft
   - **Descrição:** Presença de estilos inline (`style={{ display: 'flex', gap: '8px' }}`, `style={{ color: 'var(--color-text-muted)' }}`) em elementos internos secundários (badge container e mensagem de URL insegura).
   - **Impacto:** Nenhum impacto funcional, de contraste ou de acessibilidade (todos os elementos passam nos testes).
   - **Recomendação:** Na etapa de polimento visual, migrar esses estilos inline para classes declarativas em `SourceBreakdown.css`.

2. **[P3] FINDING-P3-02: Aviso de depreciação module.register() no runner de testes**
   - **Localização:** `frontend/src/tests/sources-accounting.test.ts:23`
   - **Categoria:** Tooling / Test Infra
   - **Descrição:** Emissão do aviso `[DEP0205] DeprecationWarning: module.register() is deprecated. Use module.registerHooks() instead.` ao executar os testes no Node.js v22+.
   - **Impacto:** Apenas ruído informativo na saída do terminal; os 12 testes executam e passam integralmente.
   - **Recomendação:** Atualizar para `module.registerHooks()` quando a API estiver consolidada nos ambientes de CI.

---

## 5. Escopo e Veredito

- **Escopo do Parecer:** Focado exclusivamente nos componentes e serviços da funcionalidade S01.
- **Veredito:** `approve_for_visual_validation`
- **Justificativa:** A implementação cumpre com rigor todos os requisitos contratuais, semânticos, de segurança, tipagem e resiliência de estado. Não há nenhum defeito P0 ou P1 pendente.

---

## 6. Retestes Obrigatórios e Limites Honestos

1. **Reteste Obrigatório 1:** Captura de screenshot no navegador real e inspeção visual do layout do `SourceBreakdown` integrado ao `ReportView` para validação definitiva dos critérios estéticos do Craft Floor (alinhamento, tipografia e espaçamento real renderizado).
2. **Reteste Obrigatório 2:** Execução da suíte completa de Cucumber ao final do ciclo de remedição, quando o trabalhador responsável por PlanView e Settings finalizar suas alterações.
3. **Limites Honestos:**
   - Esta auditoria é estática, de integração e validação de estado/contrato; não inventa evidências de pixels a partir de arquivos estáticos.
   - Não constitui a auditoria global final do sistema nem autorização final de release da aplicação.
