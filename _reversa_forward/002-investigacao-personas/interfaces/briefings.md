# Interface: Briefings API — delta da Feature 002

> Contrato pretendido após a Feature 002; não atesta entrega do código parcial.
> Fontes: [requirements](../requirements.md), §2.1, RF-01/RF-02/RF-03/RF-12 e esclarecimentos Q1/Q11/Q12/Q13/Q14/Q15/Q16 (superando Q4/Q6); [adendo 001](../../../_reversa_sdd/addenda/001-modulo-briefing.md).
> Atualizado em 2026-10-14: extinção de `/approve`, aprovação implícita no `/investigate`, revisão única no PATCH com auto-investigate.

## Autenticação e limites

Todos os endpoints exigem administrador por `require_admin`, definido em `app/core/security.py`. Mecanismos existentes: Bearer ou `X-API-Key` com o segredo administrativo configurado; ou cookie `dr_session`, acompanhado de `x-csrf-token` nas mutações. Não combinar mecanismos: o guard atual retorna HTTP 400 para credenciais ambíguas ou cabeçalho `X-Tenant-ID`.

- Tema: 3–300 caracteres, conforme contrato da 001 mantido; entradas com mais de 300 caracteres são rejeitadas com HTTP 422 e mensagem explícita sobre o limite de 300 (Q13).
- Rascunho válido: 3–7 pontos; título e descrição não vazios.
- Título de ponto: títulos e descrições não vazios gerados pelo Scout NÃO possuem teto de 500 caracteres (Q11; regra Q6 revogada). PATCH não aceita lista manual de pontos.
- Feedback: somente `{"note": "texto"}`, 3–4000 caracteres. Revisão única por briefing (Q16): segunda chamada a PATCH retorna HTTP 409.
- Identificador público canônico: `research_id`. Não emitir `id` como alias público; `briefings.id` e `research.id` permanecem o mesmo UUID no banco.

## Requisições e respostas

| Método e caminho | Request | Sucesso e response | Erros específicos |
|---|---|---|---|
| `POST /briefings` | `{"theme": "tema de pesquisa"}` | 201; objeto de briefing em `draft`, com o `research_id` criado antes da geração | 422 entrada/conteúdo inválido (inclusive tema > 300 com mensagem explícita, Q13); 409 conflito de estado/versão; mapeamento existente da criação: 500 configuração/prompt e 503 busca/geração indisponível |
| `GET /briefings/{research_id}` | UUID no path, sem body | 200; objeto atual de briefing | 404 inexistente |
| `PATCH /briefings/{research_id}` | `{"note": "Aprofundar riscos regulatórios"}` | 200 síncrono; objeto do briefing revisado (nova versão), já com aprovação implícita e investigação iniciada em background na mesma operação | 404 inexistente; 409 já revisado uma vez (2ª revisão bloqueada, Q16), conflito de versão ou pesquisa não elegível à revisão; 422 conteúdo inválido; falha terminal: 500 (configuração), 502 (modelo indisponível) ou 503 (busca Jina indisponível) conforme Q12; pesquisa fica `FAILED` e briefing `failed`, sem iniciar investigação |
| `POST /briefings/{research_id}/investigate` | Sem body (`{}` ou ausente) | 202; aprovação implícita do primeiro briefing válido em `draft` e início da investigação na mesma operação, em background | 404 inexistente; 409 re-disparo/concorrência ou briefing não elegível; 422 body inválido. Detalhes em [investigate.md](investigate.md) |
| `POST /briefings/{research_id}/approve` | — | **EXTINTO (2026-10-14)**. Endpoint removido do contrato sem substituto; nenhuma rota de negócio responde neste caminho | Não existe mais contrato de sucesso ou erro de negócio para este caminho |
| `POST /briefings/{research_id}/reopen` | Sem body; guard existente também aceita `{}` e JSON `null` | Nenhum sucesso pós-aprovação no contrato da 002 | 404 inexistente; 409 para `approved` ou transição inválida; 422 body inválido |
| `GET /briefings/approved/{research_id}` | UUID no path, sem body | 200; `research_id`, `theme`, `points`, `approved_at` | 404 inexistente; 409 não aprovado |
| `GET /briefings/{research_id}/versions` | UUID no path, sem body | 200; lista de snapshots com `version`, `status`, `points`, `error`, `approved_at`, `created_at` | 404 inexistente |

