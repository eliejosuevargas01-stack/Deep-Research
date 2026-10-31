# Adendo v5 — entrega sequencial Audit

Fonte: objetivo e delegação explícitos do usuário, backlog DR-001..DR-015 e política de simplicidade v3. Plan e Search já têm aceite independente e HTTP real. Este adendo esclarece somente Audit e seus pontos de integração necessários, preservando as specs originais. Writer continua na etapa seguinte.

## Entrada e evidência

Audit usa o plano geral e eixo integral, as quatro análises atuais, conclusões, lacunas, diário e trechos/fontes canônicos da **coleta mais recente** do ponto. Coletas antigas servem ao histórico e à comparação de avaliações; não são concatenadas como se todas as versões fossem fatos atuais.

Somente URLs, descrições SERP ou um status antigo aprovado não comprovam evidência. Exigir corpo Reader/cache disponível, trechos com hash/offset coerentes e referências conhecidas no contexto efetivamente fornecido. Coleta atual incompleta, sem fonte ou sem proveniência não pode ser aprovada recorrendo silenciosamente a uma rodada antiga.

Contexto é JSON delimitado como dado não confiável, sem reasoning, prompts privados ou milhares de IDs excluídos. Enviar os trechos citados e relevantes já selecionados pelo Search, sem todo o corpus. Limites simples:32000caracteres de texto de evidência e120000no JSON de entrada. Se o material obrigatório não couber, retornar insuficiência explícita, sem corte oculto ou aprovação parcial disfarçada. Não criar outro motor de pesquisa no Audit; novas verificações são solicitadas ao Search.

## Doze critérios e decisão

Os IDs1..12 correspondem, nesta ordem, aos critérios do backlog: clareza temática, corroboração canônica, atualidade, ausência de contradições internas, embasamento factual, aderência ao escopo, profundidade analítica adequada, precisão de dados, neutralidade, densidade de evidências, incertezas/lacunas e solidez lógica.

Um único contrato tipado deve exigir IDs inteiros estritos1..12, ordem/cardinalidade exatas e booleanos reais, justificativa específica, listas de claim_ids/source_ids conhecidos e feedback de lacuna/correção. Não manter o contrato antigo com12booleanos que nascem True. Nome de fonte e ID existente não certificam implicação factual: o modelo deve julgar o conteúdo dos trechos, distinguir relato de confirmação e preservar o público/formato do pedido.

O backend calcula `atendidos = sum(c.aprovado is True)` e `percentual = round(100*atendidos/12,2)`. Default11; corte explícito10 ou12 é permitido.10/12=83.33,11/12=91.67. Não arredondar83.33para85 nem aceitar nota/status global sugeridos pelo modelo. Parâmetro inválido é rejeitado, sem troca silenciosa pelo default.

Vetor inválido, referências desconhecidas, resposta irregular/truncada ou ausência de dados nunca aprovam. A resposta distingue avaliação válida de diagnóstico técnico. Sem vetor válido, expor critérios ausentes/None e o diagnóstico; não inventar12julgamentos nem confundir falha do provedor com qualidade100%. Manter o comportamento fechado de pontuação0para contrato inválido previsto no adendo v1. Um reparo dirigido adicional é permitido; todos os envelopes observados precisam sobreviver.

## Persistência e repetição

Guardar avaliações como histórico estruturado no JSON existente da coleta (`metadados_coleta.auditorias`), com identidade da coleta/rodada, entrada/versionamento,12critérios, corte, contagem, percentual, decisão, diagnóstico/feedback, antes/depois e referências aos envelopes. Corpos e trechos não são duplicados. `GenerationAttempt` guarda cada chamada real com etapa `audit`, incluindo falhas/reparos, reasoning privado e métricas observadas. Não criar tabelas/colunas para necessidades antecipadas.

Resultado válido para a mesma coleta e mesma entrada/modelo/instrução pode ser reutilizado. Usar identidade/hash da entrada que exclua o próprio histórico de auditorias, para não invalidar o cache ao gravá-lo. Uma mudança apenas no corte recalcula o vetor existente no backend, sem nova inferência. Uma mudança de coleta/instruções/modelo exige avaliação nova. Reutilização idêntica é leitura sem incrementar tentativas nem invalidar um dossiê válido; nova decisão ou alteração do corte invalida artefato incompatível.

