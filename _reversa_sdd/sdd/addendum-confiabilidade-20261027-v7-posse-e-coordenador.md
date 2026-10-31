# Adendo v7 — Autenticação de Posse CAS, Fechamento de ReadingCoordinator e Limites de Armazenamento

Data: 27/10/2026. Autoridade: Reauditoria FIX de Confiabilidade Concorrente.
Complementa os adendos v4 (Search), v5 (Audit) e v6 (Writer) e o backlog DR-001 a DR-015.
Preserva integralmente as especificações originais e estabelece os deltas normativos abaixo.

---

## 1. Autenticação de Posse CAS com Entropia Forte e Invariantes de Armazenamento

### 1.1 Problema Identificado
Anteriormente, Searcher e Auditor utilizavam `datetime.now(timezone.utc).isoformat()` como token de posse de lease em `atualizado_em`. Essa abordagem possuía três falhas críticas:
1. **Colisão de Timestamp:** Dois trabalhadores concorrentes disparados no mesmo instante (ou com relógios simulados/mockados) geravam o mesmo token candidato.
2. **Liberação Indevida por Trabalhador Rejeitado:** Ao falhar na aquisição da reserva (`CONCURRENT_EXECUTION` ou `MAX_ATTEMPTS_EXCEEDED`), o trabalhador rejeitado caía no bloco `except`, onde a expressão `effective_token = reserved_token or candidate_token` utilizava o candidato. Havendo colisão de timestamp, o trabalhador que NUNCA adquiriu a posse chamava `release_point_reservation` ou `release_point_audit_reservation` e revogava a posse legítima do trabalhador dono.
3. **Corrupção da Semântica de Data:** Armazenar tokens arbitrários em `atualizado_em` destrói a ordenação cronológica lexicográfica necessária para verificação de expiração de lease (`Ponto.atualizado_em < lease_cutoff`), além de colidir com restrições de tamanho de coluna.

### 1.2 Regras Normativas de Posse CAS
1. **Entropia Forte Exclusiva:** O token de lease (`lease_token`) DEVE ser gerado com entropia criptográfica forte (UUID4 hexadecimal de 32 caracteres) no início da tentativa de reserva de cada trabalhador.
2. **Coluna Dedicada no Armazenamento:** A tabela `pontos` recebe a coluna `lease_token VARCHAR(64) NULL` via migração aditiva idempotente. A coluna `atualizado_em` é preservada exclusivamente para timestamps cronológicos ISO 8601 UTC.
3. **Semântica Estrita de Timestamp e Harmonização Geral:** Todos os campos de timestamp (`pesquisa.criado_em`, `pesquisa.concluido_em`, `pontos.criado_em`, `pontos.atualizado_em`, `conteudo_coletado.criado_em`, `credenciais.atualizado_em`, `generation_attempts.criado_em`) e cutoffs de lease devem registrar datas no formato ISO 8601 UTC com precisão de microssegundos no formato `%Y-%m-%dT%H:%M:%S.%fZ` (estritamente 27 caracteres), garantindo compatibilidade integral com `VARCHAR(30)` em qualquer dialeto relacional e preservando comparações lexicográficas (`< lease_cutoff`). Registros legados no banco são normalizados por rotina aditiva idempotente convertendo offsets de timezone para UTC canônico.
4. **Isolamento de Concorrente Rejeitado:** Se a reserva atômica falhar por concorrência (`CONCURRENT_EXECUTION`) ou limite de tentativas (`MAX_ATTEMPTS_EXCEEDED`), o trabalhador REJEITADO NUNCA deve acionar métodos de liberação de posse (`release_point_reservation` ou `release_point_audit_reservation`).
5. **Preservação de Propriedade sob Cancelamento durante Reserva:** Caso ocorra cancelamento (`CancelledError`) durante o commit da reserva ou refresh em `reserve_point` / `reserve_point_for_audit`:
   - O commit é executado com sincronização segura via `_shield_and_wait` no repositório, garantindo conclusão efetiva da transação sem deixar commits órfãos em background após o fechamento da sessão.
   - Caso o commit tenha sido persistido no banco com o token do trabalhador, mas a corrotina seja cancelada antes de atribuir a variável de retorno no caller (`reserved_token` ou `token_audit`), o manipulador de erro utiliza o token UUID candidato (`token_search_candidate` ou `token_audit_candidate`).
   - Como o token candidato é um UUID4 único gerado localmente, a liberação CAS atômica (`WHERE ponto_id = :ponto_id AND (lease_token = :expected_token ...)`) libera com segurança a posse se o commit sobreviveu no banco, e afeta 0 linhas se a reserva não foi efetivada, sendo matematicamente impossível liberar reserva alheia.
