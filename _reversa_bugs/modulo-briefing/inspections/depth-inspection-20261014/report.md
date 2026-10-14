# Reversa Depth Inspection — 2026-10-14

Base auditada: `582ed04abd3f03de8d38f8d162d1d945534e6b54`.

Esta inspeção consolidou 18 achados confirmados e os promoveu ao registry canônico `_reversa_bugs/<contexto>/bugs/<BUG-ID>/bug.md`, preservando os bugs #1–#3 já existentes.

## F-SET-01
`BUG-20261014-8A1C`: teste do Jina proxy referencia `payload` inexistente e não testa valores ainda não persistidos.

## F-FE-01
`BUG-20261014-2F5A`: frontend usa estados legados minúsculos enquanto o backend usa `ResearchStatus` canônico em UPPERCASE.

## F-PIPE-01
`BUG-20261014-3C9B`: pipeline pode estacionar em `SCRAPER` e depois em `AUDIT` sem consumidor.

## F-BRF-01
`BUG-20261014-5D8A`: transições de briefing DRAFT/FAILED não sincronizam `Research.status`.

## F-SET-02
`BUG-20261014-9D4E`: falha de um provedor derruba toda a listagem de modelos.

## F-PIPE-02
`BUG-20261014-1E7F`: Writer marca a pesquisa inteira como FAILED quando há ponto `blocked` apesar do relatório persistido.

## F-BRF-02
`BUG-20261014-6F2E`: contrato Sprint C8/Q14–Q16 ainda não está implementado.

## F-SEC-01
`BUG-20261014-7A3D`: bypass SSRF em IP não-global/CGNAT, proxy Jina sem validação e logging ausente.

## F-INV-01
`BUG-20261014-8B4C`: PersonaWorker mantém tools após teto, contabiliza query vazia e ignora tool inválida.

## F-SEC-02
`BUG-20261014-1C9D`: resultado de persona não passa pelo output guardrail e entrada não confiável entra no system prompt.

## F-INV-02
`BUG-20261014-2A7E`: provider resolver divergente e fallback `openai/implement` inválido.

## F-FE-02
`BUG-20261014-4E8D`: schema de status da chave Jina diverge entre backend e frontend.

## F-FE-03
`BUG-20261014-5B2C`: frontend aceita tema >300 e perde detalhe de validação 422.

## F-PIPE-03
`BUG-20261014-9A6F`: retomada pula tentativa interrompida e conflita com semântica de `attempt_count` das personas.

## F-SEC-03
`BUG-20261014-3D2A`: CORS não permite `X-API-Key` apesar de a autenticação suportar esse header.

## F-SET-03
`BUG-20261014-6C7B`: validação de timeout é silenciosa/bool e detecção de máscara descarta segredos contendo `*`.

## F-SEC-04
`BUG-20261014-7E1B`: bootstrap de ambiente não gera `API_AUTH_SECRET`.

## F-TST-01
`BUG-20261014-8F3E`: testes frontend importam `.ts` sem loader compatível e não rodam no CI.

## Regra de correção
Cada defeito deve ser corrigido através de `/reversa-debugger-fix`, respeitando `closure.policy: local-software`, com teste de regressão antes do fechamento. Issues paralelas não devem editar os mesmos arquivos.
