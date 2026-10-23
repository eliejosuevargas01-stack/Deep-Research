# Interface: POST /api/v1/writer (Redação do Dossier)

> Identificador: `001-pesquisa-profunda-mvp`
> Tipo de Contrato: HTTP REST (Exposto pelo sistema)
> Protocolo: HTTP/1.1 ou HTTP/2 sobre TLS
> Referência SDD: `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md`

---

## 1. Visão Geral
Endpoint da Etapa 4 (final) do pipeline Deep Research. Consolida os pontos auditados, recupera o conteúdo coletado e as fontes canônicas, acionando a persona `redator final` com LLM forte para redigir o dossiê executivo completo em Markdown. Rejeita pesquisas com qualquer ponto pendente de auditoria (HTTP 400). Persiste o dossiê na tabela `pesquisa` e despacha requisição HTTP POST para o webhook de callback com assinatura HMAC-SHA256 (`X-Signature`).

---

## 2. Detalhes da Requisição

- **Método HTTP:** `POST`
- **Caminho:** `/api/v1/writer`
- **Cabeçalhos Exigidos:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <API_BEARER_TOKEN>`
- **Timeout:** 240 segundos

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

## 3. Estrutura do Dossiê Produzido (Markdown)
O texto sintetizado pelo LLM forte cumpre obrigatoriamente a estrutura:
1. **Sumário Executivo:** Visão geral dos achados, principais conclusões e síntese estratégica.
2. **Desenvolvimento dos Eixos Temáticos:** Seção dedicada para cada ponto de investigação, detalhando evidências, consensos e dados apurados.
3. **Ressalvas e Limitações Metodológicas:** Subseção explicitando os pontos que receberam parecer de reprovação na auditoria com suas fragilidades declaradas (sem ocultação de dados inconclusivos).
4. **Referências e Fontes Canônicas:** Lista exaustiva com 100% dos links e autores canônicos mapeados e utilizados na fundamentação do texto.

---

## 4. Respostas da API (Response)

### 4.1 Sucesso: HTTP 200 OK
```json
{
  "id_pesquisa": "550e8400-e29b-41d4-a716-446655440000",
  "tema": "Impacto da Inteligência Artificial Generativa na Educação Básica",
  "status": "concluido",
  "total_caracteres_dossier": 18450,
  "concluido_em": "2026-10-21T18:40:00Z",
  "webhook_entrega": {
    "url": "https://meu-servico.exemplo.com/webhooks/pesquisa",
    "status": "entregue",
    "http_status_code": 200,
    "tentativas": 1
  },
  "dossier_resumo": "# Dossiê Analítico: Impacto da IA na Educação\n\n## Sumário Executivo\n..."
}
```

---

## 5. Códigos de Erro e Tratamento

| Código HTTP | Erro | Causa / Comportamento |
|-------------|------|-----------------------|
| `400 Bad Request` | `PENDING_AUDIT_POINTS` | Pesquisa contém pontos com status `pendente` ou `em_andamento`; lista de IDs pendentes é retornada no erro |
| `404 Not Found` | `RESEARCH_NOT_FOUND` | Identificador `id_pesquisa` não localizado |
| `500 Internal Server Error` | `WRITER_GENERATION_FAILED` | Falha estrutural no LLM ou formatação do documento |
| `502 Bad Gateway` | `LLM_SERVICE_UNAVAILABLE` | Erro de infraestrutura no provedor LLM forte |
| `504 Gateway Timeout` | `WRITER_TIMEOUT` | Processamento analítico excedeu o limite de 240s |

*Nota de Resiliência:* Caso o despacho para o webhook de callback falhe definitivamente após retentativas, o dossiê é preservado com sucesso no SQLite permanente (`webhook_status = 'falha_definitiva'`), retornando código HTTP 200 com o alerta de falha no objeto `webhook_entrega`.

---

## 6. Idempotência e Concorrência
- A consulta aos pontos pendentes impede execuções parciais.
- Se o dossiê já tiver sido gerado para a pesquisa, o endpoint retorna o documento existente sem reinvocar o modelo gerador, a menos que novo ciclo seja explicitamente autorizado.