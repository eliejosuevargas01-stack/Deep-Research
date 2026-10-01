# Matriz de validação — Deep Research

Contrato de testes para executar após integração de backend, frontend e Compose. Nenhum caso abaixo é considerado aprovado sem resposta real e evidência.

## Segurança e configuração

| Cenário | Critério observável |
|---|---|
| Sem sessão | Rotas de pesquisa, relatório, eventos e configuração rejeitam com 401; `/health` continua público. |
| Login e logout | Login emite cookie `HttpOnly` e `SameSite`; logout revoga sessão; cookie antigo recebe 401. |
| CSRF e origem | POST/PUT autenticado de origem externa é rejeitado; solicitação legítima mesma origem funciona. |
| Segredos | GET `/api/settings` retorna só presença de credenciais e modelos; não retorna chave, senha, token ou texto cifrado. Frontend não grava segredos no armazenamento do navegador. |
| Modelos efetivos | Após alterar modelo de cada papel em `/api/settings`, próxima chamada desse papel usa escolha persistida; configuração não exige reinício. |
| Fallback | Sem SerpAPI/Apify, busca usa Jina sem chave; falhas externas são registradas sem inventar evidências. |
| SSRF | URLs privadas, loopback, link-local, IPv6 local, redirecionamento para IP privado e rebind de DNS são bloqueados tanto na leitura quanto no callback. |

## Ciclo de pesquisa

| Cenário | Critério observável |
|---|---|
| Tema inválido | Rejeição antes de chamar LLM ou busca. |
| Scout | Tema válido produz rascunho de cinco pontos e pausa em `pending_approval`. |
| Aprovação única | Edição aprovada é persistida; segunda aprovação é rejeitada, sem criar workers extras. |
| Dependências | Pontos dependentes aguardam conclusão dos predecessores; pontos independentes podem avançar juntos. |
| Concorrência | Pico de workers nunca excede 20, também entre pesquisas simultâneas. |
| Evidência | Cada alegação factual do relatório aponta para URL e trecho coletado; URL viva, isoladamente, não comprova alegação. |
| Auditor | Decisão registrada por ponto; após três tentativas malsucedidas, relatório segue com ressalvas explícitas, não com aprovação fabricada. |
| Persistência | Reinício do único backend durante scouting/pesquisa não perde execução nem duplica aprovação, evidências ou relatório. |
| Eventos | SSE reconecta e recupera eventos desde último ID; publica apenas eventos públicos estruturados, sem prompts internos nem raciocínio privado. |
| Relatório | GET `/api/reports/{id}` devolve Markdown persistido, links rastreáveis e incertezas; não devolve placeholder. |
| Callback | Sem URL de callback, relatório conclui; com URL permitida, entrega é verificada; falha preserva relatório para reenvio. |

## Interface e entrega

| Cenário | Critério observável |
|---|---|
| Chat | Entrada de tema, histórico, pausa para aprovação/edição, progresso dos quatro agentes e relatório final acessíveis por mouse e teclado. |
| Configurações | Chaves e modelos salvos pela UI são lidos de volta mascarados e influenciam chamadas reais do backend. |
| Responsividade | Fluxo completo utilizável em viewport móvel e desktop; contraste, foco visível e mensagens de erro. |
| Compose | PostgreSQL, backend e frontend sobem saudáveis; migrações são aplicadas em banco vazio; `.env` existente não é sobrescrito. |
| Domínio | DNS aponta ao servidor correto; HTTPS apresenta certificado público válido; `/health`, SPA, API e stream respondem no domínio alvo. |
| Pesquisa real | Realizar tema de base com provedor configurado, aprovar rascunho, acompanhar eventos e verificar amostra de citações no conteúdo das páginas originais. |

## Pendências verificadas antes da integração

- `research.dominuslabs.online` resolve para `72.60.247.157`, mas consulta HTTPS a `/health` falhou por certificado autoassinado. Não é evidência de deploy.
- Repositório local não apresenta remoto Git configurado.
- Nenhuma das variáveis `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `JINA_API_KEY`, `APIFY_API_TOKEN` e `SERPAPI_API_KEY` está definida no ambiente da sessão; configurar provedor real sem expor segredo antes do teste de pesquisa.
- Backend e frontend estão em implementação independente; contratos de payload e CSRF exigem teste conjunto, não suposição.
