# Onboarding local seguro — PLAN-005-B

> Plano executável para humano após actions/coding, não relato de teste passado. Produto desta sprint: somente documentação. Q-501/Q-502 continuam premissas de falha segura, não respostas humanas.

## 1. Limites e ambiente observado

Raiz `/root/projects/deep-research`. Inspeção sem `.env`: Python disponível 3.14.7; `pytest`, `httpx`, `sqlalchemy`, `alembic`, `asyncpg`, `aiosqlite` localizáveis por `importlib.util.find_spec`. Isso não prova compatibilidade/import ou suite verde. `requirements.txt` declara FastAPI, uvicorn, Pydantic/settings, SQLAlchemy async, asyncpg, aiosqlite, Alembic, cryptography, PyJWT, httpx, aiohttp, LiteLLM e pytest. Nenhuma instalação, servidor, DB ou teste de produto executado nesta sprint.

Não executar stack padrão, deploy, probes de produção, `tests/e2e_production_probe.py`, comandos destrutivos de DB ou suite inteira sem isolamento. Nunca usar base de desenvolvimento/produção, URL herdada ou senha/token literal. Não ler/carregar `.env`, inclusive por import indireto: `app/core/config.py` configura `env_file=".env"`, portanto desabilitar essa leitura antes de importar app/testes. Sem provedor pago, novo framework, modelo ou dependência.

## 2. Checks já feitos e comandos futuros separados

Já feitos: leitura estática dos mounts/decorators/schemas/modelos, grafo Alembic head 0007 e descoberta do runner/dependências. Checks documentais desta entrega ficam no resumo final do executor, sem inferir execução de testes. Todo comando abaixo é **planejado**, não executado nesta sprint.

### Runner preferido: pytest em processo isolado, SQLite memória e providers simulados

Com ambiente local existente, executar da raiz o bloco abaixo somente quando quiser rodar regressões. Ele não instala dependências nem escreve arquivo auxiliar. Configuração temporária existe só no processo. `-B`, `PYTHONDONTWRITEBYTECODE` e plugin cache desativado evitam arquivos de cache. Não remover defesa de isolamento para contornar falha.

```bash
cd /root/projects/deep-research
PYTHONDONTWRITEBYTECODE=1 python -B - <<'PY'
import base64
import os
import secrets
from unittest.mock import patch

# Não herdar URLs/chaves/proxies do shell. Nunca imprimir valores gerados.
for name in tuple(os.environ):
    if name.endswith(('_API_KEY', '_API_TOKEN', '_API_BASE', '_MODEL')) or name in {
        'DATABASE_URL', 'TEST_DATABASE_URL', 'API_AUTH_SECRET', 'ADMIN_PASSWORD',
        'SESSION_SECRET', 'APP_ENCRYPTION_KEY', 'HTTP_PROXY', 'HTTPS_PROXY',
        'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy',
    }:
        os.environ.pop(name, None)
os.environ.update(
    ENVIRONMENT='test', DATABASE_URL='sqlite+aiosqlite:///:memory:',
    ADMIN_PASSWORD=secrets.token_urlsafe(32), SESSION_SECRET=secrets.token_urlsafe(48),
    API_AUTH_SECRET=secrets.token_urlsafe(32),
    APP_ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
)
from pydantic_settings import BaseSettings
original = BaseSettings.__init__
def without_dotenv(self, **kwargs):
    kwargs['_env_file'] = None
    original(self, **kwargs)
# API fixtures já substituem SERP/LLM e investigação background.
with patch.object(BaseSettings, '__init__', without_dotenv):
    import pytest
    raise SystemExit(pytest.main([
        '-q', '-p', 'no:cacheprovider', 'tests/test_briefing_api.py',
    ]))
PY
```

`tests/test_briefing_api.py` usa `unittest.IsolatedAsyncioTestCase`, SQLite memória, `ASGITransport`, `FakeSerp`, `FakeLLM`, dependency overrides de DB e mock de `InvestigationService.run_investigation`. Credenciais fixtures internas são somente teste; não copiá-las para requests humanos. Essa suite testa HTTP, não prova ciclo real até Report, porque investigação é mockada. Se módulo falhar, registrar exit code/erro seguro e parar; não trocar para API paga.

