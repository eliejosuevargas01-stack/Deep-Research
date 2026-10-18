# Perguntas para Validação e Deliberação — Deep Research Engine

> Gerado pelo Revisor Documental (`/reversa-reviewer`) em 2026-10-16  
> Todas as 30 deliberações foram formalmente submetidas e respondidas pelo operador.  
> Status: 100% Respondidas e Consolidadas.

---

## Bloco 1: Ciclo de Vida do Briefing e Transições

### Pergunta 1: Reabertura de Briefing Aprovado
**Contexto:** Definição de imutabilidade do briefing após aprovação vs reabertura para rascunho.  
**Decisão do Operador:** ✅ **Respondida — Aprovação Definitiva.**  
> Uma vez aprovado, o briefing nunca mais volta a ser rascunho; tentativas de reabertura retornam HTTP 409 Conflict.

### Pergunta 2: Refinamento e Ajuste de Pontos
**Contexto:** Mecanismo de interação com o Scout para ajustar os pontos de foco.  
**Decisão do Operador:** ✅ **Respondida — Fluxo Conversacional e Interativo.**  
> O operador informa o tema -> Scout executa query SERP e gera rascunho de 3 a 7 pontos -> operador analisa e responde com direcionamento -> Scout recebe (tema + rascunho anterior + feedback do operador), formula nova query SERP mantendo o tema, ajusta os pontos afetados direta e indiretamente, auto-aprova e avança para a investigação. Se o operador aprovar o rascunho inicial direto, não há 2ª busca: é aprovado e avança imediatamente para os workers.

### Pergunta 3: Fluxo de Início da Investigação
**Contexto:** Unificação do endpoint de aprovação com o disparo de pesquisa.  
**Decisão do Operador:** ✅ **Respondida — Aprovação em Etapa Única.**  
> Acionar 'Iniciar Investigação' (`POST /briefings/{research_id}/investigate`) já aprova o briefing e dispara os agentes automaticamente.

---

## Bloco 2: Autenticação, Acesso Externo e Resiliência

### Pergunta 4: Conexão via API Externa
**Contexto:** Cabeçalhos aceitos para clientes máquina-a-máquina.  
**Decisão do Operador:** ✅ **Respondida — Aceitar Ambos.**  
> O sistema aceita oficialmente tanto `Authorization: Bearer <API_AUTH_SECRET>` quanto `X-API-Key: <API_AUTH_SECRET>`.

### Pergunta 5: Limite de Pesquisas por Agente
**Contexto:** Teto de buscas web das 4 personas investigadoras por ponto.  
**Decisão do Operador:** ✅ **Respondida — Até 3 buscas com parada inteligente.**  
> O agente faz até 3 consultas na web por ponto, parando antes voluntariamente se os dados coletados forem suficientes.

### Pergunta 6: Tratamento de Falhas Parciais de Agentes
**Contexto:** Resiliência quando 1 ou 2 personas falham em um ponto.  
**Decisão do Operador:** ✅ **Respondida — Sucesso Parcial.**  
> Se pelo menos uma persona trouxer dados válidos, o ponto avança para a auditoria.

### Pergunta 7: Critério de Falha Geral da Pesquisa
**Contexto:** Condição para transição da pesquisa para status `FAILED`.  
**Decisão do Operador:** ✅ **Respondida — Falha Total Estrita (100%).**  
> A pesquisa só é marcada como `FAILED` se 100% dos pontos falharem; havendo sucesso em ao menos um ponto, o fluxo avança para auditoria com o que foi apurado.

---

## Bloco 3: Armazenamento, Execução e Modelos

### Pergunta 8: Privacidade e Armazenamento dos Agentes
**Contexto:** Retenção de raciocínio intermediário (*chain-of-thought*) vs síntese final.  
**Decisão do Operador:** ✅ **Respondida — Síntese Final e URLs.**  
> Prompts brutos e pensamentos intermediários residem estritamente em RAM temporária; o banco de dados armazena apenas a síntese analítica final e a lista de links/URLs utilizados.

