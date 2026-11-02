# Perfil Hermes `deep-research`

Perfil embutido na imagem do backend (SDD v10). Um único processo Hermes roda a
pesquisa inteira: o planner orquestra, quatro searchers pesquisam em paralelo, o
auditor julga e o redator escreve o dossiê. A troca entre papéis é por arquivos
Markdown no diretório da pesquisa — não há JSON de etapa para etapa.

```
deep-research/
├── SOUL.md       # protocolo do planner + contrato dos 6 subagentes
├── config.yaml   # 9router via LLM_BASE_URL/OPENAI_API_KEY, delegation
└── README.md
```

## Contrato de arquivos (lido por `app/core/hermes_adapter.py`)

| Arquivo | Dono | Regra |
|---|---|---|
| `PLAN.md` | planner | último bloco ` ```json ` com `versao, tema, objetivo, escopo, perguntas, personas, criterios_evidencia, criterios_aprovacao` |
| `HISTORIADOR_SEARCH.md` | historiador | append-only; `tentativa N` … `TOTAL: N páginas` |
| `VISIONARIO_SEARCH.md` | visionario | idem |
| `CETICO_SEARCH.md` | cetico | idem |
| `FUTURISTA_SEARCH.md` | futurista | idem |
| `AUDITORIA.md` | auditor | append-only; `## Rodada N — APROVADO\|REPROVADO — nota X/12` |
| `DOSSIE.md` | redator | dossiê final; só URLs presentes nos `*_SEARCH.md` |

## Ambiente

| Variável | Uso |
|---|---|
| `LLM_BASE_URL` | endpoint OpenAI-compatible do 9router (ex.: `https://<9router>/v1`) |
| `OPENAI_API_KEY` | chave do 9router |
| `LLM_MODEL_STRONG` | modelo do planner e dos subagentes |
| `HERMES_HOME` | raiz que contém `profiles/deep-research/` (imagem: `/app/hermes-home`) |
| `DR_HERMES_PROFILE` | perfil usado por `app/core/hermes_planner.py` (default do código: `planner`; use `deep-research`) |
| `DR_HERMES_PESQUISAS_DIR` | raiz dos workspaces (default `<repo>/data/pesquisas`) |

Nenhuma variável ou rota Jina é usada.

## Rodar local

```bash
# na raiz do repo; o workspace da pesquisa é o cwd do processo
HERMES_HOME="$PWD/hermes_home" \
LLM_BASE_URL="https://<9router>/v1" \
OPENAI_API_KEY="<chave>" \
LLM_MODEL_STRONG="<modelo>" \
hermes -p deep-research -z "Tema da pesquisa: ..." --usage-file /tmp/usage.json
```

`-p deep-research` é o que seleciona o perfil nesta versão; `HERMES_PROFILE` sozinho
não troca o `HERMES_HOME` (o backend usa `-p $(DR_HERMES_PROFILE)`).

## Testar o protocolo com tema dummy

1. Crie um workspace vazio e rode o planner com um tema curto e verificável:

```bash
W=/tmp/pesquisa-dummy && mkdir -p "$W" && cd "$W"
HERMES_HOME=<repo>/hermes_home LLM_BASE_URL=... OPENAI_API_KEY=... LLM_MODEL_STRONG=... \
hermes -p deep-research -z "Tema da pesquisa: o que é o Protocolo de Montreal e qual seu efeito documentado na camada de ozônio?
Diretório de trabalho: $W
Máximo de reprovações do auditor: 1

Execute o protocolo completo descrito no seu SOUL e responda apenas \`OK <caminho absoluto do DOSSIE.md>\`." \
--usage-file "$W/usage.json"
```

2. Confira o contrato sem chamar modelo nenhum:

```bash
cd <repo> && python3 - "$W" <<'PY'
import sys
from pathlib import Path
from app.core.hermes_adapter import plan_payload, search_payload, audit_payload, writer_payload
w = Path(sys.argv[1])
print("plano:", plan_payload(w)["valido"], plan_payload(w)["erro"])
print("busca:", search_payload("dummy", w)["resumo_coletas"][0]["total_urls_fonte"], "URLs")
print("auditoria:", audit_payload("dummy", w)["auditorias"][0])
print("writer:", writer_payload("dummy", "dummy", w)["status"])
PY
```

O esperado: `plano: True None`, 4 personas com URLs, ao menos uma rodada legível em
`AUDITORIA.md` e `writer: concluido`.

## Nota de integração (pin 0.19.0)

`app/core/hermes_planner.py` monta `hermes -p <perfil> -z <prompt> --in <workspace>`.
O binário 0.19.0 **não tem** a flag `--in` (o `cwd` do processo já é o workspace):
sem remover essa flag o planner sai com erro de argparse antes de rodar. Ajuste o
argv em `hermes_planner.py` ou o pin de versão antes do deploy.
