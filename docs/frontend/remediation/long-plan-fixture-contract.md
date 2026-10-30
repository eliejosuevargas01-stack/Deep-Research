# Contrato da Fixture de Plano Longo para Regressão Visual

## 1. Objetivo e Motivação

Durante a execução com navegador real no ambiente de aceitação, foi gerado um plano investigativo real com 2 pontos extensos, revelando um defeito de usabilidade na interface:
- Ambos os pontos ficavam abertos simultaneamente por padrão;
- O Ponto 1 continha 6 subperguntas e o Ponto 2 continha 7 subperguntas, com hipóteses, fontes primárias e critérios de conclusão extensos;
- O botão "Iniciar pesquisa" ficava inacessível ou difícil de localizar devido ao deslocamento do layout.

As fixtures curtas anteriores (baseadas em "IA na Educação") tinham textos breves e ocultavam esse problema de volumetria. Esta fixture introduz dados determinísticos com **volume idêntico ao da resposta real capturada**, simulados exclusivamente no nível de transporte do provedor LLM externo (`AcceptanceMockNetwork`), sem qualquer alteração na aplicação FastAPI, no esquema de dados, na autenticação ou nas rotas.

---

## 2. Contrato de Disparo (Trigger)

Para ativar determininisticamente o plano longo na infraestrutura de testes de aceitação (`localhost:8011`):

1. **Tema da Pesquisa (exato):**
   ```text
   Energia solar: plano extenso para verificação visual
   ```
2. **Quantidade de Pontos:**
   - Deve ser configurada explicitamente como **2 pontos** (`n_pontos: 2`) no painel expansível `+` do compositor.
3. **Comportamento da Fixture:**
   - Se o tema for exatamente `"Energia solar: plano extenso para verificação visual"` e a contagem for **2**:
     - O simulador `AcceptanceMockNetwork` responde com os 2 eixos investigativos completos extraídos de `docs/frontend/remediation/fixtures/long-plan-public.json`.
     - O Eixo 1 possui exatamente **6 subperguntas** detalhadas.
     - O Eixo 2 possui exatamente **7 subperguntas** detalhadas.
     - O volume total de texto ultrapassa 2.000 caracteres de subperguntas e 1.400 caracteres de hipóteses.
     - O campo `pedido_original` é atualizado para o tema do gatilho.
   - Se o tema do gatilho for enviado com contagem **diferente de 2** (ex: 1, 3, 5):
     - A fixture retorna erro explícito HTTP 400 (`invalid_marker_count`). Não ocorre truncamento silencioso nem fallback para a fixture curta.
   - Qualquer outro tema (ex: "IA na Educação"):
     - Continua utilizando a geração padrão parametrizável de 1 a 5 pontos da fixture.

---

## 3. Proveniência e Dados Públicos

- **Arquivo de Dados:** `docs/frontend/remediation/fixtures/long-plan-public.json`
- **Origem dos Dados:** Extraído da resposta real `/api/v1/plan` com código HTTP 201 registrada em `docs/frontend/remediation/evidence/live-payloads.jsonl`.
- **Hash SHA-256 da Resposta Bruta Original:** `a6585a72d75d89495bfae81e29b8bbe798313d8325825d38bdb979a2f64e706a`
- **Sanitização:**
  - Apenas campos públicos (`pedido_original`, `pedido_normalizado`, `publico`, `formato_entrega`, `recorte_temporal`, `pressupostos`, `ambiguidades`, `eixos`, `pontos`) foram preservados.
  - Nenhum raciocínio privado (`reasoning`, `reasoning_planejamento`), envelopes de modelo, chaves de API ou dados de sessão constam na fixture.

---

## 4. Fronteiras de Propriedade e Execução

1. **Simulação Estrita no Provedor Externo:**
   - Apenas o transporte HTTP simulado para `https://api.openai.com/v1/chat/completions` é interceptado por `AcceptanceMockNetwork`.
   - O `Planner` real (`app/core/planner.py`), o validador Pydantic (`app/core/plan_validator.py`), o repositório de banco de dados (`app/db/research_repository.py`), a sessão de navegador SameSite=Strict e os endpoints FastAPI `/api/v1/plan` e `/app/session` executam seu código real completo sem mocks internos ou overrides de dependência (`dependency_overrides = 0`).
   - O avaliador semântico de eixos avalia os 2 eixos longos normalmente e aprova o plano com 1 par complementar.
2. **Natureza da Prova:**
   - Esta fixture é uma **regressão determinística** para teste visual e acessibilidade da interface (Gherkin/Cucumber, expansão/recolhimento de eixos, visibilidade do botão Iniciar).
   - **Não reivindica conclusão da pesquisa real:** O passo de busca real na execução prévia expirou por timeout nos provedores externos e está sendo corrigido pelo worker de backend.
3. **Uso no Frontend Worker:**
   - O frontend worker pode usar este tema em seus cenários Cucumber e testes manuais:
     ```gherkin
     Dado que o usuário insere o tema "Energia solar: plano extenso para verificação visual"
     E seleciona "2" pontos nas opções avançadas
     Quando clica em "Planejar pesquisa"
     Então o plano estruturado deve ser exibido com 2 pontos investigativos extensos
     E o botão "Iniciar pesquisa" deve permanecer claramente visível e acessível
     ```
