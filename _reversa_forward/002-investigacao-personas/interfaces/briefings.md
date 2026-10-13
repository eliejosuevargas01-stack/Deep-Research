# Interface: Briefings API (Atualizada para Feature 002)

> Contrato HTTP atualizado do módulo de Briefing para alinhamento com `research_id`.

---

## 1. Alterações Contratuais

### 1.1 Campo de Identificador (`id` -> `research_id`)

Todos os endpoints que retornam o objeto de briefing passam a emitir o campo `research_id` em vez de `id`:

```json
{
  "research_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "theme": "Impacto da IA Generativa na Medicina Diagnóstica",
  "status": "draft",
  "points": [
    {
      "title": "Precisão em Imagens",
      "description": "Investigar acurácia em imagens..."
    }
  ],
  "version": 1,
  "error": null,
  "approved_at": null
}
```

*Endpoints impactados*:
- `POST /briefings` (status 201)
- `GET /briefings/{research_id}` (status 200)
- `PATCH /briefings/{research_id}` (status 200)
- `POST /briefings/{research_id}/approve` (status 200)
- `GET /briefings/approved/{research_id}` (status 200)

### 1.2 Transição de Aprovação (`POST /briefings/{research_id}/approve`)

Além de marcar o briefing como `approved`:
1. Cria os registros em `research_points` para cada ponto aprovado com `status = 'SCRAPER_PENDING'`.
2. Atualiza `research.status` para `'SCRAPER'`.

### 1.3 Bloqueio de Reabertura (`POST /briefings/{research_id}/reopen`)

Conforme deliberação do operador:
- Briefing aprovado **não pode voltar para rascunho**.
- Chamadas para `POST /briefings/{research_id}/reopen` em briefing com status `approved` retornam HTTP 409 Conflict (`"Briefing aprovado não pode ser reaberto"`).

### 1.4 Edição por Feedback (`PATCH /briefings/{research_id}`)

Substitui o PATCH antigo por lista de pontos (que deixa de existir).

- **Corpo**: `{"note": "texto livre do usuário"}`, mínimo 3 e máximo 4000 caracteres (mesmo formato do `BriefingApproval` legado e do frontend).
- **Comportamento**: o Scout roda a busca Jina de novo combinando o tema com o feedback e gera um novo rascunho (nova versão em `briefing_versions`). Pesquisa permanece em/volta para `BRIEFING` durante a geração e termina em `PENDING_APPROVAL`.
- **Resposta**: síncrona, HTTP 200 com o novo rascunho (mesmo schema do `POST /briefings`, com `research_id`).
- **Erros**: 409 se o briefing não está em `draft`; falha do Scout segue o tratamento do `POST /briefings`.
