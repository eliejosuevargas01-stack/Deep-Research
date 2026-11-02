# SDD v10 — Pipeline único em Hermes (sem Jina, sem chamadas diretas ao modelo)

Status: normativo. Substitui o modo duplo de v9. Toda a investigação roda dentro do
container da API, por um perfil Hermes embutido na imagem.

## 1. Superfície

- `/api/v1/plan`, `/api/v1/search`, `/api/v1/audit`, `/api/v1/writer` mantêm **os mesmos
  schemas de resposta** (`PlanResponse`, `SearchResponse`, `AuditResponse`, `WriterResponse`).
- Nenhum endpoint resolve credencial Jina nem instancia `LLMClient`. `DR_PIPELINE_MODE`
  deixa de existir: o caminho Hermes é o único.
- A montagem das respostas continua em `app/core/hermes_adapter.py`, derivada dos arquivos
  Markdown do workspace da pesquisa.

## 2. Perfil Hermes embutido

- Perfil `deep-research` em `hermes_home/profiles/deep-research/` dentro do repositório,
  copiado para `$HERMES_HOME/profiles/deep-research` na imagem.
- 1 orquestrador (planner) + 6 subagentes: `historiador`, `visionario`, `cetico`,
  `futurista`, `auditor`, `redator`.
- O planner usa `delegate_task` para acionar cada subagente; cada subagente recebe o papel
  no próprio prompt e escreve **somente** o seu arquivo. `delegation.max_spawn_depth >= 2`.
- Modelo via 9router (`LLM_BASE_URL`, `OPENAI_API_KEY`), configurado no `config.yaml` do
  perfil; sem chave de Jina.

## 3. Workspace por pesquisa

`$DR_HERMES_PESQUISAS_DIR/<slug-do-tema>-<8 primeiros do id>/` — um diretório por pesquisa,
criado por `hermes_planner.criar_workspace`. Contrato de arquivos (inalterado):

- `PLAN.md` — planner. Contém bloco ```json``` com `versao, tema, objetivo, escopo,
  perguntas, personas, criterios_evidencia, criterios_aprovacao` (lido por `plan_payload`).
- `HISTORIADOR_SEARCH.md`, `VISIONARIO_SEARCH.md`, `CETICO_SEARCH.md`,
  `FUTURISTA_SEARCH.md` — append-only. Cada tentativa abre `tentativa N`, registra as URLs
  consultadas e fecha com `TOTAL: N páginas`.
- `AUDITORIA.md` — append-only, uma seção por rodada:
  `## Rodada N — APROVADO|REPROVADO — nota X/12`.
- `DOSSIE.md` — redator. Lê `PLAN.md`, os quatro `*_SEARCH.md` e `AUDITORIA.md`; grava o
  dossiê final.
- `TEMA.md`, `hermes.log`, `usage.json` — operacionais.

## 4. Ciclo

1. planner grava `PLAN.md`;
2. planner delega os 4 searchers em paralelo — cada um faz a própria pesquisa e escreve o
   seu `*_SEARCH.md`;
3. planner delega o `auditor`, que lê os 4 arquivos + `app/CRITERIA.md` e escreve uma seção
   em `AUDITORIA.md`;
4. se a última rodada for `REPROVADO`, o planner redispara os searchers (append de nova
   `tentativa`) e reaudita, até `DR_MAX_RODADAS` (default 3) reprovações;
5. no teto, o planner delega o `redator` mesmo sem aprovação; o dossiê inclui
   `## Ressalvas da auditoria` nomeando cada ponto reprovado, critérios falhos e lacunas;
6. `DOSSIE.md` existe ⇒ `WriterResponse.status = "concluido"`.

## 5. Empacotamento

- `Dockerfile.backend` instala `hermes-agent==0.19.0` por pip e copia o perfil.
- `HERMES_HOME=/app/hermes-home`; a API invoca `hermes -z <prompt> --usage-file ...` com
  `HERMES_PROFILE=deep-research` e `cwd` no workspace.
- `docker-compose.prod.yml` monta `data/` e `frontend/dist`; sem `JINA_*`, sem
  `DR_PIPELINE_MODE`, sem container vizinho.
- Sem `bwrap` dentro do container: sandbox é o próprio container.

## 6. Critérios de aceite

- `grep -rn "JinaClient\|LLMClient" app/api` vazio.
- `plan/search/audit/writer` respondem com os schemas atuais usando apenas arquivos.
- `hermes --version` dentro da imagem = 0.19.0 e `hermes profile list` mostra `deep-research`.
- Uma pesquisa real termina com `DOSSIE.md` não vazio e `AUDITORIA.md` com ≥1 rodada.
