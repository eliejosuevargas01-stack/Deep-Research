# Adendo de Convergência: Módulo de Briefing (Backend)

> Identificador da feature: `001-modulo-briefing`
> Data: `2026-10-11` (Revisado em `2026-10-15`)
> Cenário: `greenfield` (ancorado em PRD e SDD; sem extração de legado prévia)

## Vigência

Vigente desde 2026-10-11.

## Resumo da entrega

O módulo de briefing estabelece a etapa inicial do ciclo de pesquisa autônoma:
- 🟢 CONFIRMADO — Recebimento e validação de tema entre 3 e 300 caracteres [`app/briefing/domain.py:10-11,31-37`, `app/briefing/schemas.py:48`].
- 🟢 CONFIRMADO — Busca SERP via Jina sem extração de corpo de página [`app/briefing/serp_client.py:11,89,124-143`].
- 🟢 CONFIRMADO — Geração de 3 a 7 pontos de foco através de agente LLM [`app/briefing/domain.py:12-13,40-53`, `app/briefing/service.py:27-30,108`].
- 🟢 CONFIRMADO — Modelo padrão da role scout configurado para `gemini/gemini-3.8-flash` [`app/services/settings.py:13,303`].
- 🟢 CONFIRMADO — Persistência relacional com controle de concorrência otimista (CAS) via HTTP 409 [`app/briefing/storage.py:103-124`, `app/briefing/router.py:137-139`].
- 🟢 CONFIRMADO — Histórico de versões de briefing append-only [`alembic/versions/0006_briefing_storage.py:40-66`, `app/briefing/storage.py:89-96,124`].
- 🟢 CONFIRMADO — API REST completa com 7 endpoints protegidos por autenticação de administrador [`app/briefing/router.py:141,202,222,232,289,308,327`].
- 🟢 CONFIRMADO — Resiliência com 4 tentativas sequenciais contra falhas transitórias de provedor e rede [`app/briefing/serp_client.py:12,65`, `app/briefing/service.py:74,94`, `app/briefing/llm_binding.py:46-86`].
- 🟢 CONFIRMADO — Total de 28 ações atômicas concluídas localmente mais emenda E001 [decisão documental `_reversa_forward/001-modulo-briefing/actions.md:29-59`].
- 🟢 CONFIRMADO — Total de 38 ações registradas na sincronização parcial, sendo 10 externas planejadas [decisão documental `_reversa_forward/001-modulo-briefing/actions.md:61-75`].
- 🟢 CONFIRMADO — Suíte de validação com testes unitários e de integração locais passando comprovadamente no baseline [registro histórico `progress.jsonl` e execução pytest].

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta | Nível e Evidência |
|---|---|---|---|---|
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Implementação de validação de tema (3-300 caracteres) e restrição de pontos (3-7, alvo habitual 5). | 🟢 CONFIRMADO [`app/briefing/domain.py:10-13,31-53`, `app/briefing/schemas.py:40-60`] |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Adapter SERP exclusivo Jina sem raspagem de páginas, com retentativa sequencial de até 4 tentativas. | 🟢 CONFIRMADO [`app/briefing/serp_client.py:11-12,60-75,89,124-143`] |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Ciclo de vida do briefing: geração (`draft`), aprovação e transições de estado. | 🟢 CONFIRMADO [`app/briefing/domain.py:16-20,94-156`, `app/briefing/router.py:141-306`; Nota de alinhamento: Reabertura bloqueada com HTTP 409 (`domain.py:158-161`, `router.py:318-324`) e edição manual de pontos extinta em prol de feedback `note` foram aprovadas como quebra explícita da 001 pela decisão vigente da Feature 002 (`_reversa_forward/002-investigacao-personas/requirements.md:134-137,231,347-349`); specs da 001 e SDD briefing estão desatualizadas perante a decisão 002 vigente; itens remanescentes de C8 (extinção de `/approve`, aprovação implícita via `/investigate` e auto-investigate no PATCH) permanecem como escopo futuro planejado] |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Modelo padrão da role scout atualizado para `gemini/gemini-3.8-flash` com fallback explícito em runtime. | 🟢 CONFIRMADO [`app/services/settings.py:13,303`] |
| `_reversa_sdd/sdd/briefing.md` | §6.1 Requisitos Principais (RF-01 a RF-10) | componente-novo | Módulo `app/briefing/` implementado com domínio puro imutável, esquemas Pydantic rígidos e prompt loader em disco. | 🟢 CONFIRMADO [`app/briefing/domain.py:77-92`, `app/briefing/schemas.py:27-135`, `app/briefing/prompt_loader.py:10-23`] |
| `_reversa_sdd/sdd/briefing.md` | §6.1 Requisitos Principais (RF-02/RF-10) | componente-novo | `JinaSerpClient` implementado com validação estrita de token ASCII imprimível, lock por instância e isolamento de redirecionamentos. | 🟢 CONFIRMADO [`app/briefing/serp_client.py:49-50,58-61,92`] |
| `_reversa_sdd/sdd/briefing.md` | §6.1 Requisitos Principais (RF-03/RF-04) | componente-novo | Orquestração de geração e binding LiteLLM isolado com supressão de retries de biblioteca e sanitização de segredos. | 🟢 CONFIRMADO [`app/briefing/service.py:68-111,233-323`, `app/briefing/llm_binding.py:144-149,162-164`] |
| `_reversa_sdd/sdd/briefing.md` | §6.1 Requisitos Principais (RF-05 a RF-09) | componente-novo | Storage relacional assíncrono (tabelas `briefings` e `briefing_versions`), migração Alembic 0006 e controle CAS com HTTP 409. | 🟢 CONFIRMADO [`app/briefing/storage.py:71-147`, `alembic/versions/0006_briefing_storage.py:17-67`, `app/briefing/router.py:137-139`] |
| `_reversa_sdd/sdd/briefing.md` | §6.1 Requisitos Principais (RF-07) | componente-novo | API HTTP canônica `/briefings` expondo 7 endpoints protegidos por autenticação de administrador e validação prévia. | 🟢 CONFIRMADO [`app/briefing/router.py:141,202,222,232,289,308,327`, `app/briefing/router.py:146,206,226,237,294,313,331`] |
| `app/services/settings.py` | Resolução de modelo scout | regra-alterada | `DEFAULT_ROLE_MODELS["scout"]` e `runtime_settings()` configurados para `gemini/gemini-3.8-flash`. | 🟢 CONFIRMADO [`app/services/settings.py:13,303`] |