HTTP 401 indica credencial ausente/inválida; HTTP 403 é produzido pelo guard existente quando CSRF de sessão é inválido. UUID malformado e schemas inválidos recebem HTTP 422. Erros usam `{"detail": "mensagem segura"}` ou a estrutura de validação do FastAPI para 422; não incluir secrets, prompts ou CoT.

### Objeto de briefing — exemplo sintético

```json
{
  "research_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "theme": "Impactos da IA na medicina",
  "status": "draft",
  "points": [
    {"title": "Precisão", "description": "Avaliar precisão diagnóstica"},
    {"title": "Riscos", "description": "Examinar riscos clínicos"},
    {"title": "Regulação", "description": "Investigar regras aplicáveis"}
  ],
  "version": 1,
  "error": null,
  "approved_at": null
}
```

`draft` é estado do briefing; `PENDING_APPROVAL` é estado da pesquisa. Não substituir um pelo outro.

## Efeitos e idempotência

1. Criar briefing registra primeiro `research`; pontos ainda não existem em `research_points` durante geração/revisão.
2. PATCH usa tema original, rascunho anterior e feedback no Scout; dispara obrigatoriamente 1 nova consulta SERP Jina formulada pela IA (tema original + feedback); preserva pontos não afetados e ajusta/acrescenta foco conforme novas evidências; pesquisa fica `BRIEFING` durante a revisão. Em sucesso, gera a versão revisada, aprova implicitamente e inicia a investigação automaticamente em background na mesma operação: pontos persistem em `research_points` com `SCRAPER_IN_PROGRESS` e `attempt_count = 0`, pesquisa transita para `SCRAPER`, workers de 4 personas por ponto despachados em background, resposta síncrona 200. Sem segunda chamada a `/investigate` e sem confirmação intermediária. Falha terminal deixa pesquisa `FAILED`, briefing `failed`, sem iniciar investigação; recuperação exige novo briefing, conforme §2.1. Revisão é única: novo PATCH posterior retorna 409 (Q16).
3. Não existe aprovação explícita. `POST /briefings/{research_id}/investigate` sobre o primeiro briefing válido em `draft` opera aprovação implícita: status `draft` e ausência prévia de pontos em `research_points` NÃO retornam HTTP 409. Os pontos são persistidos diretamente com status `SCRAPER_IN_PROGRESS` e `attempt_count = 0`, a pesquisa vai para `SCRAPER` e os workers de 4 personas por ponto são despachados em background (HTTP 202). Re-disparos e concorrência retornam HTTP 409. Nenhum caminho agenda `schedule(run_research)` (Q1), inclusive aprovação/revisão legada.
4. GETs não alteram estado. POST de criação não possui chave de deduplicação documentada; não prometer reenvio seguro. PATCH produz nova versão quando aceito; CAS/conflito 409 não equivale a idempotência de request. Re-disparo do investigate e reopen aprovado recebem 409, sem duplicar pontos.

## Timeouts e fronteira existente

POST de criação e PATCH são síncronos no que tange à resposta HTTP; a investigação disparada por ambos os caminhos (investigate direto ou auto-investigate do PATCH) executa em background. Não há deadline HTTP total aprovado: não inventar SLA ou timeout global do Scout. Na geração existente da 001, `_resolve_briefing_timeout()` lê `SEARCH_TIMEOUT_SECONDS` (default atual 30s) por tentativa. Os limites 90s por chamada Jina/LLM e 600s por worker pertencem à investigação da 002, não devem ser aplicados automaticamente ao Scout da 001.

Divergências conhecidas do código parcial: `BriefingResponse` ainda possui alias `id`, `ApprovedBriefingResponse` ainda usa `id`. Títulos gerados pelo Scout sem teto (Q11) requerem ampliação de schema/colunas para `sa.Text`. No PATCH, a distinção canônica de 500 (configuração), 502 (geração LLM) e 503 (busca Jina) alinha formalmente o contrato pretendido (Q12) ao router atual. Rota `/approve` presente no código parcial deve ser removida na implementação da 002.
