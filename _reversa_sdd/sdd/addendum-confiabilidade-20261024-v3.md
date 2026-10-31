# Adendo de confiabilidade v3 — simplicidade e entregas sequenciais

Data: 24/10/2026. Fonte: orientações explícitas do usuário nesta conversa. Preserva os adendos anteriores e as especificações originais; prevalece somente nos pontos abaixo.

## Primeira entrega: Plan

A implementação concentra-se exclusivamente em Plan e nas dependências que ele realmente usa. Search, Audit e Writer serão tratados sequencialmente após a aceitação da etapa anterior. Isso não reduz o backlog DR-001 a DR-015 nem o objetivo final de uma pesquisa completa avaliada pelos 12 critérios.

Gemini 3.8 Flash High no Antigravity implementa. Sonnet 5.5 no Antigravity arbitra a conformidade e a qualidade da entrega. Se o limite do Sonnet acabar, uma sessão nova e independente do Gemini poderá arbitrar. Somente um agente externo ativo por vez.

Plan é entregável quando seu código e suas dependências necessárias forem aprovados, os testes da revisão aprovada passarem e uma chamada HTTP real local com um ponto produzir um plano profissional, persistido corretamente, aceito pelo árbitro. Testes com mocks não comprovam a qualidade do plano real.

## Simplicidade obrigatória

Cada estrutura de produção precisa atender a um comportamento necessário e verificável. Evitar infraestrutura antecipada, caminhos duplicados e regras específicas de um assunto para simular entendimento semântico genérico.

As entidades citadas na seção 2.4 do adendo v2 representam necessidades de informação e rastreabilidade. **Não obrigam a criação de uma tabela separada por entidade.** Evidência, afirmações, ações, auditorias e versões de documentos continuam sendo requisitos para suas respectivas etapas, mas podem usar estruturas existentes e JSON estruturado quando isso for mais simples e suficiente.

Na entrega Plan, manter a pesquisa, seus pontos, o plano estruturado e as tentativas reais de geração/avaliação em persistência atômica. Retirar do código ainda não entregue as cinco tabelas e métodos antecipados sem integração nos fluxos. Não executar DROP nem apagar dados de bancos existentes.

Validação local garante forma, campos obrigatórios, quantidade e duplicatas literais. Avaliação semântica estruturada verifica intenção, público, formato, temporalidade e redundância entre eixos (instruindo explicitamente no prompt do avaliador a cobertura exaustiva de todos os $N(N-1)/2$ pares canônicos `1 <= eixo_1 < eixo_2 <= N` em `sobreposicao_eixos` para `N > 1`, ou `[]` para `N = 1`). Não exigir catálogos de assuntos/públicos ou regras de sinônimos para satisfazer esses requisitos.

Falhas honestas, preservação do histórico, separação entre conteúdo e reasoning, telemetria sem custos inventados e migrações aditivas idempotentes permanecem obrigatórias. A simplicidade não permite enfraquecer esses comportamentos.
