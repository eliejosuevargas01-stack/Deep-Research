# Protocolo de aceitação da correção integral

Estado: pendente de implementação e verificação. Este documento é um plano, não um relatório de aprovação.

As nove críticas C01–C09 e os gates G01–G06 em `.impeccable/remediation-20261026/requirements.json` são bloqueantes. A avaliação antiga de checkpoint1 não aprova esta correção. A mudança da direção monocromática para violeta/índigo foi solicitada explicitamente pelo usuário. Delegação de implementação e avaliação exclusivamente por Hermes CLI, modelo ag/gemini-3.8-flash-high, reasoning high; subagentes nativos são proibidos.

## Duas classes de evidência

1. **Execução real:** mesma aplicação compilada servida pelo FastAPI, sessão real sem chave manual, SQLite de aceitação isolado, modelos e adaptador de busca configurados de verdade. `capture_app.py` apenas observa ASGI e registra payloads sanitizados. A chamada precisa passar pelos validadores e pelo writer real. Qualquer erro é registrado; não se substitui resultado por fixture para concluir este gate.
2. **Regressão determinística:** aplicação e autenticação reais, apenas provedores externos simulados. `serve_acceptance_app.py` viabiliza payloads reproduzíveis e erros. Não equivale à execução real. Preferências variáveis são geradas pela fixture externa; o planner de produção valida a contagem recebida normalmente.

Não registrar headers, cookies, chaves de provedor, HMAC, credenciais nem reasoning privado. As evidências devem citar versão/hash de código e bundle, modo do provedor, URL e limites do ensaio. Sucesso de HTTP/health não comprova interação de ponta a ponta.

## Cinco rodadas de crítica na aplicação corrigida

| Rodada | Superfície | Ações reais e provas |
|---|---|---|
| 1 | Entrada e compositor | Clicar nas sugestões, conferir foco no input, editar/Shift+Enter/Enter, limites do tema, abrir +, pontos/personas, Escape, foco e recuperação de sessão. |
| 2 | Planejamento e relatório | Conferir preferências e payload, expandir e recolher plano, única ação Iniciar pesquisa, pesquisa/auditoria/writer, erro com retomada, relatório no início, copiar/exportar. |
| 3 | Configurações | Abrir painel, distinguir vazio de falha, validação acessível, rascunho ao navegar, padrões de pontos/personas, modelos e callback. Credenciais reais não devem ser modificadas pelos testes; usar fixture isolada para gravação. |
| 4 | Histórico, documentação e navegação | Reabrir relatório, navegar sem perder contexto, nova pesquisa, links/documentação reais, controle de dados públicos no histórico e comparação com referências locais. |
| 5 | Responsividade e coerência | 375/837/1440, teclado, zoom, áreas de toque, foco, contraste, fontes efetivamente carregadas, GSAP normal/reduzido e transições interrompidas. |

Cada rodada tem avaliação A de design e avaliação B de detector/evidência independentes via Hermes. A não vê saída do detector antes de concluir. A orquestração só sintetiza após ambas concluídas, com origem declarada. O navegador nativo pode coletar cliques/evidências para os workers; não serão criados subagentes nativos. A indisponibilidade de overlay em evaluate somente leitura deve ser registrada, sem injetar scripts por outro caminho. A nota heurística é honesta e não será forçada a 40/40; a aprovação exige critérios de aceitação verificados e ausência de defeitos bloqueantes, sem transformar opinião estética em percentual comprovado.

## Ordem de entrega

Implementação Hermes -> conferência de integração e coleta real -> cinco críticas independentes e correções -> auditor Hermes independente de todos os requisitos com hashes atuais -> Cucumber visual pós-aprovação -> corrigir/revisar/retestar se houver falha -> entrega com endereço funcional, comando único e evidências. Nenhum deploy externo é necessário. SSE continua reservado ao checkpoint2.
