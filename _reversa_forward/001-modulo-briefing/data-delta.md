# Data delta — 001-modulo-briefing

## Base existente

- `Research` (`app/models/domain_models.py:31–42`): `id UUID`, `theme String(500)`, `callback_url`, `status`, `briefing_draft JSON`, `error`, `approved_at`, `created_at`, `updated_at`.
- `ResearchPoint` (`:45–57`): `id UUID`, `research_id`, `position`, `title`, `description`, `dependencies`, `is_parallelizable`, `status`, `attempt_count`, `audit`.
- `ResearchStatus`: estados misturam scouting/aprovação/execução (`scouting`, `pending_approval`, `revising`, `approved`, `in_progress`, `completed`, `blocked`, `failed`, `interrupted`).

## Decisão Arquitetural: Entidade Isolada (F-03 / 2026-10-11)

- **Decisão:** o módulo `app/briefing/` utiliza entidade de briefing ISOLADA, sem herdar `Research`, `ResearchPoint` ou `ResearchStatus`. Reutilização futura limitada à infraestrutura compartilhada (sessão DB, autenticação), não às entidades de pesquisa.
- **Justificativa:** `ResearchStatus` do legado mistura estados de briefing (`scouting`, `pending_approval`) com estados de execução (`in_progress`, `completed`, `blocked`) e `ResearchPoint` carrega campos de execução (`attempt_count`, `audit`). Reaproveitar não seria inevitavelmente violação de requisito, mas a entidade isolada minimiza risco e acoplamento: evita depender de um modelo cuja decomposição (tema até 500, exatamente 5 pontos, agendamento de pesquisa via `schedule()`) precisaria ser revertida para atender aos limites aprovados (tema 3–300, pontos 3–7) e ao ciclo próprio.
- **Ciclo próprio:** `generating`, `draft`, `failed`, `approved`.
- **Execução separada:** esta decisão não cria modelo/storage/migration; entidade pura permanece em T007; implementação de persistência permanece em T011, sem ligação com a execução de pesquisa.

## Proposta

| Mudança | Tipo | Detalhe |
|---|---|---|
| Entidade briefing | Nova | Entidade briefing isolada (decisão registrada em "Decisão Arquitetural" acima): `Briefing` próprio com ciclo `generating/draft/failed/approved`; entidade pura pertence a T007; implementação de modelo DB/storage/migration permanece para T011 |
| `theme normalized` | Novo/ajustado | Armazenar tema com 3–300 caracteres após normalização; rejeitar fora do intervalo antes de chamadas externas |
| `state lifecycle` | Novo/ajustado | `generating`, `draft`, `failed`, `approved`; reabertura retorna `approved → draft`; editar aprovado proibido |
| `points[]` | Novo/ajustado | Cada item com `title`, `description`, opcional `position`/`dependencies`; geração, edição salva e aprovação exigem 3–7 itens; geração visa habitualmente 5, variando quando necessário; versão salva consultável |
| `search evidence` | Nova | Registrar identificador/consulta SERP, resultado normalizado mínimo, horário e tentativas; não armazenar respostas brutas desnecessárias nem chaves |
| `prompt provenance` | Nova | Registrar nome/versão/hash do arquivo de prompt usado; obter instrução do arquivo em tempo de execução; jamais persistir segredos ou conteúdo sensível integral |
| `revision/version` | Nova | Persistir edições e reabertura com nova versão consultável; não impor limite 1–10 não aprovado |
| `error` | Ajustado | Erro seguro persistido no registro; sem segredos; falha externa não cria briefing válido |
| `approval metadata` | Nova | Operador/timestamp/versão aprovada; leitura para etapa posterior retorna apenas conteúdo aprovado |
| `point research linkage` | Nenhuma nesta feature | Não ligar briefing a execução/relatório; investigação permanece fora |

## Migração

Necessária apenas se criar nova tabela/campo. Alterações em migrações legadas existentes não devem ser feitas por edição direta; usar migration aditiva compatível com async SQLAlchemy/Postgres e SQLite conforme `requirements.txt`. Verificação de migração fora do escopo da fase plan/to-do.

## Contrato local puro T004/T005/T007 — adendo 2026-10-11

Este adendo concretiza somente o domínio em memória e os testes locais. Mantém a decisão de entidade isolada: `Briefing` não herda nem referencia `Research`, `ResearchPoint` ou `ResearchStatus`. `app/briefing/domain.py` permanece stdlib, sem DB, HTTP, rede, prompt, agente ou I/O; reutiliza `validate_theme`, `validate_points`, `assert_can_edit`, `transition`, `BriefingStatus`, `InvalidContent` e `InvalidTransition` sem refatorá-los por preferência.

### Forma mínima proposta para o registro

