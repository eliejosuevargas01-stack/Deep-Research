# Brief inicial, /reversa-new

> Selo 🟡 PLANEJADO. Documento de entrada do time Code New Project Agents.

**Data:** 2026-10-21
**Usuário:** eliezer

## Ideia original

Pipeline simples de pesquisa profunda na internet composto de 4 etapas, cada uma com
um endpoint próprio, em Python (FastAPI), monolito modular, cada endpoint funciona
por separado.

**Etapa 1 — Plano de investigação** (`api/v1/plan`)
Entrada/tema → banco → LLM + tool Jina SERP → LLM formula query e escolhe N pontos
mais relevantes (só lê resultados SERP, nunca abre páginas) → parser → persiste
pontos no banco (`tema`, `id_pesquisa`, `ponto_id`, `ponto_n`). N por pesquisa
definido em variável de ambiente (padrão 5, sem fallback hardcoded).

**Etapa 2 — Busca** (`api/v1/search`)
Banco + id_pesquisa → todos os pontos em paralelo por LLM leve → personas
(`historiador`, `visionario`, `cectico`, `futurista`) → memória apenas para tool
call → tool Jina SERP + Scrapper (`s.jina.ai`) → filtro de URLs já lidas por
id_pesquisa → parser concatena resposta inteira (sem cortar) em 1 item com links →
persiste URLs em background → modelo decide mais query ou devolve resposta → parser
(`tema`, `id_pesquisa`, `ponto`, `ponto_id`, `conteudo_coletado`, `urls_lidas`,
`urls_fonte`) → banco.

**Etapa 3 — Auditoria** (`api/v1/audit`)
Banco + id_pesquisa → LLM forte responde 12 perguntas de qualidade sobre o
conteúdo coletado → parser (`id_pesquisa`, `tema`, `id_ponto`, `ponto`,
`aprovado|reprovado`, `pontos_fracos`).

**Etapa 4 — Redação** (`api/v1/writer`)
Banco + id_pesquisa (quando todos os pontos finalizados) → concatena tudo →
LLM forte gera dossier completo com fontes canônicas marcadas → parser → banco →
POST para webhook de callback.

## Personas do sistema (7)

planejador, historiador, visionario, cetico, futurista, auditor, redator final.
Número e identidade definidos por variável de ambiente; sem fallback hardcoded.

## Restrições técnicas

- Python + FastAPI, monolito modular, exatamente 4 endpoints principais.
- Endpoints administrativos extras permitidos para cadastrar pesquisa e
  carregar/salvar configuração (chaves, base URLs, preferências).
- Chamadas HTTP a modelos apenas OpenAI-compatible; Jina via tool.
- Tentativas: 1 inicial + 3 retries, timeout 600s.
- Persistência: SQLite permanente (sobrevive a redeploy sem perder dados).
- Base URL de Jina e de LLM configuráveis e persistidas.
- Toda credencial (chave, base URL, preferência) em tabela criptografada, com
  override por variável de ambiente do container.

## Tabelas

- `pesquisa` — usada pelo endpoint 1 (cadastro) e pelo writer (relatório final).
- `pontos` — usada pelo plan (1 item por ponto) e pelo auditor (status).
- `conteudo_coletado` — usada pelo search e pelo auditor.

## Respostas da entrevista única

- Problema raiz: pesquisas manuais levam dias, fontes não auditadas, relatório
  sem rastreabilidade; o custo atual é alto.
- Valor entregue: pesquisa profunda auditada com rastreabilidade a custo baixo.
- Alternativas: Perplexity, GPT Deep Research, Gemini Deep Research (custo/caixa
  preta, sem auditoria por ponto).
- Público: analistas, redatores, devs, times de research.
- Métrica de sucesso: dossier com fontes canônicas, N pontos aprovados,
  tempo < 10 min.
- Premissas perigosas: custo de tokens, qualidade da persona, complexidade do
  código, falhas em produção.
- Prazo: 21 de outubro, 22h (horário de Brasília).
- Compliance: nenhuma.
- Não-objetivos no MVP: fazer tudo de uma vez só, complicar a pesquisa, entregar
  resultado mediano, ter mais de 4 endpoints principais.
- Dúvidas durante execução: parar e perguntar (`answer_mode = chat`).

---
Gerado por /reversa-new em 2026-10-21
