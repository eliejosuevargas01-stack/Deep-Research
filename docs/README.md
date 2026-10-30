# Documentação — Deep Research

Índice dos documentos técnicos. A porta de entrada do projeto é o [`README.md`](../README.md).

| Documento | Para quem | Conteúdo |
| :--- | :--- | :--- |
| [`html/index.html`](html/index.html) | Todos | Versão HTML navegável, com busca, sumário lateral e tema claro/escuro |
| [`../README.md`](../README.md) | Todos | Visão geral, início rápido, stack, API resumida, limitações |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Engenharia | Componentes, fluxo por etapa, modelo de dados, concorrência, SSE, segurança |
| [`API.md`](API.md) | Integradores | Contratos HTTP, payloads, erros, eventos SSE, webhook |
| [`OPERATIONS.md`](OPERATIONS.md) | DevOps / operação | Variáveis, execução, banco, testes, diagnóstico, segurança |
| [`frontend/`](frontend/) | Frontend / QA | Auditorias, evidências visuais e relatórios de remediação |
| [`security_audit_findings.md`](security_audit_findings.md) | Segurança | Achados e itens de remediação |

## Especificações de origem

- [`../PRODUCT.md`](../PRODUCT.md) — propósito, usuários, restrições e princípios
- [`../DESIGN.md`](../DESIGN.md) — sistema visual
- [`../_reversa_sdd/prd.md`](../_reversa_sdd/prd.md) — PRD e invariantes
- [`../_reversa_sdd/sdd/`](../_reversa_sdd/sdd/) — SDD por endpoint e adendos de confiabilidade
- [`../_reversa_sdd/personas.md`](../_reversa_sdd/personas.md) — personas de usuário e do sistema
- [`../_reversa_sdd/traceability/bugs.md`](../_reversa_sdd/traceability/bugs.md) — rastreabilidade de bugs resolvidos

## Convenções

- Documentação em português; identificadores de código, variáveis e rotas permanecem no original.
- Comandos assumem o diretório `Deep-Research/` e o virtualenv `.venv` ativo.
- Payloads são exemplos ilustrativos; campos obrigatórios e limites estão nas tabelas de [`API.md`](API.md).
