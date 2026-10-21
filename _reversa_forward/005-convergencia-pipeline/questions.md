# Questões e premissas: convergência do pipeline

> PLAN-005-A; rascunho reconciliado, sem aprovação humana nova.
> Requirements §10 e adendo normativo §1.6 preservados. Modo autônomo converte dúvidas em premissas explícitas, não em decisões aprovadas.

## Q-501 — menos dez corpos, inacessibilidade e contexto

🔴 Política de recuperação permanece pendente. Premissa conservadora: solicitar `num=10` no Search investigativo e exigir dez corpos legíveis integrais por toolcall. Menos dez, corpo ausente/inacessível ou janela insuficiente gera erro seguro, não síntese parcial marcada como sucesso. Preservar material válido, sem truncamento silencioso, fontes inventadas, snippet substituto ou fallback DDG apresentado como leitura Jina. Não abrir novas buscas/recuperações indefinidas.

Escopo: personas investigativas, **não Scout**. Scout permanece SERP-only. Resultado incompleto não libera barreira, não conta como reprovação factual e não autoriza Writer antes de todos conclusivos. Limite de contexto não é resolvido por aumentar token arbitrariamente, cortar corpos ou persistir prompt bruto. Política futura poderá autorizar recuperação; nada disso foi aprovado aqui.

## Q-502 — falha fatal de persona / crash

🔴 Recuperação operacional ainda pendente. Premissa: erro seguro persistido quando banco/processo permitirem; demais personas e análises preservadas. Quatro sucessos distintos da mesma rodada são necessários; erro não é quarta análise, reprovação do auditor ou `AUDIT_CAVEAT`.

Encerrar invocação do ponto com diagnóstico explícito não conclusivo; não fazer retry fatal automático indefinido. Writer fica impedido se qualquer ponto não conclusivo. Retomada após crash só usa rodada explicitamente persistida e tarefas realmente ausentes; linha terminal de erro não vira sucesso por overwrite. Crash pode impedir gravação do diagnóstico. Histórico sem rodada fica retido, sem backfill fictício para 1. Não prometer entrega final normal nesses casos sem política adicional.

## Q-503 — protocolo Jina: decisão técnica, não lacuna de produto resolvida por suposição

🟡 Escolha fechada: POST Search existente com `{"q": query, "num": 10}` somente no `JinaToolAdapter` investigativo. Fonte oficial `https://raw.githubusercontent.com/jina-ai/reader/main/src/api/searcher.ts:114-116` aceita `count`/`num` de 0 a 20; fonte consultada declara parâmetro default 10 e propriedade `targetResultCount=6` na linha 59. Não confundir isso com site público historicamente citado como cinco por padrão em requirements §10. Site `https://jina.ai/search/` não foi revalidado nesta consulta (extração falhou). Nenhum default resolve pedido explícito dez, nem garante dez corpos reais.

`app/investigation/tools.py:165-170` hoje envia somente q; `_parse_body:58-78` aceita content/text **e** description/snippet. Search não é inerentemente snippet-only. Não impor Reader nem provider novo. MockTransport futuro comprova payload, shape e passagem integral; runtime com chave/proxy permanece não testado. Não alterar `JinaSerpClient` do briefing para dez corpos.

## Q-504 — armazenamento e histórico: fechado para detalhar, não pergunta humana

🟡 Adotar campos de rodada nullable sem default histórico, tabela proposta `investigation_merges`, merge determinístico e projeção de citações verificadas compatível com Evidence. Escolha e constraints no roadmap §4; não deixar menu entre tabela e pseudo-persona. NULL histórico é excluído da barreira; `attempt_count` atual mistura falhas técnicas e não permite reconstrução confiável. ID Alembic definido somente no coding após leitura do grafo.

## Estado e próximos artefatos

Decisões aprovadas do adendo e RN-501..510 preservadas. Q-501/Q-502 seguem pendentes com falha segura provisória, sem alegar resposta humana ou recuperação aprovada. Q-503/Q-504 são escolhas técnicas propostas, não garantias operacionais. Próximos: data-delta e ações consistentes com roadmap; auditoria independente depois. Nenhum produto implementado ou gate aprovado.