Outras regressões existentes, para seleção posterior após ler fixtures/isolamento: `tests/investigation/test_jina_tool.py`, `test_persona_worker.py`, `test_investigation_e2e.py`, `test_investigation_runtime_regressions.py`, `tests/audit/test_audit_api.py`, `tests/integration/test_full_pipeline.py`, `tests/test_briefing_generation_boundaries_qa.py`, `tests/test_briefing_lifecycle_qa.py`. `tests/test_briefing_migration.py` e `tests/investigation/test_investigation_migration.py` não substituem prova Alembic PostgreSQL. Não declarar esses testes compatíveis com runner acima sem examinar suas fixtures. Testes novos abaixo são **propostos**, sem nomes de arquivo/node fictícios; actions definirá localização e comandos.

## 3. Exercício HTTP sem rede paga

Preferir ampliar fixture `BriefingAPI` existente com `ASGITransport`, SERP/LLM simulados e autenticação de teste. Não abrir uvicorn apontado a configuração real. Na fixture, usar headers/cookie gerados por setup seguro; nunca colar token/password literal. Se cookie for escolhido, incluir CSRF válido nas mutações e não enviar Bearer/API key simultâneos.

1. POST `/briefings`, somente `{"theme":"Energia solar em escolas"}`. Assert 201, `status="draft"`, pontos completos e persistidos na resposta; Scout recebeu SERP, não dez corpos investigativos. Capturar `research_id = response.json()["research_id"]` real. Não inventar UUID para encadear requests.
2. Escolher **A ou B**, não ambos na mesma pesquisa. A: PATCH com `{"note":"Detalhar custos e limites das fontes"}`, assert 200, revisão concluída/autoaprovada e um agendamento background. Como negativo deliberado, uma segunda revisão recebe 409 e não altera dados nem agenda novamente; não tentar corrigir esse 409 com terceira revisão ou investigate. B: POST `/briefings/{research_id}/investigate` sem body; assert 202, reserva única e status SCRAPER. Para exercitar outra alternativa, criar outra pesquisa e capturar outro ID real.
3. Assert payload misto com campo proibido recebe 422 sem alteração parcial; auth ausente 401, ambígua 400, cookie sem CSRF 403. Erros não vazam corpo/input/segredos. Não usar endpoint approve novo, polling de geração ou campo de rodada no frontend.
4. Fixtures de ciclo propostas abaixo deixam investigação executar com ferramentas/LLM simulados, não mockam o método inteiro. Ao concluir, consultar GET `/api/reports/{research_id}`, assert 200 e campos do contrato. Antes de existir Report, 404 não é conclusão. Via sessão isolada confirmar um Report e Research DONE.
5. Repetir prova pelo entrypoint legado POST `/api/research`, preservando response próprio, dependências e scheduler; resume deve manter assinatura e não fabricar identidade de ativos históricos. Zero callback real; simular falha e conferir Report/DONE intactos. Não chamar retry-callback contra destino externo.

## 4. Exercícios determinísticos propostos