- `Briefing`: dataclass stdlib `frozen=True`, campos `id: UUID`, `theme: str`, `status: BriefingStatus`, `points: tuple[BriefingPoint, ...]`, `version: int`, `approved_at: datetime | None`, `error: str | None`. `BriefingPoint`: dataclass stdlib congelada com `title: str`, `description: str`. Tipos técnicos são proposta; `id` estável identifica registro, `version` começa em 1 e aumenta em cada alteração de conteúdo/estado, inclusive fail, approve e reopen. Conteúdo imutável/tupla evita alias mutável; funções criam novo valor.
- `new_briefing(theme: str) -> Briefing`: valida/normaliza por `validate_theme` antes de qualquer operação externa, usa UUID4, estado `GENERATING`, pontos vazios, versão 1 e metadados nulos.
- `complete_briefing(briefing: Briefing, points: Sequence[BriefingPoint | Mapping[str, object]]) -> Briefing`: aceita apenas `GENERATING`, aplica `validate_points` (3–7, title/description não vazios), retorna mesmo `id`, `DRAFT`, conteúdo copiado e versão incrementada; erro não altera objeto de entrada.
- `fail_briefing(briefing: Briefing, error: str) -> Briefing`: aceita somente `GENERATING`, retorna mesmo `id`, `FAILED`, sem pontos e com mensagem segura fornecida pelo chamador; versão incrementada. Não define política de recuperação automática.
- `edit_briefing(briefing: Briefing, points: Sequence[BriefingPoint | Mapping[str, object]]) -> Briefing`: usa `assert_can_edit`; valida e copia a lista toda antes de retornar `DRAFT` com versão incrementada. Invalidez lança `InvalidContent`; estado incompatível lança `InvalidTransition`; registro anterior mantém identidade e conteúdo intactos. Sem teto de edições.
- `approve_briefing(briefing: Briefing, approved_at: datetime) -> Briefing`: valida conteúdo existente, transita somente `DRAFT → APPROVED`, registra instante recebido pelo chamador e incrementa versão. Timestamp é parâmetro técnico, não relógio/I/O interno.
- `reopen_briefing(briefing: Briefing) -> Briefing`: somente `APPROVED → DRAFT`, limpa `approved_at`, incrementa versão; sem condição baseada em pesquisa.
- `read_approved(briefing: Briefing) -> Briefing`: devolve snapshot isolado apenas em `APPROVED`; caso contrário `InvalidTransition`. Não consulta nem persiste.

Ponte de entrada (A002): `complete_briefing`/`edit_briefing` aceitam `Sequence` como lista ou tupla, mas recusam `str`, `bytes` e entradas que não sejam sequências com `InvalidContent`. Criar lista nova; para cada `Mapping` (inclusive não-`dict`), extrair `title` e `description` por chaves para um `dict` novo; manter `BriefingPoint` para validação por atributos; recusar outros tipos de item com `InvalidContent`. Aplicar `validate_points` sobre essa lista e somente depois criar tupla de novos `BriefingPoint` congelados, preservando ordem e strings sem trim obrigatório. Aprovação valida uma lista derivada da tupla do snapshot. Não ampliar nem refatorar o contrato do helper auditado. Testar lista, tupla, Mapping não-dict, tipos inválidos e isolamento da entrada mutável.

Esses nomes/assinaturas formam contrato proposto para leitores escreverem testes T007 sem adivinhar API. Exceções existentes são suficientes; sem novas classes ou abstrações. A implementação pode ajustar detalhe de tipagem mantendo comportamento e símbolos, sujeito à auditoria.

### Identidade, isolamento e histórico

Testar que operações mantêm `id`, produzem versão crescente e nunca mutam instância anterior. Editar a partir de lista/dicts mutáveis, mutar a entrada depois e tentar alterar snapshot retornado não pode contaminar versão anterior ou seguinte. `read_approved` deve retornar snapshot equivalente e isolado. Histórico local é sequência de snapshots que o chamador pode manter; política de retenção não definida. Isso não satisfaz por si só requisito de versão salva consultável: persistência durável, consulta histórica, atomicidade transacional, concorrência e idempotência ficam para T011 e design de storage. Não inferir aprovação persistida de contrato puramente funcional.

### Gates e classificação

- T004 — gate local: schema e `new_briefing`/`validate_theme`, fronteiras 2/3/300/301 e strip, sem spy de I/O em função pura. Gate integrado separado: T010 deve invocar serviço real com SERP/LLM substituídos por fakes e provar zero chamadas para tema rejeitado. T004 permanece aberta até esse gate.
- T005 — gate local parcial: ciclo em memória, rejeição de edição aprovado, limites 3/7, atomicidade, ordem, identidade, cópia/isolamento e read-approved. RF-05 exige versão salva consultável; marcar ação como concluída somente após integração durável/consulta verificável em T011.
- T007 — gate local: operações puras e matriz de transições/regras abaixo. Não inclui schema DB, migration, serviço ou persistência.

