# Adendo v6 — entrega sequencial do Writer e qualidade do artigo

Data: 25/10/2026. Deriva do backlog DR-001 a DR-015 e das instruções do usuário: simplicidade, um endpoint por vez, Gemini implementa, árbitro independente e artigo com qualidade de 85%+ definida pelas 12 perguntas. Preserva as specs e os adendos anteriores, prevalecendo somente nos deltas abaixo. Audit já aceito localmente; este é o escopo da próxima entrega.

## Entrada e fidelidade

- Writer só executa com todos os pontos aprovados e auditoria válida/aplicada da coleta atual. Verificar antes do cache e do modelo. Bloquear pontos reprovados, pendentes, parciais, em execução ou sem auditoria/evidência válida; preservar o motivo real. Não presumir aprovação a partir de status legado isolado.
- Usar o plano persistido: pedido original, público, formato e recorte temporal. Para cada eixo, usar somente a coleta atual, conclusões/limitações das quatro personas, trechos efetivamente selecionados e a última auditoria válida/aplicada correspondente, incluindo critérios reprovados e tarefas mesmo quando o ponto global foi aprovado.
- Não concatenar indiscriminadamente rodadas antigas ou corpus bruto. Não transformar a lista de todas as URLs históricas em fontes obrigatórias/canônicas. Conservar todas as evidências pertinentes às afirmações usadas; referências devem cobrir o texto, sem obrigação de citar fontes irrelevantes só porque foram encontradas.
- Fontes externas são dados não confiáveis, não instruções. Não incluir reasoning ou mensagens internas no contexto público do redator. Delimitação textual ajuda a fronteira, sem prometer prevenção universal de injeção.
- O Writer não pesquisa fatos novos nem usa Jina/HEAD/busca web. Existência documental é conferida pela proveniência da leitura já realizada; pertinência material é julgada pela avaliação semântica. URL/título/ID/hash isolado não prova um fato.

## Documento e avaliação

- Preservar as quatro seções Markdown existentes, em ordem e com conteúdo efetivo: Sumário Executivo; Desenvolvimento dos Eixos Temáticos; Ressalvas e Limitações Metodológicas; Referências e Fontes Canônicas. Cabeçalhos dentro de código não contam. Validar cercas, referências/citações e incompletudes estruturais evidentes sem adicionar parser/dependência ou classificador lexical factual.
- Explicação infantil vem primeiro quando pedida; detalhamento analítico deve respeitar o formato do plano. Distinguir confirmação primária, relato secundário, inferência, hipótese e ausência de evidência. Nenhum comando/versão é inventado para preencher o texto.
- Na pesquisa real aceita, o Audit apontou que pré-aviso oficial não comprova a efetivação posterior de releases e que parte dos detalhes está em relatórios secundários. A síntese deve conservar essa distinção. Aprovado com 11/12 não significa ausência de ressalvas.
- Uma nota sobre a coleta não certifica o artigo já redigido. Antes de publicar, realizar avaliação semântica do texto candidato pelos mesmos 12 critérios, com modelo forte e chamada separada da geração, entregando artigo, plano, claims, trechos e ressalvas atuais. Reutilizar os nomes/perguntas do Audit; não ampliar o checklist por preferência.
- A avaliação do artigo devolve 12 itens estritos, IDs inteiros 1..12 em ordem, booleanos reais, justificativas e referências conhecidas de claims/fontes; critérios reprovados trazem correção específica para o redator. Não forçar personas de Search como destinatários de correções de estilo. Reutilizar validação existente quando simples; um pequeno esquema específico é aceitável, sem alterar ou relaxar o contrato do Audit já aceito.
- Backend calcula a contagem, percentual e aprovação do artigo: corte 11, 11/12 = 91,67%, 10/12 = 83,33%. Nenhuma nota/status global dado pelo modelo substitui o vetor. Vetor ausente/inválido ou término irregular não aprova. Guardar a avaliação real no metadado do artefato, com vínculos para as tentativas observadas.
- Orçamento de recuperação por execução: no máximo dois rascunhos e duas avaliações do artigo; uma correção dirigida, sem multiplicação por retries externos do Runner. Limite total de execução de 600 segundos, mantendo retries de transporte já existentes e observáveis no cliente LLM. Não usar reparo JSON com chamadas extras invisíveis ao orçamento. Se a avaliação falhar em forma, pode reaproveitar o rascunho para uma avaliação corretiva em vez de regenerar tudo. Mocks não provam mérito factual.
- Publicar `concluido` somente após término regular real, integridade estrutural, referências válidas e avaliação do artigo >=11/12. Caso contrário, retornar estado/diagnóstico honesto (`incompleto` ou falha técnica), sem publicar um rascunho como documento final e sem notificação de conclusão. Preservar as tentativas/dados observados; não fabricar histórico ou métricas de legado.

