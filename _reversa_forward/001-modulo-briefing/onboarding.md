# Onboarding — 001-modulo-briefing

## Pré-requisitos

- Acesso somente leitura aos requisitos e planos em `_reversa_forward/001-modulo-briefing/`.
- Sem credenciais externas e sem instalação/execução de dependências nesta fase.
- Investigação/pesquisa completa fora do escopo.

## Leitura na ordem

1. `requirements.md` — ciclo geração/edição/aprovação/reabertura, tool exclusiva Jina e limites.
2. `roadmap.md` — abordagem, conflitos de comportamento legado e bloqueio Google/Jina.
3. `investigation.md` — evidência de código/linhas e verificação oficial necessária.
4. `data-delta.md` — proposta de estado e histórico editável.
5. `interfaces/briefing-http.md` — contrato backend proposto.
6. `actions.md` após `/reversa-to-do` — ordem de execução, dependências e paralelismo.

## Validação manual futura

1. Solicitar briefing com tema válido e confirmar geração com 3–7 pontos; conferir orientação de 5 como alvo habitual no prompt.
2. Inspecionar que adapter contém apenas tool SERP Jina e que nenhuma leitura de páginas ocorre.
3. Editar rascunho com 3–7 pontos e confirmar versão consultável; tentar salvar 2 ou 8 pontos e confirmar rejeição sem perda da versão anterior.
4. Aprovar briefing com 3–7 pontos e confirmar bloqueio de edição; confirmar rejeição de aprovação fora do intervalo.
5. Reabrir e confirmar nova edição.
6. Simular falha SERP/LLM e confirmar quatro tentativas, mesma identidade do registro, reutilização SERP após erro LLM e mensagem segura.
7. Remover/renomear prompt e confirmar falha de configuração sem chamar agente.
8. Consultar briefing aprovado como consumidor posterior sem disparar pesquisa.
