# Adendo: 002-pipeline-autonomo-seguro

> Data: 2026-10-22
> Cenário: greenfield

## Vigência

Vigente desde 2026-10-22.

## Resumo da entrega

Extensão de segurança e continuidade autônoma do monólito Deep Research:
1. Autenticação por chave de API (`X-API-Key`) em todas as rotas de negócio.
2. Continuidade assíncrona com `POST /api/v1/plan` (`async_execute=true`) e `PipelineRunner`.
3. Integração dinâmica de `CALLBACK_WEBHOOK_URL` e `WEBHOOK_HMAC_SECRET` nas credenciais.
4. Rota de monitoramento em tempo real `GET /api/v1/pipeline/{id_pesquisa}/status`.

Total de ações concluídas: 10 de 10 (100%).

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `_reversa_sdd/prd.md` | Escopo | componente-novo | Adicionada orquestração contínua e proteção de API Key |
| `_reversa_sdd/sdd/endpoint-planejamento.md` | API | componente-novo | Suporte a `async_execute` e resposta HTTP 202 Accepted |
| `_reversa_sdd/sdd/modulo-credenciais-e-seguranca.md` | Segurança | componente-novo | Implementada autenticação timing-safe via `verify_api_key` |

## Fontes

- `_reversa_forward/002-pipeline-autonomo-seguro/requirements.md`
- `_reversa_forward/002-pipeline-autonomo-seguro/legacy-impact.md`
- `_reversa_forward/002-pipeline-autonomo-seguro/actions.md`
