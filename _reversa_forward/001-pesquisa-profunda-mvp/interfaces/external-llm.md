# Interface: Integração Externa LLM (OpenAI-Compatible)

> Identificador: `001-pesquisa-profunda-mvp`
> Tipo de Contrato: HTTP REST (Consumido pelo sistema)
> Protocolo: HTTPS
> Referência SDD: `_reversa_sdd/prd.md#10-restricoes-tecnicas--nao-funcionais`, `_reversa_sdd/sdd/endpoint-plano-de-investigacao.md`, `_reversa_sdd/sdd/endpoint-busca-com-personas.md`, `_reversa_sdd/sdd/endpoint-auditoria-de-qualidade.md`, `_reversa_sdd/sdd/endpoint-redacao-do-dossier.md`

---

## 1. Visão Geral
Todas as chamadas a modelos de inteligência artificial do pipeline Deep Research são restritas ao padrão aberto OpenAI-compatible via rota `/v1/chat/completions`. O sistema segrega as inferências em duas categorias de modelo:
- **Modelo Leve (Light LLM):** Empregado na formulação do plano (persona `planejador`) e na orquestração paralela dos trabalhadores de busca (personas `historiador`, `visionario`, `cetico`, `futurista`). Prioriza baixa latência e parsing estruturado.
- **Modelo Forte (Strong LLM):** Empregado na auditoria crítica de consistência (persona `auditor`) para avaliação das 12 perguntas de qualidade e na síntese exaustiva do dossiê final (persona `redator final`). Prioriza raciocínio analítico denso e ancoragem factual.

---

## 2. Detalhes da Requisição (OpenAI-Compatible Chat Completion)

- **Endpoint:** `POST {LLM_BASE_URL}/chat/completions` (padrão: `https://api.openai.com/v1/chat/completions`)
- **Cabeçalhos Enviados:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <OPENAI_API_KEY>`
- **Timeout:** 600 segundos operacionais máximos
- **Política de Retentativas:** 1 tentativa inicial + 3 retentativas automáticas com backoff exponencial

### Formato do Payload Enviado
```json
{
  "model": "gpt-4o-mini",
  "temperature": 0.2,
  "response_format": { "type": "json_object" },
  "messages": [
    {
      "role": "system",
      "content": "Você é a persona auditor do sistema Deep Research..."
    },
    {
      "role": "user",
      "content": "Avalie o conteúdo coletado para o ponto 1 frente às 12 perguntas de qualidade..."
    }
  ]
}
```

---

## 3. Configuração Estrita sem Fallback Hardcoded
Conforme a regra RN-02 (`requirements.md#4-regras-de-negocio-novas-ou-alteradas`), o sistema não admite nomes de modelo ou parâmetros fixados diretamente no código fonte. Todos os parâmetros devem ser providos via:
- `LLM_MODEL_LIGHT` (modelo leve)
- `LLM_MODEL_STRONG` (modelo forte)
- `LLM_BASE_URL` (URL base da API)
- `OPENAI_API_KEY` (chave de autorização)
A ausência dessas variáveis ou registros de credencial interrompe o serviço com erro explícito de inicialização.

---

## 4. Códigos de Erro e Tratamento de Exceções

| Código HTTP | Causa | Tratamento |
|-------------|-------|------------|
| `429 Too Many Requests` | Limite de taxa ou quota de tokens atingida | Aciona backoff exponencial com jitter (espera de 2s a 30s) até 3 retries |
| `500 / 502 / 503` | Falha interna no provedor de inferência | Retentativa automática de conexão |
| `504 Gateway Timeout` | Resposta excedeu tempo limite | Cancela requisição e registra erro estruturado |