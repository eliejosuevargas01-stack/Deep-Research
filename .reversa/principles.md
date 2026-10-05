# Princípios Arquiteturais e Diretrizes: Deep Research Engine

> Gerado por Reversa Framework  
> Data: 2026-10-04  
> Mantido por: `/reversa-principles`

## Princípios Ativos

### I. Rastreabilidade Factual Estrita (Verbatim Citation)
**Descrição.** Nenhuma afirmação ou dado numérico pode ser apresentado no relatório final ou aceito pela auditoria sem que exista uma citação exata (*verbatim*) correspondente ao conteúdo extraído da fonte original. Links e URLs representam apenas acessibilidade, não veracidade.

**Exemplo de aplicação.** Se o worker afirma que a NVIDIA lançou uma GPU com 288GB de memória, o texto da citação deve conter esse dado explícito no trecho coletado. Caso contrário, o Auditor emite `RETRY` com instrução concreta ou registra ressalva de incerteza.

---

### II. Defesa de Privacidade e Isolamento de Prompts
**Descrição.** Nenhum segredo, chave de API, prompt de sistema ou cadeia de pensamento bruto (*chain-of-thought*) pode vazar para logs públicos, eventos de SSE, respostas de API ou banco de dados. Entradas de usuários e dados externos coletados da web são tratados estritamente como dados não confiáveis (*untrusted data*).

**Exemplo de aplicação.** Prompts são delimitados por `<untrusted_user_input>` e `<untrusted_external_content>` com instruções estritas para o modelo não executar comandos contidos nas fontes raspadas.

---

### III. Resiliência por Degradação Graciosa e Limites Rígidos
**Descrição.** Falhas em serviços externos (APIs de busca, webhooks de callback ou modelos de IA) ou esgotamento de retries de auditoria nunca devem causar travamento silencioso ou perda do relatório. O sistema degrada graciosamente (ex.: fallback para busca alternativa, marcação de ponto como `blocked` com ressalvas, retry posterior de webhook).

**Exemplo de aplicação.** Se o Auditor reprovar um ponto por 4 tentativas consecutivas, o ponto é marcado como `blocked` e o Redator gera o relatório final com um capítulo dedicado às ressalvas e incertezas desse ponto.

---

### IV. Concorrência Segura e Idempotência
**Descrição.** A concorrência máxima do sistema é limitada por semáforo de aplicação (`Semaphore(20)`), os estados de transição são persistidos no banco de dados antes da execução e a escrita concorrente de evidências utiliza controle otimista de versão (`version_id_col`).