## Regras sob vigilância

Os watch items abaixo protegem as regras de negócio e contratos técnicos da feature:

- 🟢 CONFIRMADO — `W001` a `W032` em `_reversa_forward/001-modulo-briefing/regression-watch.md` [decisão documental `_reversa_forward/001-modulo-briefing/regression-watch.md:14-110`].

## Fontes

- `_reversa_forward/001-modulo-briefing/requirements.md`
- `_reversa_forward/001-modulo-briefing/actions.md`
- `_reversa_forward/001-modulo-briefing/legacy-impact.md`
- `_reversa_forward/001-modulo-briefing/regression-watch.md`
- `_reversa_forward/001-modulo-briefing/progress.jsonl`
- `_reversa_sdd/prd.md`
- `_reversa_sdd/sdd/briefing.md`

## Atualização 2026-10-12

- 🟢 CONFIRMADO — Validação consolidada de testes unitários e de integração locais passando (exit 0) [registro histórico `progress.jsonl` e execução pytest].
- 🟢 CONFIRMADO — Emenda E001 (role scout padrão atualizada para `gemini/gemini-3.8-flash`) incorporada e validada [decisão documental `_reversa_forward/001-modulo-briefing/actions.md:57`, `app/services/settings.py:13`].
- 🟢 CONFIRMADO — Feature 001 sincronizada e finalizada para deploy em produção no Coolify [decisão documental `_reversa_forward/001-modulo-briefing/progress.jsonl`].
