# Adendo de Convergência: Módulo de Briefing (Backend)

> Identificador da feature: `001-modulo-briefing`  
> Data: `2026-10-11`  
> Cenário: `greenfield` (ancorado em PRD e SDD; sem extração de legado prévia)

## Vigência

Vigente desde 2026-10-11.

## Resumo da entrega

O módulo de briefing estabelece a etapa inicial do ciclo de pesquisa autônoma, recebendo um tema de pesquisa (validado entre 3 e 300 caracteres), executando busca SERP via Jina (sem extração de corpo de página), e gerando de 3 a 7 pontos de foco essenciais através de agente LLM (utilizando `gemini/gemini-3.8-flash` como padrão). O sistema inclui persistência relacional com controle de concorrência otimista (CAS), histórico de versões de briefing, API REST completa com 7 endpoints e resiliência com 4 tentativas sequenciais contra falhas transitórias de provedor e rede.

- Total de ações concluídas localmente: 28 ações atômicas (mais emenda E001).
- Total de ações registradas na sincronização parcial: 38 ações planejadas (10 aguardando validação final de credencial externa em produção).
- Suíte de validação: 184 testes unitários e de integração locais passando.

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|---|---|---|---|
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Implementação de validação de tema (3-300 caracteres) e restrição de pontos (3-7, alvo habitual 5). |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Adapter SERP exclusivo Jina sem raspagem de páginas, com retentativa sequencial de até 4 tentativas. |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Ciclo de vida completo do briefing: geração (`draft`), edição manual (3-7 pontos), aprovação e reabertura. |
| `_reversa_sdd/prd.md` | §4 Escopo (in) | componente-novo | Modelo padrão da role scout atualizado para `gemini/gemini-3.8-flash` com fallback explícito em runtime. |
| `_reversa_sdd/sdd/briefing.md` | §6.1 Requisitos Principais (RF-01 a RF-10) | componente-novo | Módulo `app/briefing/` implementado com domínio puro imutável, esquemas Pydantic rígidos e prompt loader em disco. |
| `_reversa_sdd/sdd/briefing.md` | §6.1 Requisitos Principais (RF-02/RF-10) | componente-novo | `JinaSerpClient` implementado com validação estrita de token ASCII imprimível, lock por instância e isolamento de redirecionamentos. |
| `_reversa_sdd/sdd/briefing.md` | §6.1 Requisitos Principais (RF-03/RF-04) | componente-novo | Orquestração de geração e binding LiteLLM isolado com supressão de retries de biblioteca e sanitização de segredos. |
| `_reversa_sdd/sdd/briefing.md` | §6.1 Requisitos Principais (RF-05 a RF-09) | componente-novo | Storage relacional assíncrono (tabelas `briefings` e `briefing_versions`), migração Alembic 0006 e controle CAS com HTTP 409. |
| `_reversa_sdd/sdd/briefing.md` | §6.1 Requisitos Principais (RF-07) | componente-novo | API HTTP canônica `/briefings` expondo 7 endpoints protegidos por autenticação de administrador e validação prévia. |
| `app/services/settings.py` | Resolução de modelo scout | regra-alterada | `DEFAULT_ROLE_MODELS["scout"]` e `runtime_settings()` configurados para `gemini/gemini-3.8-flash`. |

## Regras sob vigilância

Os watch items abaixo protegem as regras de negócio e contratos técnicos da feature:

- `W001` a `W032` em `_reversa_forward/001-modulo-briefing/regression-watch.md`

## Fontes

- `_reversa_forward/001-modulo-briefing/requirements.md`
- `_reversa_forward/001-modulo-briefing/actions.md`
- `_reversa_forward/001-modulo-briefing/legacy-impact.md`
- `_reversa_forward/001-modulo-briefing/regression-watch.md`
- `_reversa_forward/001-modulo-briefing/progress.jsonl`
- `_reversa_sdd/prd.md`
- `_reversa_sdd/sdd/briefing.md`

## Atualização 2026-10-12

- Validação consolidada de 184 testes unitários e de integração locais passando (exit 0).
- Emenda E001 (role scout padrão atualizada para `gemini/gemini-3.8-flash`) incorporada e validada.
- Feature 001 sincronizada e finalizada para deploy em produção no Coolify.