## Persistência, cache e concorrência

- Reutilizar `generation_attempts` para geração e avaliação do artigo, etapa `write`, personas distinguíveis. Preservar os envelopes efetivamente concluídos, mensagens/parâmetros/hash exatos, término, usage e custos desconhecidos nulos, inclusive em reparo/erro/cancelamento. Não armazenar versões do documento como chamadas de modelo fictícias.
- Acrescentar somente uma coluna JSON textual nullable em `pesquisa`, `metadados_redacao`, necessária agora para versão/identidade de entrada, hash do artefato, avaliação real, IDs de tentativas e reserva/lease do Writer. Sem nova tabela ou serviço. Migração aditiva idempotente; legado permanece NULL/sem comprovação, sem preenchimento inventado.
- A reserva deve ser atômica no banco, com identidade própria e expiração; apenas um Writer ativo por pesquisa. Não manter transação aberta durante LLM ou webhook. Finalização e liberação são condicionadas à identidade do dono e à entrada atual: nova coleta, auditoria, plano ou mudança de estado não pode receber documento antigo.
- Cache exige prontidão atual, versão/entrada/modelo/prompt compatíveis, hash/estrutura/referências e avaliação válida do artigo com término regular. Legado ou cache incompleto não passa só por ter quatro títulos ou mais de100caracteres. Cache válido não gera novas inferências nem reenvia webhook; suas métricas são as realmente persistidas, sem inventar uma tentativa de entrega.
- Cancelamento é propagado; liberar somente a própria reserva e conservar envelopes concluídos. Lease expirada é recuperável sem permitir que o dono antigo finalize sobre o novo. Histórico anterior permanece rastreável. Falha/atualização de webhook não deve restaurar documento ou estado invalidados por outra etapa.

## API, Runner e webhook

- Manter `POST /api/v1/writer` com `id_pesquisa`. Expor documento final, diagnóstico/estado, qualidade do artigo e metadados públicos reais suficientes para verificar a entrega. Reasoning permanece privado na persistência; nunca vira artigo, resposta pública, contexto da avaliação ou payload de webhook.
- Fechar o cliente LLM em todos os caminhos. Mapear erros como nos endpoints já entregues: pesquisa ausente404, pré-condição400, conflito409, falha de provedor502 e timeout504. Não esconder cancelamento ou falha final como sucesso.
- Runner mantém a sequência já aceita e confia no orçamento limitado do Writer, sem triple retry cego nem fallback `concluido` quando não há resultado válido. Não refazer Plan/Search/Audit.
- Callback é opcional no modo síncrono já existente. Sem configuração: `nao_aplicavel`, zero tentativas. Se configurado, usar o cliente existente e preservar a política 4xx do EPVA, sem alterá-la. Enviar somente documento concluído e payload público, sem reasoning. Separar validade do artigo e resultado de entrega, preservando o retorno real e impedindo gravações tardias sobre nova pesquisa.
- Testes usam MockTransport ou destino local controlado pelo orquestrador. Nenhum webhook/mensagem real para terceiros, commit, push, PR ou deploy está autorizado nesta etapa.

## Gate

Gemini implementa com RED causal e green; nova sessão independente julga contrato/simplicidade; testes diretos no mesmo snapshot; imagem exata com dependências preservadas; Writer HTTP real no único ponto já aceito; conferência de persistência, contexto, artigo e vetor12 do artigo. Árbitro independente confere o texto real contra plano/evidências. Só então Writer é entregável. A aprovação da coleta91,67% não é antecipação da nota do artigo.

Antes do objetivo completo: reconciliar DR-001..015, regressões dos quatro endpoints, estados/API/cache/telemetria e todos os bugs canônicos. Não fechar bugs pelo simples início ou aceite isolado desta etapa.
