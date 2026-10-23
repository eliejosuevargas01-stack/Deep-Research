# Interface: POST /api/v1/audit (Auditoria de Qualidade)

> Identificador: `001-pesquisa-profunda-mvp`
> Tipo de Contrato: HTTP REST (Exposto pelo sistema)
> Protocolo: HTTP/1.1 ou HTTP/2 sobre TLS
> Referência SDD: `_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md`

---

## 1. Visão Geral
Endpoint da Etapa 3 do pipeline Deep Research. Resgata o conteúdo coletado de cada ponto na tabela `conteudo_coletado` e submete a materialização textual ao crivo da persona `auditor` através de LLM forte OpenAI-compatible. O modelo avalia cada ponto frente às 12 perguntas de qualidade estabelecidas no PRD, deliberando `aprovado` ou `reprovado` e atualizando os campos `status` e `pontos_fracos` na tabela `pontos`.

---

## 2. Detalhes da Requisição

- **Método HTTP:** `POST`
- **Caminho:** `/api/v1/audit`
- **Cabeçalhos Exigidos:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <API_BEARER_TOKEN>`
- **Timeout:** 180 segundos

### Payload da Requisição (Request Body)
```json
{
  "id_pesquisa": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `id_pesquisa` | String (UUID v4) | Sim | Identificador canônico da pesquisa |

---

## 3. As 12 Perguntas de Qualidade Avaliadas
O modelo de auditoria avalia obrigatoriamente os seguintes critérios para cada ponto:
1. **Clareza Temática:** O conteúdo aborda objetivamente a questão formulada no ponto?
2. **Corroboração Canônica:** Existem fontes primárias verificáveis que sustentam os dados?
3. **Atualidade:** As informações e marcos citados estão temporalmente vigentes?
4. **Ausência de Contradições:** Os dados internos coletados são coerentes entre si?
5. **Embasamento Factual:** Declarações estão ancoradas em evidências empíricas e não opiniões vazias?
6. **Aderência ao Escopo:** O conteúdo se atém ao tema sem desvios laterais?
7. **Profundidade Analítica:** A explicação alcança complexidade suficiente para subsidiar decisão?
8. **Precisão Numérica:** Métricas, estatísticas e datas citadas possuem unidades e contexto?
9. **Neutralidade:** O texto preserva tom analítico objetivo e equilibrado?
10. **Densidade de Evidências:** Há proporção satisfatória entre afirmações e fontes citadas?
11. **Declaração de Incertezas:** Lacunas e divergências na literatura são expressamente apontadas?
12. **Solidez Lógica:** As conclusões decorrem necessariamente dos fatos apresentados?

---

## 4. Respostas da API (Response)

### 4.1 Sucesso: HTTP 200 OK
```json
{
  "id_pesquisa": "550e8400-e29b-41d4-a716-446655440000",
  "total_pontos": 5,
  "aprovados": 4,
  "reprovados": 1,
  "status_geral": "auditado",
  "auditorias": [
    {
      "ponto_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
      "ponto_n": 1,
      "status": "aprovado",
      "pontos_fracos": null,
      "resumo_auditoria": "Ponto com evidências sólidas, citações canônicas de estudos da UNESCO e métricas comprovadas."
    },
    {
      "ponto_id": "c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f",
      "ponto_n": 3,
      "status": "reprovado",
      "pontos_fracos": "Carência de fontes canônicas com dados primários sobre conectividade em áreas rurais; dependência excessiva de postagens de blog secundárias.",
      "resumo_auditoria": "Reprovado no critério 2 (Corroboração Canônica) e critério 10 (Densidade de Evidências)."
    }
  ]
}
```

---

## 5. Códigos de Erro e Tratamento

| Código HTTP | Erro | Causa / Comportamento |
|-------------|------|-----------------------|
| `400 Bad Request` | `SEARCH_NOT_COMPLETED` | Pesquisa não possui coletas concluídas na tabela `conteudo_coletado` |
| `404 Not Found` | `RESEARCH_NOT_FOUND` | Identificador `id_pesquisa` inexistente |
| `500 Internal Server Error` | `AUDITOR_PARSER_ERROR` | Falha na estruturação da resposta do checklist pelo LLM forte |
| `502 Bad Gateway` | `LLM_GATEWAY_ERROR` | Indisponibilidade do provedor OpenAI-compatible após 1+3 retries |
| `504 Gateway Timeout` | `AUDIT_TIMEOUT` | Inferência crítica ultrapassou 180 segundos |

---

## 6. Idempotência e Concorrência
- Execuções subsequentes de auditoria para uma mesma pesquisa atualizam deterministicamente os registros na tabela `pontos`.
- O endpoint bloqueia escritas parciais: todos os pontos do lote devem ser avaliados com sucesso na mesma transação.