### Pergunta 9: Recuperação Pós-Reinicialização do Servidor
**Contexto:** Retomada automática após crash ou restart com pesquisas em andamento.  
**Decisão do Operador:** ✅ **Respondida — Retomada Seletiva.**  
> Ao religar, o sistema detecta pontos inacabados e executa apenas as personas pendentes, preservando o que já foi finalizado.

### Pergunta 10: Modelo de IA Padrão das Personas
**Contexto:** Resolução de modelo para personas sem configuração explícita.  
**Decisão do Operador:** ✅ **Respondida — Herança do Modelo do Scout.**  
> Se uma persona não tiver modelo exclusivo configurado em settings, herda automaticamente o modelo do Scout (`gemini/gemini-3.8-flash`).

---

## Bloco 4: Restrições de Entrada e Comportamento do Scout

### Pergunta 11: Quantidade de Pontos do Briefing
**Contexto:** Limites numéricos de pontos gerados.  
**Decisão do Operador:** ✅ **Respondida — Estritamente 3 a 7 pontos.**  
> A IA gera entre 3 e 7 pontos (alvo habitual de 5); saídas fora dessa faixa são rejeitadas e regeradas.

### Pergunta 12: Tipo de Busca no Briefing
**Contexto:** Coleta web preliminar do Scout.  
**Decisão do Operador:** ✅ **Respondida — Exclusivo Jina Search sem scraping.**  
> Utiliza apenas os snippets retornados pela Jina Search (`s.jina.ai`), sem leitura profunda ou scraping de corpo de página na fase de briefing.

### Pergunta 13: Tamanho e Validação do Tema
**Contexto:** Limites de texto na criação da pesquisa.  
**Decisão do Operador:** ✅ **Respondida — 3 a 300 caracteres após strip.**  
> Rejeição imediata com HTTP 422 para temas menores que 3 ou maiores que 300 caracteres.

### Pergunta 14: Segurança de Chaves de API
**Contexto:** Exposição de credenciais em endpoints e telas.  
**Decisão do Operador:** ✅ **Respondida — Ocultação Total.**  
> Nenhuma chave de API é exposta em logs, payloads ou telas; endpoints apenas confirmam se a chave está configurada (booleano).

### Pergunta 15: Resiliência da Busca e Geração no Briefing
**Contexto:** Tolerância a falhas temporárias de rede/provedor.  
**Decisão do Operador:** ✅ **Respondida — Até 4 tentativas com timeout de 30s.**  
> Até 4 tentativas sequenciais com reuso do resultado de busca caso a falha ocorra apenas na chamada de LLM.

---

## Bloco 5: Formatos, Timeouts e Rastreabilidade

### Pergunta 16: Correção de Formato JSON das Personas
**Contexto:** Respostas truncadas ou malformadas dos pesquisadores.  
**Decisão do Operador:** ✅ **Respondida — Até 3 tentativas de autocorreção.**  
> O sistema solicita até 3 correções de formato dedicadas antes de encerrar o agente como falho.

### Pergunta 17: Timeout Global por Pesquisador
**Contexto:** Limite máximo de execução em background.  
**Decisão do Operador:** ✅ **Respondida — 10 minutos (600 segundos).**  
> Encerramento seguro se o agente não concluir em até 10 minutos para proteger o event loop.

### Pergunta 18: Rastreabilidade de Fontes da Internet
**Contexto:** Registro de links retornados pelo motor de busca.  
**Decisão do Operador:** ✅ **Respondida — 100% das URLs auditadas.**  
> O sistema grava integralmente as URLs retornadas pela ferramenta em `read_urls` no banco de dados.

### Pergunta 19: Histórico de Versões do Briefing
**Contexto:** Armazenamento de rascunhos anteriores após refinamento.  
**Decisão do Operador:** ✅ **Respondida — Sobrescrita direta da versão ativa.**  
> Manter apenas a versão final ativa do briefing no banco para manter as tabelas compactas e limpas.

