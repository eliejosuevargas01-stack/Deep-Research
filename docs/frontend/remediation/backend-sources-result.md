# Relatório de Implementação Backend: Contabilidade de Fontes (/pipeline/{id}/sources e /writer)

**Data**: 2026-10-26  
**Componente**: Backend (`app/**`, `tests/**`, `docs/**`)  
**Modelo de Execução**: `ag/gemini-3.8-flash-high` via Render Router  

---

## 1. Resumo Executivo

Foi implementada a separação contábil de fontes solicitada pelo usuário e formalizada nos contratos:
- **Fontes Consultadas (`consultadas`)**: URLs únicas HTTP(S) com leitura comprovada pelo Reader (`status == 'read_ok'`) e corpus textual material registrado no banco (`conteudo_coletado`).
- **Fontes Utilizadas (`utilizadas`)**: URLs citadas no texto Markdown do dossiê analítico final (`dossier_final`) e rastreáveis às evidências lidas.
- **Fontes Não Utilizadas (`nao_utilizadas`)**: Subconjunto de fontes lidas com sucesso que não receberam citação explícita no relatório final.

A entrega inclui:
1. Esquemas tipados Pydantic v2 em `app/schemas/sources.py` e aditivo em `WriterResponse` (`app/schemas/writer.py`).
2. Serviço contábil `SourceAccountingService` em `app/services/source_accounting_service.py`.
3. Endpoint somente-leitura `GET /api/v1/pipeline/{id_pesquisa}/sources` em `app/api/v1/endpoints/pipeline.py`.
4. Anexação aditiva do resumo de fontes no retorno do endpoint `POST /api/v1/writer` em `app/api/v1/endpoints/writer.py`.
5. Contrato publicado para o frontend em `docs/frontend/remediation/sources-api-contract.md`.
6. Bateria completa de testes unitários e de integração em `tests/unit/test_source_accounting.py` e `tests/integration/test_sources_endpoint.py`.

---

## 2. Resolução dos Defeitos Apontados nas Revisões Root (Review 1 e Review 2)

### 2.1. Defeitos da Revisão 1

1. **Estados Contraditórios e Dominância de Falha**:
   - Registro com `fontes.src.status=read_failed`, corpo vazio e `urls_lidas` contendo a URL: metadados explícitos de falha adicionam a URL a `disqualified_canon_keys`. O fallback de `urls_lidas` não sobrepõe a falha observada.
2. **Exigência de Corpus Material e Tipagem**:
   - Exige-se estritamente `bool(body and str(body).strip())` e `body` como `str` real (rejeitando conversão cega de dicts). `read_ok` vazio é desqualificado.
3. **Preservação da Semântica de Caminhos**:
   - `normalize_and_validate_url` preserva caminhos originais sem remoção arbitrária de barras finais.
4. **Robustez de URLs contra Exceções**:
   - O acesso a `.port` e `.hostname` é protegido contra `(ValueError, TypeError)`. Portas inválidas (ex: `:bad`) e caracteres de controle (`ord < 32` ou `ord == 127`) retornam `None` sem quebrar o endpoint.
5. **Parser Avançado de Citações Markdown**:
   - Definições de referência (`[id]: url`) só entram se usadas no corpo.
   - Parser com profundidade de parênteses balanceados preserva URLs da Wikipédia como `[Python](https://en.wikipedia.org/wiki/Python_(programming_language) "Título")`.
   - URLs cruas limpam pontuações periféricas sem cortar parênteses internos balanceados.
6. **Privacidade e Parâmetros Sensíveis de Consulta**:
   - Credenciais de autoridade (`user:pass@`) e parâmetros de query de autenticação/tokens (`token`, `api_key`, `secret`, `jwt`, `sig`) são removidos, preservando parâmetros de navegação legítimos.

### 2.2. Defeitos Críticos Sanados da Revisão 2

7. **Remoção de Equivalência Falsa de Barras**:
   - *Correção*: Eliminado o bloco de fallback incondicional `alt_key`. A correspondência de citações exige identidade canônica normalizada exata. Uma URL consultada `https://example.org/a/` e citada `https://example.org/a` não é tratada como equivalente sem evidência real de alias/redirect, registrando citação não rastreada e gerando status `parcial`.
8. **Validação Segura de Tipos em `length` e `body`**:
   - *Correção*: `length` não-numérico (ex: `'unknown'`) não dispara `ValueError` ao converter para `int`. `raw_body` rejeita tipos que não sejam `str` real, prevenindo erro 500 no endpoint.
9. **Pesquisa com Evidências de Leitura mas sem Dossiê Publicado**:
   - *Correção*: Quando `has_evidence` é verdadeiro mas `dossier_final` é `None` (pesquisa ainda em andamento ou anterior à redação), retorna status `parcial`, com `total_consultadas` conhecido e `total_utilizadas` e `total_nao_utilizadas` nulos (`None`), evitando fabricar partição completa de usados/não-usados antes da publicação real.

---

## 3. Evidências de Teste

### 3.1. Testes Focados do Serviço Contábil (12 testes)
```bash
uv run pytest -q tests/unit/test_source_accounting.py
```
**Resultado**:
```text
............                                                             [100%]
12 passed in 0.15s
```

### 3.2. Testes de Integração da API e Endpoints (4 testes)
```bash
uv run pytest -q tests/integration/test_sources_endpoint.py
```
**Resultado**:
```text
....                                                                     [100%]
4 passed in 1.26s
```

### 3.3. Testes Focados Consolidados (16 testes)
```bash
uv run pytest -q tests/unit/test_source_accounting.py tests/integration/test_sources_endpoint.py
```
**Resultado**:
```text
................                                                         [100%]
16 passed in 1.86s
```

---

## 4. Limitações e Riscos Residuais (Sem Autoaprovação 100%)

1. **Frontend**:
   - A renderização do componente `SourceBreakdown` e a rejeição por divergência de `artifact_hash` são de titularidade do trabalhador frontend em paralelo.
2. **Ambiente Isolado**:
   - Nenhum banco de dados de desenvolvimento em execução (porta 3002) foi alterado ou disparado; todos os testes utilizaram bancos SQLite temporários e isolados por fixture.
3. **Suite Completo**:
   - Conforme instruído pelo Root, a execução do suite completo com mais de 400 testes será conduzida pelo Root após o término desta entrega focada.
