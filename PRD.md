# PRD — Hermes Deep Research Pipeline

**Versão:** 1.3  
**Data:** 2026-11-07  
**Status:** Aprovado para Implementação  
**Core Engine:** Hermes isolado em container dedicado (`engine/`, imagem `nousresearch/hermes-agent:latest`) + backend `api` + frontend `v12/`

---

## 1. Objetivo do Produto

Construir um pipeline automatizado, isolado e auditável de pesquisa profunda onde o **Hermes é o único motor de execução agêntica**, pesquisa web e delegação de subagentes. O sistema investiga qualquer tema em múltiplos níveis de profundidade (1 a 10 pontos simultâneos), utilizando varredura exploratória inicial pelo Planner, coleta paralela em 4 perspectivas cognitivas (`historiador`, `cetico`, `visionario` e `futurista` — até **40 subagentes simultâneos** por rodada), validação rigorosa por checklist booleano (`auditor` de 12 perguntas) e síntese exaustiva (`redator`) sem perda factual entre rodadas.

O Hermes executa em **container isolado** (`engine`, porta interna 8100, nunca exposta ao público). O backend (`api`, porta pública 8000) nunca chama LLM diretamente: monta prompts a partir do banco, despacha lotes ao engine via `POST /run` e persiste artefatos, eventos SSE, histórico e telemetria. A interface web é servida pelo container `web` (nginx, porta pública **8080**) com proxy same-origin para `/research`, `/config`, `/health` e SSE.

### Princípios Arquiteturais Inegociáveis