O contador de auditoria limita3tentativas de avaliação por ponto, sem contar leitura/recalculo de vetor já válido. Não resetar contadores. Sem resultado válido ao esgotar o limite, registrar término reprovado/diagnóstico, não deixar estado intermediário eterno.10aprovado por corte explícito continua abaixo da meta85% e deve ser mostrado como83.33.

## Estados e concorrência

Reserva/finalização atômicas antes/depois de I/O, reutilizando status, contadores e atualizado_em existentes. Pode usar `auditando` no ponto e na pesquisa; operações concorrentes não podem tomar uma reserva ativa de Search/Audit. Prazo do ponto180s, lease600s, constantes testáveis. Recuperação de reserva abandonada é limitada, sem infraestrutura nova.

Fechar a transação de leitura antes de rede. Finalização confere no banco a coleta, tentativa de Search, token/contador de auditoria e posse; uma chamada antiga não aprova dados novos nem apaga o dossiê de outra revisão. Preservar chamadas já observadas mesmo quando a decisão fica obsoleta; ela deve ser marcada não aplicada. Falha/cancelamento libera somente a própria reserva e não inventa finish/usage de chamada interrompida.

Vetores/status/feedback/histórico/envelopes e agregado da pesquisa são coerentes na transação. O agregado usa valores escalares atuais de todos os pontos, inclusive fora do filtro; não se baseia em objetos ORM antigos. Aprovação nova limpa pontos_fracos anteriores. API não retorna reasoning ou mensagens privadas. Clientes fecham em finally.

### Paralelismo de Pontos na Auditoria e Isolamento Concorrente
- **Execução paralela com barreira:** Quando múltiplos pontos são avaliados em lote, a auditoria é orquestrada concorrentemente (`asyncio.gather`), aguardando todos os pontos na barreira antes de consolidar o agregado da pesquisa.
- **Isolamento de sessão e conexão:** Cada trabalhador assíncrono de auditoria de ponto obtém sua própria `AsyncSession` independente (via `sessionmaker` vinculado à engine), eliminando concorrência de corrotinas na mesma sessão ou conexão SQLAlchemy. Caso o `bind` seja uma `AsyncConnection`, deve-se derivar a engine para isolamento real; se nenhuma fábrica segura estiver disponível para múltiplos pontos concorrentes, a execução paralela sobre a mesma sessão deve ser bloqueada explicitamente. Transações de leitura fecham antes da chamada ao modelo e finalizações ocorrem atomicamente via CAS.
- **Contrato externo síncrono:** O endpoint mantém retorno HTTP 200 síncrono completo (sem SSE), preservando ordenação determinística pelo número do ponto (`ponto_n`).
- **Cancelamento e integridade:** Cancelamento interrompe avaliações ativas e libera reservas via CAS com diagnóstico, mantendo preservados os pontos já deliberados e o histórico de envelopes observados.

## Feedback e sequência

Cada falha corrigível gera recomendação específica vinculada ao critério, claims/fontes e personas pertinentes. Validar nomes das quatro personas. O backend pode projetar tarefas a partir dos próprios critérios, evitando duas listas conflitantes de decisões. A próxima avaliação mostra diferenças por ID em relação ao parecer válido anterior, sem inventar nota anterior na primeira vez.

Aceitar filtro opcional ponto_id, preservando resultados dos demais. Expor critérios, contagem/corte/percentual, validade, diagnóstico, tarefas e metadados públicos. Preservar status_geral de processo quando útil, mas expor o estado real da pesquisa e se está pronta para Writer; zero reprovações com pontos não avaliados não significa pronta.

O chamador existente pode encaminhar tarefas ao filtro de personas já entregue em Search. No PipelineRunner, adaptar somente essa integração e impedir Writer quando houver reprovação, falha, pendência ou limite esgotado. Não implementar a redação nesta etapa nem enviar webhooks reais em testes.

## Gate de entrega

Gemini implementa e reproduz red→green; árbitro independente julga Audit e compatibilidade das dependências compartilhadas com Plan/Search; confirmação direta no snapshot aprovado; imagem exata; HTTP Audit no ponto já aceito. O resultado real deve persistir os12critérios e demonstrar contagem/decisão calculadas pelo backend. Se reprovado, usar feedback em Search direcionado e reavaliar, respeitando limites. Writer só começa como próxima etapa depois do aceite de Audit; o objetivo final85%+ permanece pendente.
