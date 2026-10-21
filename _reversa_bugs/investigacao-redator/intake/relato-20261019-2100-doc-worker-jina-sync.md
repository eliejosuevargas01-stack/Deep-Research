# Relato: DOC-WORKER-JINA-SYNC

> Data: 2026-10-19  
> Contexto: investigacao-redator  
> Tipo: ajuste de documentação e specs por decisão explícita do operador  
> Sprint: DOC-WORKER-JINA-SYNC

## Palavras do operador (verbatim)

> o worker não deve devolver resposta vazia, ele SEMPRE aprende algo lendo as paginas do jina, jina não devolve respostas vazias, ela SEMPRE devolve uma lista de sites já prontos para leitura, 10 sites que devem ser enviados INTEGRAMENTE ao worker, apenas passando por uma limpeza/parser antes, para evitar que lixo de cabeçalho, footer etc de sites vão para o worker o fluxo é assim: ponto 1 > worker = personalidade + ponto + tool > worker chama a tool para fazer a primeira query > tool jina faz a busca e devolve as 10 paginas integralmente em texto limpo para o worker > worker analisa e coleta qualquer informação relevante para o ponto em investigação > worker internamente decide se a informação é suficiente ou se ainda pode pesquisar mais (maximo de 3 queries) > worker devolve uma resposta estruturada de tudo oq achou relevante durante sua busca > essa informação é salva no banco > um merge para conectar a informação das 4 personas > quando todas as 4 personas devolvere uma resposta > auditor. o briefing deve ser sincrono, nunca assincrono, isso evita fazer pooling para receber o briefing, o briefing é algo rapido de ser feito e dificilmente vai dar timeout. ajuste a documentação, specs e etc para resolver esses problemas.

## Requisitos extraídos

1. **10 páginas integrais por query:** Jina deve retornar 10 resultados e seus corpos completos em texto limpo, não snippets/resumos/cortes.
2. **Limpeza/parser obrigatória:** conteúdo bruto passa por limpeza de cabeçalhos, footers, navegação, lixo HTML antes de chegar ao worker.
3. **Máximo 3 queries por persona/ponto:** worker decide internamente se precisa pesquisar mais (parada voluntária).
4. **Worker NUNCA devolve vazio:** sempre aprende algo das páginas integrais.
5. **Persistência individual antes do merge:** resultado de cada persona salvo no banco antes de consolidação.
6. **Barreira de 4 personas antes do auditor:** auditor só roda quando as 4 personas retornaram resposta para o ponto.
7. **Briefing síncrono (request/response HTTP 200):** sem 202, sem polling, sem background task para geração de briefing.
8. **Fluxo canônico:** persona+ponto+tool > tool chama Jina > Jina devolve 10 páginas integrais > worker analisa > worker decide > resposta estruturada > salva > merge > auditor.

## Observações do registrador

- Requisitos 1-2 descrevem contrato desejado, não garantia empírica da API Jina. Lacuna: upstream pode retornar menos de 10 resultados ou conteúdo truncado; spec deve documentar ambos os cenários.
- Requisito 7 (briefing síncrono) já está parcialmente implementado em `app/routers/research.py` (diff em working tree), mas não refletido em docs/specs canônicas.
- Scope: somente documentação/specs. Nenhum código alterado nesta sprint.