| Comportamento | Teste executável proposto | Fase/gate |
|---|---|---|
| Tema | `validate_theme`: strip; lengths 2/3/300/301; inválido lança `InvalidContent` | Local T004 PASS possível; ordem antes de I/O requer T010 |
| Quantidade/conteúdo | gerar, editar e aprovar 2/3/7/8 itens; title/description whitespace, ausente ou tipo inválido; sem trim obrigatório dos pontos | Local T005/T007 |
| Estado | gerar `GENERATING`; completar para `DRAFT`; falhar para `FAILED`; editar apenas draft; aprovar; bloquear edição aprovado; reabrir para draft; failed sem conteúdo válido | Local T007 |
| Atomicidade | edição inválida e transição inválida preservam snapshot anterior integralmente | Local T005/T007 |
| Identidade/versão | mesmo UUID; versão inicial 1, cada operação aceita incrementa uma vez, recusada não incrementa | Local T007 |
| Isolamento | mutações na lista/dicts de entrada e em snapshots/read não alteram instâncias anteriores ou conteúdo interno | Local T005/T007 |
| Read-approved | approved retorna snapshot isolado; demais estados lançam `InvalidTransition` | Local T005/T007; consulta durável permanece T011 |

### Storage futuro (não decidido neste recorte)

T011 define e verifica formato persistido, histórico consultável, migração, transação, concorrência, idempotência, retenção e consulta read-only aprovada. T007 não pode ser reportada como persistência implementada. As opções de tabela/JSON e migration permanecem abertas; migrações legadas não devem ser editadas diretamente. Nenhum schema de DB foi escolhido neste adendo.

## Contrato de geração T006/T010 — adendo 2026-10-11

Dados vivos somente durante `generate_briefing` (variáveis locais em memória, zero escrita durável; detalhe de ordem/erros no adendo T006/T010 do `roadmap.md`):

| Dado | Vida | Conteúdo | Destino |
|---|---|---|---|
| `serp_results` | duração da chamada | lista de dicts `{"title","url","description"}` retornada por `JinaSerpClient.search` | reusada nas retentativas LLM sem nova busca; descartada ao fim. Evidência de busca durável (consulta, horário, tentativas) permanece decisão de storage em T011; nada disto é persistido aqui |
| payload LLM | por tentativa | `system` = instrução do arquivo de prompt; `user` = JSON `{"tema", "resultados_serp", "formato_saida"}` (contexto SERP estruturado + instrução de saída JSON, A003) | agente usa somente esse contexto (RN-02); saída bruta do LLM descartada após parse |
| pontos validados | pós-parse | tupla `BriefingPoint` (`title`/`description`) | entra em `Briefing.points` via `complete_briefing` (3–7, título/descrição não vazios) |
| erro de falha | no registro | mensagem fixa segura (prompt indisponível / busca indisponível / geração indisponível) | `Briefing.error` via `fail_briefing`; sem corpo bruto, credenciais ou conteúdo de prompt |

Nenhum campo novo — sem clock, sem timestamps de geração, sem contadores de tentativa persistidos; nenhum consumidor definido. `version` continua incrementando somente pelas operações de domínio. Este adendo não altera a decisão de entidade isolada (F-03), não antecipa schema de DB e não cria storage: persistência, histórico consultável, binding LLM real (sub-passo de T011, A001), transação e concorrência cross-process permanecem T011.

## Entradas de configuração do binding LLM real (A001) — adendo 2026-10-11

T011 ligará `llm_complete` real em `generate_briefing`. Fronteira de dados/configuração deste binding:

| Entrada | Origem | Regra |
|---|---|---|
| role de LLM | `app/schemas/__init__.py:5` `ROLES` existente | reutilizar UMA role existente, candidata registrada `scout`; escolha nomeada explicitamente na execução de T011; role `briefing` inexistente; não criar role nova implícita nem credencial |
| modelo/chave | `app/services/settings.py:273,289` `runtime_settings`/`get_record` (resolução por role/provider) | sem persistir chave; segredo nunca em `Briefing`, erro ou log |
| timeout por tentativa | parâmetro `llm_timeout_s` do serviço (default 30s) | mesmo valor configurado repassado ao provider; default 30s, finito positivo, sem teto fixo adicional |
| tentativas | teto 4 totais imposto pelo serviço (inicial + 3) | binding one-attempt SEM retry/fallback/backoff interno; retry aninhado de provider é violação de RF-10 |
| `system` | loader de prompt (T008) | string não-vazia após strip validada no serviço (A004); preservada integralmente |
| `user` | serviço monta JSON `{"tema", "resultados_serp", "formato_saida"}` | instrução de saída lista JSON explícita (A003); tema normalizado; somente `title`/`url`/`description` da SERP |
| saída | texto do provider | parse stdlib no serviço: JSON puro ou cerca `json` única opcional, lista integral exigida; saída bruta descartada, nunca persistida |

Gate de QA associado (T012, fecha somente com binding real): uma chamada externa ativa por tentativa, teto de 4 sem retry aninhado, timeout acordado aplicado, erro seguro sem segredos/payload bruto, `DRAFT` 3–7 pontos via provider real. T011 não pode ser fechada com fake no lugar do binding.