6. **Invariante CAS de Finalização e Validação de Posse em `save_collected_content`:**
   - `save_collected_content` aceita `expected_token: Optional[str] = None`.
   - Se `expected_token` for informado, valida atomicamente:
     `WHERE ponto_id = :ponto_id AND (lease_token = :expected_token OR (lease_token IS NULL AND atualizado_em = :expected_token))`
   - Se `expected_token` for omitido (chamada legada ou sem lease prévia), impede a finalização se o registro no banco possuir `lease_token` ativo não nulo pertencente a outro trabalhador concorrente, garantindo integridade contra sobreposição de coletas na mesma tentativa.

---

## 2. Ciclo de Vida e Fechamento Ordenado de `ReadingCoordinator`

### 2.1 Problema Identificado
O método `ReadingCoordinator.close()` cancelava e aguardava tarefas pendentes em `_all_tasks`, mas não fechava a rota de entrada `fetch_url()`. Consequentemente:
1. Novas requisições podiam ser despachadas enquanto `close()` drenava as tarefas ou após a sua conclusão.
2. Chamadas após o fechamento criavam novas tarefas de rede assíncronas órfãs.
3. Não havia garantia de rejeição determinística nem idempotência no fechamento.

### 2.2 Regras Normativas do `ReadingCoordinator`
1. **Estado Explícito de Fechamento:** `ReadingCoordinator` deve manter a flag booleana `_closed: bool = False`.
2. **Rejeição Imediata de Novas Buscas:** Qualquer chamada a `fetch_url()` efetuada com `_closed == True` deve ser imediatamente rejeitada com `RuntimeError("ReadingCoordinator fechado")`, sem acionar a fábrica de corrotinas `fetch_coro_fn` e sem criar tarefas em `in_flight` ou `_all_tasks`.
3. **Bloqueio de Novas Tarefas durante o Drenamento:** A ativação de `self._closed = True` ocorre no início de `close()` sob o lock interno, impedindo que novas tarefas ingressem no coordenador enquanto as tarefas em andamento são canceladas e aguardadas.
4. **Coexistência e Desacoplamento de Consumidores:** Múltiplos consumidores aguardando a mesma leitura compartilham a mesma tarefa in-flight via refcount. O cancelamento de um consumidor não afeta os demais; porém, a invocação de `close()` cancela a tarefa subjacente e todos os consumidores são liberados limpos.
5. **Idempotência e Blindagem de `close()`:** Múltiplas chamadas a `close()` são estritamente idempotentes. Se a tarefa que invocou `close()` sofrer cancelamento externo, o drenamento das tarefas pendentes é blindado (`asyncio.shield`), garantindo que nenhum recurso de rede ou tarefa de leitura permaneça órfã.

---

## 3. Relatório Honesto de Suporte a Banco de Dados e Limites de `VARCHAR(30)`

1. **Infraestrutura Real Disponível (Evidência Empírica):**
   - O ambiente de execução e testes opera exclusivamente sobre SQLite com WAL via `aiosqlite`.
   - Teste de importação de drivers relacionais externos no ambiente virtual ativo (`.venv/bin/python`):
     - `asyncpg`: NÃO instalado (`ModuleNotFoundError`).
     - `psycopg2`: NÃO instalado (`ModuleNotFoundError`).
     - `psycopg` (v3): NÃO instalado (`ModuleNotFoundError`).
   - Não há container ou instância de PostgreSQL ativa no host.
   - **Risco Arquitetural Documentado:** O sistema é estritamente SQLite-centric. O suporte a PostgreSQL limita-se à compatibilidade declarativa do esquema DDL no compilador SQLAlchemy (`compile(dialect=postgresql.dialect())`). Qualquer tentativa de implantar o backend apontando `DATABASE_URL` para PostgreSQL falhará no boot por ausência de driver e dialeto assíncrono.
2. **Diagnóstico Honesto de `VARCHAR(30)` e Harmonização de Timestamps:**
   - Em PostgreSQL real com validação estrita de tamanho, `datetime.now(timezone.utc).isoformat()` gera strings de 32 caracteres (`YYYY-MM-DDTHH:MM:SS.mmmmmm+00:00`), violando colunas `VARCHAR(30)`.
   - SQLite não impõe rejeição em colunas `VARCHAR(30)` não estritas, mascarando o estouro de tamanho em tempo de execução.
   - **Remediação Arquitetural:** Para manter conformidade relacional universal, timestamps em todas as tabelas (`pesquisa`, `pontos`, `conteudo_coletado`, `credenciais`, `generation_attempts`) e cutoffs temporais são harmonizados no padrão ISO 8601 UTC `%Y-%m-%dT%H:%M:%S.%fZ` (estritamente 27 caracteres), que cabe rigorosamente em `VARCHAR(30)`.
   - Dados legados contendo timezone offsets (como `-03:00` ou `+00:00`) ou comprimentos divergentes são normalizados por rotina aditiva idempotente durante `init_db`.
   - Novos tokens de segurança não devem ser concatenados em colunas de data/hora: utilizam a coluna dedicada `lease_token VARCHAR(64)`.
   - Nenhuma alegação de suporte em tempo de execução a PostgreSQL deve ser realizada sem instalação prévia dos drivers e ambiente real de homologação.
