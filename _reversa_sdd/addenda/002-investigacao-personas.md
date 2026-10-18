# Adendo de Convergência: Investigação Paralela por Personas

> Identificador da feature: `002-investigacao-personas`
> Data: `2026-10-16`
> Cenário: `forward` (ancorado em PRD, SDD briefing e deliberações oficiais de 2026-10-16)

## Vigência

Vigente desde 2026-10-16.

## Resumo da entrega

O módulo de investigação por personas executa a investigação aprofundada dos pontos definidos no briefing:
- 🟢 CONFIRMADO — 4 Personas analíticas paralelas (Historian, Skeptic, Pragmatist, Futurist) via LiteLLM e Jina Search [`app/investigation/worker.py:12-35`].
- 🟢 CONFIRMADO — Resiliência de investigação: avanço para auditoria permitido se ao menos 1 persona obtiver sucesso; status FAILED apenas com 100% de pontos falhos [`app/investigation/service.py:157-163`].
- 🟢 CONFIRMADO — Limite estrito de no máximo 3 buscas web por ponto com parada voluntária pela IA [`app/investigation/worker.py:16,210-250`].
- 🟢 CONFIRMADO — Autocorreção de JSON malformado em até 3 tentativas com feedback do erro de parsing [`app/investigation/worker.py:17,343-351`].
- 🟢 CONFIRMADO — Timeout global de 600s (10 minutos) por agente com cancelamento limpo [`app/investigation/worker.py:18,208`].
- 🟢 CONFIRMADO — Privacidade e conformidade: zero persistência de raciocínio intermediário ou prompts brutos no banco; apenas sínteses analíticas finais e array `read_urls` gravados [`app/investigation/worker.py:311-313`].
- 🟢 CONFIRMADO — Gravação integral de 100% das URLs retornadas pela Jina no campo `read_urls` [`app/investigation/worker.py:311-313`].
- 🟢 CONFIRMADO — Retomada seletiva pós-restart: agentes reiniciam apenas os pontos pendentes ou falhos [`app/investigation/service.py:110-112`].
- 🟢 CONFIRMADO — Herança automática de modelo da role scout configurada nas settings [`app/investigation/prompts.py:79-95`, `app/services/settings.py:12-13,303`].
- 🟢 CONFIRMADO — Extinção definitiva da rota `POST /briefings/{research_id}/approve` (D-21 / T036 / A-C8-03) [`app/briefing/router.py`, `app/routers/research.py`].
- 🟢 CONFIRMADO — Aprovação implícita e disparo em etapa única via `POST /briefings/{research_id}/investigate` sobre rascunho (D-22 / T037) [`app/investigation/router.py:35-72`].
- 🟢 CONFIRMADO — Revisão única com consulta SERP IA derivada de tema + feedback, auto-aprovação e auto-investigate via `PATCH /briefings/{research_id}` (D-23 / T038 / E001) [`app/briefing/router.py:308-340`, `app/briefing/service.py:116-152`].
- 🟢 CONFIRMADO — Bloqueio de 2ª revisão com HTTP 409 Conflict (D-24 / T039) [`app/briefing/router.py:312-316`].
- 🟢 CONFIRMADO — Emenda E001 aplicada e auditada com 100% de resolução dos findings A-C8-01 a A-C8-06 e D-01 [`_reversa_forward/002-investigacao-personas/audit-report.md`].
- 🟢 CONFIRMADO — Total de 40 ações atômicas (T001 a T040) e emenda E001 concluídas com testes passando (exit 0) [`_reversa_forward/002-investigacao-personas/actions.md`, `progress.jsonl`].

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta | Nível e Evidência |
|---|---|---|---|---|
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Orquestrador de investigação por personas (`app/investigation/`) integrado ao pipeline assíncrono. | 🟢 CONFIRMADO [`app/investigation/service.py:30-180`, `app/investigation/router.py:25-80`] |
| `_reversa_sdd/sdd/briefing.md` | §6 Ciclo de Vida | regra-alterada | Extinção de rota de aprovação separada; aprovação ocorre exclusivamente via `/investigate` (implícita) ou `/briefings` PATCH (automática). | 🟢 CONFIRMADO [`app/briefing/router.py:308-340`, `app/investigation/router.py:35-72`] |
| `_reversa_sdd/sdd/briefing.md` | §6 Ciclo de Vida | regra-alterada | Bloqueio de reabertura de briefing aprovado e bloqueio de 2ª revisão com HTTP 409 Conflict. | 🟢 CONFIRMADO [`app/briefing/router.py:312-324`] |
| `contracts.md` | Endpoints | contrato-alterado | Rota `/approve` removida; `POST /briefings/{id}/investigate` e `PATCH /briefings/{id}` assumem transição para `SCRAPER`. | 🟢 CONFIRMADO [`contracts.md`, `app/investigation/router.py`, `app/briefing/router.py`] |

## Fontes

- `_reversa_forward/002-investigacao-personas/requirements.md`
- `_reversa_forward/002-investigacao-personas/roadmap.md`
- `_reversa_forward/002-investigacao-personas/actions.md`
- `_reversa_forward/002-investigacao-personas/audit-report.md`
- `_reversa_forward/002-investigacao-personas/progress.jsonl`
- `_reversa_sdd/cross-review-result.md`
- `_reversa_sdd/questions.md`
- `_reversa_sdd/confidence-report.md`
