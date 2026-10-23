# Interface: Integração Externa Jina (SERP + Scrapper)

> Identificador: `001-pesquisa-profunda-mvp`
> Tipo de Contrato: HTTP REST (Consumido pelo sistema)
> Protocolo: HTTPS
> Referência SDD: `_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais`, `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md`, `_reversa_sdd/sdd/endpoint-busca-com-personas.md`

---

## 1. Visão Geral
O sistema consome os serviços da API Jina em duas etapas distintas com restrições arquiteturais específicas:
1. **Etapa 1 (Plano):** Acesso restrito a metadados da SERP via Jina Search (`https://s.jina.ai/<query>`). É expressamente proibido fazer scraping ou baixar corpos de páginas completas nesta fase.
2. **Etapa 2 (Busca):** Acesso a conteúdo web completo via Jina Reader/Scrapper (`https://r.jina.ai/<url>`), com filtragem prévia de URLs já consultadas por `id_pesquisa` e preservação integral sem truncamento.

---

## 2. Jina SERP (Etapa de Planejamento e Formulação de Queries)

- **Endpoint:** `GET https://s.jina.ai/{query}` (ou `POST https://api.jina.ai/v1/search`)
- **Cabeçalhos Enviados:**
  - `Authorization: Bearer <JINA_API_KEY>`
  - `Accept: application/json`
  - `X-Retain-Images: none`
  - `X-No-Cache: true`
- **Timeout:** 30 segundos (limite operacional máximo de 600s para o ciclo de tentativas)
- **Política de Retentativas:** 1 tentativa inicial + 3 retries com backoff exponencial

### Resposta Esperada (SERP)
```json
{
  "code": 200,
  "data": [
    {
      "title": "A Inteligência Artificial na Educação Básica: Diretrizes da UNESCO",
      "url": "https://unesdoc.unesco.org/ark:/48223/pf0000377897",
      "description": "Relatório analítico sobre integração pedagógica de modelos generativos..."
    },
    {
      "title": "Impactos do Uso de IA em Salas de Aula: Evidências Recentes",
      "url": "https://www.oecd.org/education/ai-in-classrooms.htm",
      "description": "Estudo comparativo da OCDE sobre desempenho acadêmico e equidade digital..."
    }
  ]
}
```

---

## 3. Jina Reader / Scrapper (Etapa de Busca com Personas)

- **Endpoint:** `GET https://r.jina.ai/{target_url}`
- **Cabeçalhos Enviados:**
  - `Authorization: Bearer <JINA_API_KEY>`
  - `Accept: text/markdown`
  - `X-Target-Selector: main, article, #content`
  - `X-Return-Format: markdown`
- **Timeout:** 45 segundos por página
- **Política de Retentativas:** 1 tentativa inicial + 3 retries com backoff exponencial

### Tratamento de Resposta
- O corpo retornado em Markdown é preservado na íntegra sem truncamento sintático na tabela `conteudo_coletado`.
- URLs retornadas que já constam na lista de URLs consultadas para aquele `id_pesquisa` são descartadas antes da invocação do leitor.

---

## 4. Códigos de Erro e Tratamento de Exceções

| Código Jina | Interpretação | Ação do Sistema |
|-------------|---------------|-----------------|
| `429 Too Many Requests` | Excedida cota ou taxa de requisições | Aguarda backoff exponencial jitter (2s, 4s, 8s...) até o limite de 3 retries |
| `500 / 502 / 503` | Falha temporária no cluster Jina | Executa retentativa automática com nova conexão HTTP |
| `404 / 403 / 410` (no Scraper) | Página de destino bloqueada, inexistente ou com paywall estrito | Registra URL como lida, descarta link falhado e orienta o trabalhador a priorizar fontes canônicas alternativas |