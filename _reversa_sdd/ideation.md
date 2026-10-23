# Ideation, Deep Research

> Selo 🟡 PLANEJADO em todos os itens, sujeito a validação.

## Brief original
Pipeline simples de pesquisa profunda na internet composto de 4 etapas, cada uma com um endpoint próprio, em Python (FastAPI), monolito modular, cada endpoint funciona por separado.

## Problema
🟡 Pesquisas manuais levam dias, fontes não auditadas, relatório sem rastreabilidade; o custo atual é alto. O problema é sentido por analistas, redatores, devs e times de research sempre que precisam produzir uma investigação profunda sob demanda.

## Valor entregue
🟡 Pesquisa profunda auditada com rastreabilidade a custo baixo — o usuário passa de dias manuais a um dossiê completo em menos de 10 minutos, com cada ponto aprovado/reprovado e fontes canônicas marcadas.

## Alternativas existentes
🟡 Perplexity — caixa preta, sem auditoria por ponto, sem rastreabilidade de fontes.
🟡 GPT Deep Research — custo elevado, sem pipeline modular, sem controle de N pontos nem de personas.
🟡 Gemini Deep Research — mesma limitação de caixa preta e ausência de auditoria estruturada por etapa.

## Público-alvo (bruto)
🟡 Analistas, redatores, devs e times de research que precisam produzir investigações profundas sob demanda.

## Métricas de sucesso
🟡 Dossier com fontes canônicas: 100% dos pontos com URLs de origem rastreadas.
🟡 N pontos aprovados: todos os N pontos definidos por variável de ambiente (padrão 5) com status `aprovado`.
🟡 Tempo < 10 min: ciclo completo (plano → busca → auditoria → redação) concluído em menos de 10 minutos.

## Premissas a validar
🟡 Custo de tokens — o consumo de Jina SERP + LLM forte deve permanecer dentro de orçamento viável; se estourar, o modelo pode não escalar.
🟡 Qualidade da persona — as 7 personas (planejador, historiador, visionário, cético, futurista, auditor, redator final) precisam manter coerência de tom e foco; falha degrada o output.
🟡 Complexidade do código — monolito modular em FastAPI precisa manter 4 endpoints principais sem acoplamento; complexidade excedente gera bugs em produção.
🟡 Falhas em produção — dependência de Jina e LLM OpenAI-compatible pode falhar; retries (3) e timeout (600s) precisam ser suficientes.

## Notas
🟡 Número de pontos e identidade das personas definidos exclusivamente por variável de ambiente, sem fallback hardcoded.
🟡 Tabela de credenciais criptografada com override por variável de ambiente do container.
🟡 Endpoints administrativos extras permitidos para cadastro de pesquisa e carregamento/salvamento de configuração.
🟡 Modo de resposta: `answer_mode = chat` — parar e perguntar ao usuário em caso de dúvidas durante execução.
🟡 Prazo: 21 de outubro, 22h (Brasília).
🟡 Não-objetivos no MVP: não fazer tudo de uma vez, não complicar a pesquisa, não entregar resultado mediano, não ter mais de 4 endpoints principais.

---
Gerado por reversa-ideator em 2026-10-21T22:00:00Z
Fonte: newproject-brief.md
Sessão de ideação reaproveitada: newproject_progress.interview
