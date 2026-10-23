# Interface: POST /api/v1/search (Busca com Personas)

> Identificador: `001-pesquisa-profunda-mvp`
> Tipo de Contrato: HTTP REST (Exposto pelo sistema)
> Protocolo: HTTP/1.1 ou HTTP/2 sobre TLS
> Referência SDD: `_reversa_sdd/sdd/endpoint-busca-com-personas.md`

---

## 1. Visão Geral
Endpoint da Etapa 2 do pipeline Deep Research. Recebe o `id_pesquisa`, recupera os pontos pendentes da base relacional e dispara a coleta paralela utilizando as 4 personas analíticas (`historiador`, `visionario`, `cetico`, `futurista`) acionando LLM leve e raspador Jina (`s.jina.ai`). Aplica desduplicação de URLs por pesquisa e persiste o conteúdo completo sem truncamento na tabela `conteudo_coletado`.

---

## 2. Detalhes da Requisição

- **Método HTTP:** `POST`
- **Caminho:** `/api/v1/search`
- **Cabeçalhos Exigidos:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <API_BEARER_TOKEN>`
- **Timeout:** 300 segundos

### Payload da Requisição (Request Body)
```json
{
  "id_pesquisa": "550e8400-e29b-41d4-a716-446655440000",
  "ponto_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `id_pesquisa` | String (UUID v4) | Sim | Identificador canônico da pesquisa |
| `ponto_id` | String (UUID v4) | Não | Filtro opcional para reprocessamento exclusivo de um ponto específico |

---

## 3. Respostas da API (Response)

### 3.1 Sucesso: HTTP 200 OK
```json
{
  "id_pesquisa": "550e8400-e29b-41d4-a716-446655440000",
  "total_pontos_processados": 5,
  "status_pesquisa": "coletado",
  "resumo_coletas": [
    {
      "ponto_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
      "ponto_n": 1,
      "status": "coletado",
      "total_urls_lidas": 8,
      "total_urls_fonte": 4,
      "tamanho_conteudo_caracteres": 34820
    },
    {
      "ponto_id": "b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e",
      "ponto_n": 2,
      "status": "coletado",
      "total_urls_lidas": 6,
      "total_urls_fonte": 3,
      "tamanho_conteudo_caracteres": 28450
    }
  ]
}
```

---

## 4. Códigos de Erro e Tratamento

| Código HTTP | Erro | Causa / Comportamento |
|-------------|------|-----------------------|
| `400 Bad Request` | `INVALID_PAYLOAD` | Formato do identificador UUID inconsistente |
| `404 Not Found` | `RESEARCH_NOT_FOUND` | Identificador `id_pesquisa` não localizado na base SQLite |
| `404 Not Found` | `NO_PENDING_POINTS` | Pesquisa não possui pontos pendentes para processar |
| `500 Internal Server Error` | `PERSONAS_CONFIG_MISSING` | Configuração das personas ausente no ambiente/banco |
| `502 Bad Gateway` | `SCRAPER_FAILURE` | Provedor Jina indisponível após 1+3 retries |
| `504 Gateway Timeout` | `SEARCH_TIMEOUT` | Processamento concorrente ultrapassou 300 segundos |

---

## 5. Idempotência e Concorrência
- As URLs já lidas para a pesquisa corrente são registradas no banco e cacheadas em memória para descarte automático imediato de novas requisições repetidas ao mesmo endereço.
- Re-execuções da rota processam apenas pontos com status `pendente` ou o `ponto_id` especificado, prevenindo duplicidade de coletas já salvas na tabela `conteudo_coletado`.