1. **Zero Chamadas Diretas a APIs Externas pelo Backend:** o backend auxiliar **não** faz chamadas HTTP diretas a provedores de LLM (`/chat/completions`) nem a serviços externos de busca. O backend chama **unicamente o engine Hermes** (`DR_ENGINE_URL`) e acompanha sua execução, persistindo artefatos, histórico, eventos e telemetria no banco de dados.
2. **Hermes Faz Todo o Trabalho Pesado:** toda busca na web (`web_search`), abertura e extração de páginas (`web_extract`), raciocínio, orquestração e delegação de subagentes (`delegate_task`) ocorrem integralmente no runtime do Hermes isolado.
3. **Sem Limite Artificial de 3 Pontos Paralelos (`max_concurrent_children: 40`):** todos os `N` pontos do plano (`1..10`) rodam em paralelo sem trava de 3 pontos. Na fase de busca, o Hermes pode despachar até **40 subagentes simultâneos** (`10 pontos × 4 personas`) por rodada, com `max_concurrent_children: 40`, `max_spawn_depth: 2`, `oneshot_max_children: 0`.
4. **Provedor Só via Ambiente (nunca via API):** credenciais e endpoint do provedor vivem **exclusivamente** em variáveis de ambiente (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` e overrides `LLM_MODEL_<PAPEL>`). O endpoint `PUT /config` gerencia **apenas** modelos por papel e limites de delegação; qualquer `base_url`/`api_key` não-vazio é rejeitado com **422**. Nenhum segredo é gravado em `config.yaml`, nenhum segredo trafega na API pública, nenhum segredo é commitado no repositório (exemplos usam placeholder).
5. **Isolamento Estrito por Pesquisa e por Container:** cada pesquisa executa em seu próprio workspace exclusivo (`/workspaces/{research_id}`). O processo Hermes roda com `cwd` fixado nesse diretório e o engine rejeita qualquer workspace fora de `/workspaces` (403). O engine roda como usuário `hermes`, sem acesso ao host; o banco do Hermes (`state.db`) é montado **somente-leitura** (`:ro`).
6. **Autenticação da API Pública:** com `API_KEY`/`DR_API_KEY` configurada, todas as rotas exigem `X-API-Key` ou `Bearer` (SSE aceita `?api_key=` por limitação do EventSource). `GET /health` permanece sempre aberto. Sem chave configurada, o backend fica aberto (somente dev/testes).

---

## 2. Parâmetros de Entrada do Usuário

O sistema é acionado via requisição assíncrona contendo:

- `tema` (`string`, obrigatório): assunto central da pesquisa.
- `profundidade` (`int`, 1 a 10): quantidade de pontos estruturais em que o tema será decomposto e investigado simultaneamente.
- `veracidade_alvo` (`int` ou `float`, 0 a 100): percentual mínimo de respostas `true` exigidas para aprovação de um ponto.
- `max_rodadas_auditoria` (`int`, 1 a 10, padrão 4): máximo de ciclos de busca + auditoria permitidos por ponto.
- `atualidade` (`string`): janela temporal prioritária para os dados, como `24H`, `7D`, `1Y` e `ALL`.
- `callback_url` (`string`, URL): endpoint webhook que receberá o payload final quando a pesquisa terminar.

> Convenção canônica: os campos do payload de entrada e dos contratos internos devem usar os nomes acima, sem variações.

---

## 3. Contratos Canônicos de Entrada e Saída

### 3.1. Entrada do usuário

```json
{
  "tema": "matriz energetica no Brasil.",
  "profundidade": 10,
  "veracidade_alvo": 90,
  "max_rodadas_auditoria": 4,
  "atualidade": "24H",
  "callback_url": "https://webhook.callback.com"
}
```

### 3.2. Saída do planner (após varredura exploratória inicial no Hermes)

```json
{
  "research_id": "123ABC321",
  "tema": "matriz energetica no Brasil.",
  "profundidade": 10,
  "veracidade_alvo": 90,
  "max_rodadas_auditoria": 4,
  "atualidade": "24H",
  "callback_url": "https://webhook.callback.com",
  "pontos": [
    {
      "ponto_id": 1,
      "enunciado": "Quais são as matrizes energéticas do Brasil e sua participação atual",
      "subperguntas": [
        "Qual o percentual atual de renováveis vs não-renováveis?",
        "Como se divide a geração hidráulica, térmica, eólica e solar?",
        "Quais foram as atualizações oficiais mais recentes?"
      ],
      "hipoteses": [
        "Fontes renováveis representam mais de 45% da matriz energética total.",
        "A geração solar distribuída cresceu acima da média histórica no último ciclo.",
        "Gargalos de transmissão limitam o escoamento no Nordeste."
      ],
      "lacunas_iniciais": [
        "Dados consolidados das últimas 24 horas do ONS.",
        "Impacto exato do curtailment eólico recente.",
        "Diferença metodológica entre dados da EPE e da ANEEL."
      ],
      "perguntas_auditoria": "(injetada pelo backend: 12 estáticas idênticas em todos os pontos)"
    }
  ]
}
```

> `perguntas_auditoria` NÃO vem do planner: o backend injeta as 12 ESTÁTICAS (`PERGUNTAS_AUDITORIA_ESTATICAS`) em cada ponto antes de persistir.

---

## 4. Requisitos Funcionais (RF)

### RF01 — Varredura Exploratória Inicial e Decomposição pelo Planner no Hermes
Ao iniciar a pesquisa, o agente principal **Planner** no Hermes realiza uma **busca exploratória inicial na web** (`web_search` e abertura livre das páginas necessárias via `web_extract`) com a finalidade exclusiva de levantar contexto real e atualizado sobre o tema antes de estruturar o plano. Em seguida, gera um plano contendo exatamente `N` pontos (`N = profundidade`, de 1 a 10), onde cada ponto contém obrigatoriamente:

- `ponto_id` (sequencial de `1` a `N`)
- `enunciado`
- `subperguntas` (mínimo 3)
- `hipoteses` (mínimo 3)
- `lacunas_iniciais` (mínimo 3)

O planner NÃO cria `perguntas_auditoria`: o backend injeta as 12 perguntas ESTÁTICAS universais (`PERGUNTAS_AUDITORIA_ESTATICAS`, idênticas em todos os pontos — ver README § Critérios de Auditoria) em cada ponto em `_planejar` antes de persistir.

O planner também declara `urls_lidas`/`urls_usadas` da varredura, persistidas na linha do planner em `agent_executions` e incluídas nas listas globais da consolidação.

### RF02 — Fan-Out Paralelo Multi-Persona no Hermes (Até 40 Subagentes Simultâneos)
Não há limite de 3 pontos paralelos. Para todos os `N` pontos em aberto (`1..10`), o Hermes instancia simultaneamente os 4 subagentes buscadores (`historiador`, `cetico`, `visionario`, `futurista`), alcançando até **40 subagentes simultâneos** por rodada (`max_concurrent_children: 40`), cada um realizando até `max_queries: 3` buscas na rodada e abrindo as páginas relevantes para extrair evidências densas.

### RF03 — Acúmulo Integral no Banco + Prompt Compactado sem Perda Factual
Toda informação coletada em uma rodada é salva **integralmente** no banco de dados (`agent_executions.informacao_coletada`, nunca reescrita). Quando houver retentativas (rodada 2, 3, 4), as informações anteriores nunca são descartadas:

- O subagente `auditor` da rodada `K` recebe no seu 1º prompt `informacao_coletada_acumulada = R1 + R2 + ... + RK`, além de `atualidade` e `perguntas_auditoria`.
- O subagente `redator` recebe no seu 1º prompt `informacao_coletada_acumulada_integral = R1 + R2 + ... + RN`, `urls_usadas_acumuladas` e `resultado_final_auditor`.

O conteúdo do **banco é integral (100% dos bytes)**; o conteúdo do **prompt é compactado de forma determinística** (`compactar_acumulado`: dedup de linhas exatas + remoção de ruído de navegação por lista conservadora, com proteção absoluta a linhas com dígitos, URLs, datas e inícios de citação). Números, datas, URLs e citações são preservados integralmente. As estatísticas da compactação (`compactacao{}`: `linhas_antes/depois`, `chars_antes/depois`) acompanham o payload. **Métrica corrigida na v1.3:** integridade = DB integral + prompt compactado sem perda factual, com `compactacao{}` auditável — não mais "100% dos bytes no prompt".

### RF04 — Auditoria Booleana de 12 Perguntas
O subagente `auditor` no Hermes avalia o material acumulado frente às 12 perguntas do ponto e à janela de `atualidade`, retornando estritamente um objeto JSON com o mapeamento das chaves `"1"` a `"12"` para `true` ou `false` (booleanos JSON estritos; strings `"true"`/`"false"` são rejeitadas).

### RF05 — Cálculo de Veracidade e Loop de Retentativa
O sistema avalia o retorno do auditor por ponto:

$$
\text{taxa\_aprovacao} = \left( \frac{\text{quantidade de respostas true}}{12} \right) \times 100
$$

- Se `taxa_aprovacao >= veracidade_alvo`, o ponto é aprovado e segue para o `redator`.
- Se `taxa_aprovacao < veracidade_alvo` e `tentativa_atual < max_rodadas_auditoria`, o ponto entra em nova rodada de busca no Hermes.
- Se `tentativa_atual == max_rodadas_auditoria`, as buscas são encerradas para aquele ponto e ele segue para o `redator` com o registro das perguntas que permaneceram `false` (`perguntas_nao_concluidas`).

### RF06 — Direcionamento Inteligente nas Retentativas
Na Rodada 1, o 1º prompt de cada subagente buscador recebe `tema`, `atualidade`, `ponto_enunciado`, `subperguntas`, `hipoteses` e `lacunas_iniciais`. A partir da Rodada 2, recebe também:

1. `perguntas_auditoria_pendentes`: dicionário contendo apenas as perguntas que receberam `false` na rodada anterior como alvo prioritário;
2. `urls_lidas_ignoradas`: lista acumulada de todas as `urls_lidas` daquele ponto nas rodadas anteriores para bloquear releituras (bloqueio também aplicado programaticamente no backend).

### RF07 — Redação Final e Documentação de Lacunas
O subagente `redator` no Hermes é o único responsável por escrever o relatório analítico completo do ponto (`relatorio_ponto`) e as lacunas textuais finais (`lacunas_identificadas`), citando exclusivamente URLs presentes em `urls_usadas_acumuladas` (URLs fora do conjunto são rejeitadas pelo validador). O payload do redator inclui `perguntas_nao_concluidas` e `erro_coleta` quando aplicável, para que o relatório documente explicitamente o que não foi concluído.

### RF08 — Notificação via Webhook Callback
Ao finalizar a redação de todos os `N` pontos, o sistema consolida os relatórios na ordem `1..N`, calcula as listas globais deduplicadas de URLs (`urls_usadas`, `urls_lidas`, `urls_lidas_nao_usadas`), soma a telemetria real de tokens de todas as sessões do Hermes (agente principal + subagentes), anexa a seção `## Avaliação de veracidade` com o boletim `avaliacao_pontos`, atualiza o registro principal para `COMPLETED` e dispara um POST HTTP para `callback_url` (5 tentativas com espera 1s/2s/4s/8s; repete em erro de rede e HTTP 5xx; erro 4xx encerra; esgotadas as 5, levanta erro e o status segue `COMPLETED`).

### RF09 — Provider Só via Env; `PUT /config` Só Modelos e Limites (422 para Credenciais)
O provedor LLM vive **exclusivamente** no ambiente do container engine:

- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (default = planner);
- Overrides por papel: `LLM_MODEL_PLANNER`, `LLM_MODEL_HISTORIADOR`, `LLM_MODEL_CETICO`, `LLM_MODEL_VISIONARIO`, `LLM_MODEL_FUTURISTA`, `LLM_MODEL_AUDITOR`, `LLM_MODEL_REDATOR`.

O endpoint de configuração (`GET /config` e `PUT /config`, com alias `/api/v1/settings`) lê e atualiza **somente**:

- `default_model`, `modelos_por_papel` (`planner`, `historiador`, `cetico`, `visionario`, `futurista`, `auditor`, `redator`), `max_concurrent_children`, `max_spawn_depth`, `oneshot_max_children`.

Regras rígidas:

- Qualquer `base_url`/`api_key` não-vazio no `PUT /config` é rejeitado com **422** (`"provedor vem do ambiente (LLM_BASE_URL/LLM_API_KEY)"`).
- `GET /config` nunca retorna segredo (`api_key: ""`, `provider_fonte: "env"`); `base_url` exibido vem do env, apenas informativo.
- O `config.yaml` do perfil nunca contém segredo (`provider: env`, `providers.env.key_env: LLM_API_KEY`).
- **Modelos por papel (defaults):** `planner`/`auditor`/`redator` = `ocg/deepseek-v4.1-flash`; buscadores (`historiador`/`cetico`/`visionario`/`futurista`) = `gemini/gemini-3.5-flash-lite`.
- **Removida qualquer promessa das versões anteriores de configurar credenciais via endpoint, API ou `config.yaml`.** Credencial commitada no repositório é incidente (rotacionar imediatamente).

### RF10 — SSE Persistido com Snapshot/Replay e Reload sem Perda
Cada transição relevante do pipeline gera um evento persistido em `research_events` **antes** de qualquer publicação (persist-before-publish). O endpoint `GET /research/{id}/eventos` (alias `/events`) entrega:

- **Snapshot** quando `desde=0`/sem `Last-Event-ID`: `{id: ultimo_evento_id, event: snapshot, data: run completo}` seguido do replay.
- **Replay** quando `desde>0` ou header `Last-Event-ID`: eventos com `id > base`, em ordem.
- **Heartbeat** `: ping` a cada ~15s ociosas; reconexão com `?desde=<lastEventId>` após ~2s.
- Entrega **at-least-once**: o replay pode reduplicar o que o snapshot já trouxe; o cliente **deduplica por `id`** e nunca perde estado em reload/troca de página (restaura do `id 0`).
- Tipos: `run.criado`, `run.status`, `plano.pronto`, `ponto.iniciado`, `fonte.lida`, `ponto.coletado`, `auditoria.executada`, `ponto.aprovado`, `ponto.reprovado`, `redator.iniciado`, `ponto.finalizado`, `tokens.atualizados`, `run.concluido`, `ponto.erro`, `run.falhou`.

### RF11 — Resiliência por Ponto (Nenhum Ponto Aborta a Pesquisa)
Falha é isolada por ponto/rodada/persona:

- Persona buscadora que falha não derruba as demais do ponto; ponto sem nenhum sucesso na rodada é removido do loop com evento `ponto.erro`, o run segue.
- Auditor ausente/sem saída: o ponto segue ao redator com as 12 perguntas marcadas `false`, `auditor_ausente: true`, `perguntas_nao_concluidas` e `erro_coleta` no payload.
- Limite de rodadas: redator com o melhor esforço + `perguntas_nao_concluidas`.
- Redator sem saída válida após retentativas: evento `ponto.erro`, ponto listado em `pontos_falhos`, seção de incompletude no dossiê; `FAILED` só se **zero** relatórios forem produzidos.

### RF12 — Autenticação por API Key na API Pública
Com `API_KEY` (ou `DR_API_KEY`) configurada, todas as rotas exigem `X-API-Key` ou `Authorization: Bearer <chave>`; o SSE aceita `?api_key=` (EventSource não envia headers). Chave ausente/inválida → `401`. `GET /health` é sempre aberto. Sem chave configurada, o backend opera aberto (somente dev/testes). O engine usa autenticação própria e separada (`X-Engine-Token: $ENGINE_TOKEN`), nunca exposta ao público.

---

## 5. Requisitos Não-Funcionais (RNF)

- **RNF01 — Telemetria Real do Hermes (Pai + Subagentes):** cada execução do agente principal e dos subagentes delegados no Hermes tem seu consumo real de tokens (`prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `total_tokens`), `reasoning_trace`, `tool_calls` e `latency_ms` extraídos das sessões do Hermes (`state.db` filtrado pelo `cwd`/workspace da pesquisa, montado `:ro`) e dos recibos de execução de cada subagente. Cada lote registra o agente principal que delegou em `agent_executions` com `agent_role = 'orquestrador'`. Quando o `state.db` não está acessível, o `usage.json` do processo (`--usage-file`) é gravado na linha `orquestrador`: os tokens medidos são os do delegador, não dos filhos, e nenhum valor é inventado.
- **RNF02 — Passagem por Referência e Hidratação pelo Banco:** textos longos ficam no banco de dados e são injetados diretamente no 1º prompt de cada subagente do Hermes sem sobrecarregar o contexto do orquestrador pai. O `input_prompt_payload` de cada execução é persistido para auditoria.
- **RNF03 — Isolamento de Falhas, de Workspace e de Container:** a falha de uma persona não derruba as demais do mesmo ponto; ponto incompleto não aborta a pesquisa (RF11). O processo Hermes de uma pesquisa é estritamente confinado ao diretório da pesquisa atual (`_resolver_workspace` barra 403 fora de `/workspaces`); o engine executa como usuário `hermes` em container sem publish de porta e sem mounts do host.

---

## 6. Métricas de Sucesso

1. **Integridade de contexto:** 100% dos bytes coletados nas rodadas `1..K` persistidos no banco; prompt do auditor/redator compactado sem perda factual (números, datas, URLs e citações intactos) com estatísticas `compactacao{}` auditáveis.
2. **Escala real de delegação:** capacidade de executar até 40 subagentes buscadores simultâneos (`10 pontos × 4 personas`) no Hermes sem fila artificial de 3 pontos.
3. **Eficiência de re-busca:** 0% de URLs repetidas em `urls_lidas` durante retentativas.
4. **Fidelidade de configuração e telemetria:** 100% dos subagentes rodando com o modelo configurado para o seu papel; 100% dos tokens reais (agente principal + subagentes) contabilizados no banco; zero segredos em `config.yaml`/API/git.
5. **Tempo real auditável:** 100% das transições do pipeline com evento persistido e replayável via SSE; reload do cliente sem perda de estado.
6. **Boletim oficial:** `avaliacao_pontos` presente no dossiê (`## Avaliação de veracidade`), no webhook e no `GET /research/{id}`.

---

## 7. Pendências conhecidas (não afirmar como pronto)

- **Artefato local `data/deep_research.db`:** o arquivo não é versionado (`data/` e `*.db*` no `.gitignore`); o schema canônico e o container possuem as 4 tabelas. O `conectar()` cria `research_events` via `SCHEMA IF NOT EXISTS` no próximo open RW.
- **Efetividade dos modelos leves nos buscadores em produção:** confirmada no deploy vigente via `GET /config` do engine (planner/auditor/redator `ocg/deepseek-v4.1-flash`, buscadores `gemini/gemini-3.5-flash-lite`).
- **Paridade fina SSE ↔ UI ao vivo:** corrigida na árvore atual (arrays de fonte/ponto, `tokens_execucao` como delta, refetch do GET em `run.concluido`); o contrato persistido (snapshot + replay) continua sendo a fonte de verdade e o SSE é at-least-once com dedupe por `id` no cliente.
- **Segredo legado commitado:** se qualquer cópia de `config.yaml` com `api_key` real ainda existir no histórico do git, rotacionar a chave independentemente do estado atual dos arquivos.