| RF | Preparação controlada | Assert necessário, não resultado já obtido |
|---|---|---|
| RF-501 | `httpx.MockTransport`: dez páginas, cada uma com marcador final além de 100000 caracteres; HTML com header/footer/nav/script/style/anúncios por atributos, tags aninhadas/malformadas | Request Jina `num=10`; dez corpos/títulos/URLs/consulta chegam completos ao contexto; boilerplate removido sem apagar trecho informativo nem marcador final; description/snippet não substituem corpo |
| RF-502 | LLM fake gera query inicial, repete query, tenta quatro distintas e final antes de buscar; outro caso para cedo | Primeira query vem do modelo; 1 a 3 distintas por persona/ponto/rodada; igualdade `query.strip()` deduplica sem rede/orçamento extra; final sem primeira busca rejeitado; retries transporte separados |
| RF-503 | Sessões isoladas gravam quatro personas reais e rodada positiva; negativos branco, fonte não lida, erro técnico e NULL histórico | Quatro linhas válidas committed antes merge; used_urls subset de corpos efetivamente lidos; terminal imutável; replay idêntico relê e divergente conflita sem overwrite |
| RF-504 | Instrumentar auditor consultando banco; preparar 3/4, duplicata, outra rodada, pesquisa/ponto incompatíveis e corrida | Nenhum merge/audit nos negativos; com quatro atuais válidos, merge committed único contém quatro IDs/análises/fontes/contradições/lacunas antes audit; CAS rejeita veredito obsoleto |
| RF-505 | Dois pontos, auditor fake reprova quatro vezes cada; simular também falha técnica de persona | Exatamente quatro auditorias por ponto, nenhuma quinta investigação; quarta reprovação caveat; falha técnica não incrementa tentativa; Writer apenas depois de todos conclusivos |
| RF-506 | Todos pontos conclusivos sem conteúdo aproveitável, zero linhas Evidence; segundo caso misto | Report curto com seção/limitação por ponto, sem mínimo artificial/fato/URL inventados, DONE; misto conserva fatos citados e limitações separadas |
| RF-507 | Proposta didática não factual e fatos sem citação em prosa/negrito/lista/tabela | Negrito não vira lista falsa; proposta aceita, quatro formatos factuais negativos; rótulo e URL conhecida não isentam fatos |
| RF-508 | Executar ambos entrypoints reais com transporte/LLM fakes, dependências entre pontos, retomada WRITE e corrida; callback fake falha | Um Report/DONE por pesquisa, sem duplicação/overwrite; retomada WRITE sem Report escreve; DONE/Report não reprocessa; callback falho mantém entrega |
| RF-509 | Fixture HTTP da seção 3 | POST201/PATCH200 contêm briefing concluído; segunda revisão409 sem reenvio corretivo; alternativa investigate202; uma decisão, sem mudança frontend |

Adicionar prova de preservação: mesma persona/URL em rodada posterior com outra citação verificada não sobrescreve Evidence original nem perde citação adicional em result/merge/bundle conclusivo do Writer. Preservar `version_id_col` e `uq_evidence_source`.

Negativos de segurança: SSRF/redirect/DNS privado bloqueados, fonte e operador tratados como dados não confiáveis, sem prompt injection executado, sem corpos/segredos/prompts internos em eventos/erros/persistência. MockTransport não deve neutralizar guardrails de URL sem asserts equivalentes.

Q-501: nove corpos, página ilegível ou contexto insuficiente produzem falha explícita sem truncar/fingir dez leituras/sucesso parcial. Q-502: persona fatal/crash preserva material quando possível, impede merge/audit e não vira reprovação/conclusão. Não autorizar recuperação automática nova nem Writer com barreira incompleta.

## 5. PostgreSQL efêmero — execução futura condicionada

Não executar migration nesta sprint. Seguir protocolo de `data-delta.md` §5. Requer instância recém-criada estritamente descartável, não banco preexistente com nome `_test`. Executor identifica host/porta/volume exclusivos antes de fornecer URL; `TEST_DATABASE_URL == DATABASE_URL`, ENVIRONMENT=test e `.env` desabilitado. Nunca escolher URL default de `app/core/config.py`, ambiente herdado ou base de desenvolvimento/produção. Se runner/container disponível não estiver comprovado, parar e registrar bloqueio; sem install/deploy como atalho.

Sequências futuras pelo runner Python seguro, com URL efêmera validada em memória e Alembic programático: `command.upgrade(Config('alembic.ini'), 'head')` para clean upgrade; outra base no parent real para seed histórico e populated upgrade; `command.downgrade(cfg, parent_real)` só nessa base descartável, após reconhecer perda de tabela/campos novos, seguido de reupgrade. Não usar `create_all()` para preencher lacuna de migration. Head observado 0007; ID novo/parent recalculados no coding. `tests/test_postgres.py` contém guard de URL explícita e sufixo `_test`, mas não prova origem efêmera sozinho.

Asserts de clean/populated/downgrade constam em data-delta: constraints positivas, uniques, histórico NULL intacto, ativos retidos, DONE/Report/Evidence preservados e nenhuma promoção artificial. Descartar somente instância/volume criado para teste. Capturar exit codes e diferenças esperadas sem imprimir credenciais; não reportar pass antes de executar.

## 6. Saída esperada da validação futura

Registrar comando, ambiente descartável comprovado, exit code, asserts executados, skips e limites de MockTransport/LLM fake; nenhuma equivalência com provedor live. Falha ou dependência ausente fica explícita. Actions, revisão independente, coding e testes continuam pendentes; este documento não aprova gates nem altera estado Reversa. Sem novo modelo/provedor/frontend/refactor amplo.