### Pergunta 20: Visualização do Progresso da Investigação
**Contexto:** Feedback ao vivo na tela do usuário.  
**Decisão do Operador:** ✅ **Respondida — Eventos em Tempo Real (SSE).**  
> Transmissão contínua de eventos SSE (*Server-Sent Events*) com o status individual de cada agente.

---

## Bloco 6: Rede, Integrações e Auditoria

### Pergunta 21: Proteção de Rede e SSRF na Busca
**Contexto:** Validação de rede e endpoints de navegação.  
**Decisão do Operador:** ✅ **Respondida — Responsabilidade Delegada à Jina.**  
> A Jina é um buscador externo seguro que realiza a varredura e higienização na nuvem; a responsabilidade da aplicação é ler e extrair os dados retornados, sem filtros adicionais redundantes de SSRF sobre a busca.

### Pergunta 22: Notificação Externa via Webhook
**Contexto:** Avisos automatizados para n8n ou plataformas externas.  
**Decisão do Operador:** ✅ **Respondida — Disparo via Webhook.**  
> Disparo automático de payload seguro para a URL de callback configurada assim que a pesquisa atingir `DONE` ou `FAILED`.

### Pergunta 23: Formato do Relatório Final
**Contexto:** Entrega da pesquisa redigida pelo Writer.  
**Decisão do Operador:** ✅ **Respondida — Markdown Completo com Citações Diretas.**  
> Documento estruturado em Markdown com referências explícitas para cada afirmação e fonte.

### Pergunta 24: Apresentação de Erros ao Usuário
**Contexto:** Exposição de falhas externas.  
**Decisão do Operador:** ✅ **Respondida — Mensagens Sanitizadas.**  
> Exibir apenas o motivo limpo e seguro em até 500 caracteres, sem expor stack traces ou detalhes internos.

### Pergunta 25: Identidade Visual da Interface
**Contexto:** Design system do frontend.  
**Decisão do Operador:** ✅ **Respondida — Dark Mode estilo Linear.**  
> Identidade visual nativa dark mode, tipografia limpa e layout minimalista de alta precisão.

---

## Bloco 7: Configurações, Sessão e Agente Auditor

### Pergunta 26: Validade da Sessão de Administrador
**Contexto:** Expiração do cookie de login no navegador.  
**Decisão do Operador:** ✅ **Respondida — 24 Horas.**  
> Cookie `dr_session` com tempo de vida de 24 horas a partir do login.

### Pergunta 27: Suporte a Proxy Jina
**Contexto:** Roteamento de tráfego de busca.  
**Decisão do Operador:** ✅ **Respondida — Proxy Opcional.**  
> Se configurado nas opções (`jina_proxy_url`), o tráfego de busca passa pelo proxy; caso contrário, conecta diretamente à Jina Search.

### Pergunta 28: Modelo Sugerido de Fábrica para o Scout
**Contexto:** Configuração padrão inicial.  
**Decisão do Operador:** ✅ **Respondida — `gemini/gemini-3.8-flash`.**  
> Modelo leve e veloz para a fase de briefing inicial.

### Pergunta 29: Atuação do Agente Auditor (Fase 3)
**Contexto:** Escopo e critérios da checagem de fatos.  
**Decisão do Operador:** ✅ **Respondida — Checklist das 12 Perguntas do Prompt.**  
> O auditor atua estritamente avaliando se as evidências respondem afirmativamente ao checklist das 12 perguntas definidas no seu prompt (`app/prompts/auditor.md`), aprovando com 10/12 ou solicitando correção focal.

### Pergunta 30: Retenção de Arquivos Transitórios
**Contexto:** Limpeza de dados temporários no encerramento.  
**Decisão do Operador:** ✅ **Respondida — Limpeza Automática.**  
> Purgar arquivos e rascunhos temporários do disco, preservando somente dados estruturados no banco.
