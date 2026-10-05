# Critérios Aceitos para o Sistema de Deep Research

## 1. Backend

### A. Briefing

- **Autenticação:** cada chamada deve usar o mecanismo adequado ao tipo de cliente, sem exigir os dois mecanismos simultaneamente:
  - Clientes backend-to-backend devem enviar a chave de API no header `X-API-Key`. Essa chave não deve ser exigida nem exposta ao frontend.
  - O frontend deve autenticar o usuário com JWT em cookie `HttpOnly`, com proteção CSRF nas rotas mutantes. O token não deve ser exposto ao JavaScript do cliente.
- **API-first e dupla superfície:** todo o ciclo principal de pesquisa deve funcionar sem frontend por meio da API autenticada e também por meio do frontend. O frontend é um cliente da mesma capacidade de backend, não um caminho privilegiado nem obrigatório. Um cliente backend-to-backend autenticado por `X-API-Key` deve conseguir iniciar pesquisa, consultar status, aprovar/editar briefing, acompanhar eventos, consultar relatório, configurar callback por request e retomar uma pesquisa quando permitido.
- **Payload de criação:** apenas o tema é obrigatório. As credenciais são validadas pela camada de autenticação, não pelo schema do briefing.
- **Callback para o frontend:** a URL de webhook é opcional, configurada e persistida na página de configurações. Ela não deve ser enviada no payload de criação da pesquisa pelo frontend.
- **Callback para clientes backend:** clientes backend-to-backend autenticados por `X-API-Key` não possuem página de configurações. Podem enviar `callback_url` opcional em cada request de criação da pesquisa. O backend deve validar e persistir essa URL associada à pesquisa para entregar o relatório e permitir retry. Se não enviarem `callback_url`, consultam o relatório posteriormente pelo endpoint autenticado e ID da pesquisa ou do relatório.
- **Consulta de relatórios:** o relatório deve sempre ser persistido e consultável por ID via API, com ou sem callback. Usuários do frontend consultam suas pesquisas e relatórios pela interface.

- **A1. Guardrails:** devem proteger o agente de responder algo que não deveria, incluindo segredos, funcionamento interno e prompts de sistema.
- **A2. Briefing conciso:** o agente de briefing não deve fazer pesquisas extensas nem demoradas. Deve realizar no máximo de 3 a 5 pesquisas em sites diferentes, coletando apenas informações centrais sobre o assunto para criar o rascunho da pesquisa.
- **A3. Revisão única do briefing:** o rascunho deve ser enviado uma única vez ao usuário para edição ou aprovação. A resposta de aprovação não deve voltar ao briefing; o fluxo continua. A resposta de edição deve voltar ao agente de briefing para refazer o rascunho, sem ser encaminhada novamente ao usuário, e então o fluxo continua.
- **A4. Persistência:** após o rascunho ser enviado ao usuário e a resposta ser recebida, ela deve ser persistida no banco, consolidando oficialmente a pesquisa iniciada.
- **A5. Paralelismo dos pontos:** após a persistência da pesquisa no banco, cada ponto deve ser roteado de acordo com seu paralelismo:
  - Pontos independentes devem ser executados em paralelo.
  - Pontos sequenciais devem ser iniciados um por vez.
  - Em um fluxo misto, pontos paralelos iniciam em paralelo; pontos sequenciais iniciam pela primeira dependência e avançam conforme ela termina.

### B. Workers

- **B. Execução dos workers:** todos os workers devem pesquisar o mesmo assunto em paralelo, cada um com seu viés, aprender com as informações encontradas e continuar a pesquisa por no máximo 3 queries por assunto.
- **B1. Memória contextual:** os agentes devem ter memória baseada no assunto, nunca na pesquisa inteira, e não devem manter memória persistente longa. A memória deve ser dinâmica e focada apenas no assunto atual. Quando as perguntas do subagente forem satisfeitas ou o limite de 3 queries for atingido, o worker deve entregar um resumo do que aprendeu e encontrou, com as URLs das fontes.
- **B2. Persistência e sincronização:** a resposta e as evidências válidas de cada worker devem ser persistidas no banco. Se um dos 4 workers terminar antes, a pipeline deve esperar os quatro workers concluírem a pesquisa antes de continuar para a auditoria daquele ponto.
- **B3. Auditoria por ponto:** o auditor deve analisar as 4 perspectivas de um único ponto por vez, nunca vários pontos diferentes simultaneamente. Para cada ponto, deve responder e registrar as 12 perguntas abaixo como critérios verificáveis:

  1. **A pergunta original foi realmente respondida?**
      - O resultado responde diretamente ao que foi pedido ou apenas fala do assunto de forma geral?
  2. **Todos os pontos essenciais da pergunta foram cobertos?**
      - Existe alguma lacuna importante que impeça considerar a resposta completa?
  3. **As afirmações importantes possuem evidência?**
      - Dados, números, datas e fatos relevantes estão apoiados por fontes identificáveis?
  4. **As fontes são adequadas para cada afirmação?**
      - Deve-se priorizar fonte primária ou oficial quando existir. Um blog ou agregador não deve sustentar algo que pode ser confirmado em documentação oficial.
  5. **As fontes realmente dizem aquilo que o worker afirma?**
      - Não basta ter uma URL: a evidência precisa sustentar a conclusão.
  6. **As informações estão atuais o suficiente para a pergunta?**
      - Se o assunto é NVIDIA em 2026, uma fonte de 2022 pode servir para histórico, mas não para afirmar o estado atual.
  7. **Há contradições entre as fontes?**
      - Se houver, elas foram identificadas e tratadas corretamente, em vez de o worker escolher silenciosamente uma versão?
  8. **O worker separou fato, inferência e incerteza?**
      - Algo deduzido pelo agente não pode aparecer como fato confirmado.
  9. **A pesquisa permaneceu dentro do escopo?**
      - Ela encontrou informação relevante ou começou a perseguir assuntos interessantes, porém desnecessários para responder à pergunta?
  10. **Há alguma informação crítica que justificaria uma nova busca?**
        - Não basta que “seria legal pesquisar mais”; a ausência deve realmente prejudicar a resposta.
  11. **É possível encerrar esta pesquisa agora?**
        - O auditor deve dar uma decisão explícita: `APPROVED` ou `RETRY`.
  12. **Se for `RETRY`, exatamente o que falta pesquisar?**
        - O auditor deve devolver instruções concretas ao worker, por exemplo: “Confirmar o limite gratuito atual da NVIDIA API em fonte oficial e verificar se o limite é por conta ou por modelo”. Não deve dar instruções vagas como “pesquise mais”.

- **B3.1. Limiar de aprovação:** cada uma das 12 perguntas deve ser registrada como satisfeita ou não satisfeita. Um ponto é considerado suficiente quando pelo menos 80% dos critérios são satisfeitos, o que significa **10 de 12**. Abaixo de 10/12, o resultado é `RETRY`, salvo quando o teto de tentativas já foi atingido. Critérios condicionais devem ser considerados satisfeitos apenas quando sua condição foi tratada corretamente; eles não devem ser simplesmente ignorados.
- **B3.2. Resultado da auditoria e retry:** em `APPROVED`, o resultado é persistido e o ponto avança. Em `RETRY`, o auditor deve devolver instruções específicas sobre as lacunas. Os workers devem reutilizar evidências válidas já persistidas e pesquisar somente o que ainda falta sempre que possível, sem repetir automaticamente as três queries nem refazer fontes já suficientes. São permitidos no máximo 3 retries além da execução inicial, totalizando até 4 execuções por ponto.
- **B3.3. Teto de tentativas:** se o ponto continuar abaixo do limiar após a quarta execução, ele passa para `BLOCKED`, preserva todas as evidências e achados coletados, registra as lacunas e incertezas e segue para a síntese final com caveats. Um único ponto bloqueado não pode impedir indefinidamente a chegada ao redator.

### B4. Busca, leitura e desempenho

- **Modo `free` obrigatório e padrão:** o sistema deve funcionar sem credencial de busca. Nesse modo, usa uma fonte de busca gratuita/sem credencial e o Jina Reader sem autenticação para leitura das páginas quando aplicável. O sistema deve respeitar RPM, TPM, concorrência e demais limites do provedor por meio de filas, semáforos, backoff e timeouts; nunca deve tentar contornar limites.
- **Modo `jina_proxy` opcional e acelerado:** o usuário configura apenas a URL base do Cloudflare Worker/relay e o segredo de autenticação desse Worker. O Deep Research envia a requisição ao Worker de forma síncrona e recebe a resposta por ele. O pool interno de Jina API keys, rotação, bloqueio de chaves e failover pertencem ao Worker e não devem ser expostos nem administrados pelo Deep Research.
- **Reuso do conteúdo do Jina Search:** quando o Jina Search, diretamente ou via proxy, já retornar conteúdo utilizável das páginas junto aos resultados, esse conteúdo deve ser consumido diretamente. Não se deve fazer automaticamente uma segunda chamada ao Jina Reader para as mesmas URLs, salvo se o conteúdo estiver ausente, insuficiente, desatualizado para a auditoria ou exigir revalidação específica.
- **Providers alternativos:** SerpAPI e Apify permanecem como integrações opcionais/fallbacks e não são requisitos para o modo padrão.
- **Meta de tempo:** uma rodada de worker — query + aquisição de fontes + leitura/extração necessária + resumo de aprendizado — deve ter deadline aproximado de **30 segundos**. Com no máximo 3 queries, um worker não deve normalmente exceder aproximadamente **90 segundos** de wall time de pesquisa. Personas do mesmo ponto e pontos independentes continuam concorrentes de acordo com a DAG e o teto global.

### C. Redator

- O redator deve iniciar quando todos os pontos tiverem encerrado seu ciclo como `APPROVED` ou `BLOCKED` após o teto de tentativas. Deve usar toda a evidência válida persistida ao longo das execuções, os achados do Auditor e as incertezas/caveats dos pontos bloqueados para produzir a síntese final.
- O redator não deve deixar de executar apenas porque um ponto terminou `BLOCKED`; deve explicitar no relatório o que ficou inconclusivo.

### D. Relatório e callback

- O relatório final deve ser persistido no backend e consultável por ID via endpoint autenticado. Usuários do frontend também devem acessá-lo pela interface.
- Para o frontend, a URL de callback opcional vem das configurações persistidas. Para clientes backend-to-backend, `callback_url` opcional vem em cada request de criação de pesquisa e deve ser persistida associada à pesquisa.
- Quando disponível por qualquer um desses meios, o backend envia o relatório para esse destino como canal adicional. Falha ou indisponibilidade do webhook não pode impedir nem remover o acesso ao relatório no sistema, e deve ser possível tentar o envio novamente.

### E. Serviço de eventos e retomada

- Deve existir um serviço de eventos do backend para publicar em tempo real o ciclo de execução da pesquisa, incluindo mudanças de status, início e conclusão de etapas, uso de ferramentas, progresso de cada agente, auditoria, retries e geração do relatório.
- Além de status genérico, os workers devem emitir resumos públicos estruturados de atividade, como `worker_search_started`, `worker_sources_found`, `worker_learning_summary`, `worker_next_search`, `worker_satisfied`, `audit_started`, `audit_score` e `audit_retry_requested`, ou equivalentes. Esses eventos devem informar com segurança o que o agente encontrou e qual é o próximo passo sem expor raciocínio privado.
- Os eventos devem ser associados à pesquisa, persistidos em ordem e disponibilizados por stream autenticado, com retomada após reconexão a partir do último evento recebido.
- **Retomada de pesquisa:** uma pesquisa interrompida ou marcada como `failed` deve poder ser retomada explicitamente a partir do último checkpoint persistido válido. A retomada deve preservar briefing, pontos, `attempt_count`, evidências, auditorias, eventos e relatório parcial aplicável; pontos já `APPROVED` ou `BLOCKED` não devem ser refeitos sem necessidade.

#### E1. Privacidade dos eventos

- Os eventos podem apresentar resumos seguros do que o agente está fazendo, aprendeu ou pretende pesquisar em seguida, mas nunca devem transmitir chain-of-thought, pensamento interno bruto, prompts de sistema, conteúdo privado de ferramentas, credenciais ou outros segredos.

### F. Integração com modelos

- Todas as chamadas de inferência aos modelos de linguagem, para qualquer agente e provedor, devem passar exclusivamente pelo LiteLLM SDK, por meio de um gateway comum do backend.
- Não devem existir chamadas nativas diretas por provedor, uso de SDKs específicos para completar modelos nem requests HTTP construídos manualmente para inferência.

#### F1. Teste de credenciais

- O backend deve oferecer uma operação autenticada para testar uma chave de provedor antes de confirmar sua configuração.
- A operação deve retornar sucesso ou erro acionável sem devolver, registrar ou incluir a chave em eventos, logs ou respostas.
- O teste deve aceitar credenciais ainda não salvas.

#### F2. Descoberta de modelos

- O backend deve disponibilizar a lista real de modelos acessíveis para cada provedor configurado, obtida dinamicamente do catálogo do provedor ou endpoint configurado, sem substituir essa descoberta por uma lista fixa ou por modelos presumidos.
- A listagem não pode ser confundida com inferência: toda chamada de modelo continua obrigatoriamente passando pelo LiteLLM SDK.

#### F3. Endpoint OpenAI-compatible

- A configuração do provedor OpenAI deve aceitar uma `base_url` opcional para endpoints compatíveis com a API OpenAI.
- A `base_url` e a credencial devem ser encaminhadas ao LiteLLM SDK na configuração adequada, e a descoberta de modelos deve refletir os modelos realmente expostos por esse endpoint.

### G. Infraestrutura autogerenciada

- O projeto deve incluir `docker-compose.yml`/`compose.yml` suficiente para levantar o sistema completo com um único comando de build/up.
- O Compose deve criar e conectar automaticamente, no mínimo, `postgres`, backend e frontend/reverse proxy quando aplicável.
- O PostgreSQL deve usar volume nomeado persistente criado automaticamente pelo Compose; reiniciar ou recriar containers não pode apagar os dados por padrão.
- O backend deve aguardar o health check do banco e executar `alembic upgrade head` automaticamente antes de servir tráfego. Migrations são a fonte canônica de criação/evolução de schemas, tabelas, índices e constraints; o operador não deve executar SQL manual para preparar o banco.
- Segredos locais necessários ao próprio sistema, como `SESSION_SECRET`, `APP_ENCRYPTION_KEY` e senha local do banco, devem possuir bootstrap seguro de primeira execução quando ausentes, sem sobrescrever valores já existentes.
- Dependências Python, Node e de runtime devem ser instaladas pelas imagens durante o build. O operador não deve precisar instalar dependências dentro dos containers nem criar banco, volume, schema ou tabelas manualmente.
- O sistema deve ficar operacional após o fluxo documentado de `docker compose up --build`/equivalente, salvo a configuração de credenciais externas deliberadamente escolhidas para provedores de LLM ou integrações opcionais. O modo de busca `free` não exige credencial de busca.

## 2. Frontend

### A. Interface e experiência

- **A. Stack e experiência:** a interface deve ser implementada em React 19 com TanStack Router e Tailwind CSS. A experiência visual de chat de inteligência artificial pode se inspirar nos padrões de uso de Gemini, Kimi, Grok e ChatGPT, sem copiar literalmente suas marcas ou telas.
- **A1. Telas e estados:** a aplicação deve possuir telas para login, dashboard de pesquisas, visualização de pesquisa em andamento e página de configurações, com roteamento seguro e estados de vazio, erro e carregamento.
- **A2. Chat:** a tela de chat deve permitir que o usuário envie um tema, inicie a pesquisa, acompanhe o progresso em tempo real e visualize o status dos agentes e pontos de investigação. Não deve solicitar a URL do webhook nessa tela ou no envio da pesquisa.
- **A3. Editor de briefing:** o fluxo de briefing deve apresentar um rascunho de 5 pontos em um único card editor, permitindo revisar, reordenar, editar texto, ativar ou desativar paralelismo e aprovar ou enviar ajustes antes de continuar.
- **A4. Segurança do cliente:** a interface deve consumir o backend autenticada pelo JWT do usuário em cookie `HttpOnly`, com CSRF em rotas mutantes. Não deve expor o JWT ou chaves de API no bundle, no `localStorage` ou ao JavaScript do navegador, nem usar headers client-side como `X-Tenant-ID`. O header `X-API-Key` é reservado a clientes backend-to-backend.
- **A5. Acompanhamento ao vivo:** a interface deve acompanhar a execução por meio do serviço de eventos, exibindo status da pesquisa e de cada agente, etapas em andamento, ferramentas utilizadas, resumos públicos do que foi aprendido, próximo passo declarado pelo agente, retries, auditoria e conclusão, sem expor reasoning interno, chain-of-thought, prompts do sistema ou dados privados.
- **A6. Relatório:** a tela de resultados deve buscar e renderizar o relatório final disponibilizado pelo backend, em texto limpo, com estrutura de tópicos, evidências, citações, links de fontes, badges de auditoria e opção de copiar ou exportar o conteúdo, sem quebrar o layout em pesquisas muito longas. A disponibilidade do relatório no frontend independe da entrega ao webhook.
- **A7. Configurações:** a página de configurações do frontend deve permitir cadastrar chaves de provedores externos, testar cada chave antes de salvá-la, selecionar modelos por agente a partir de selects preenchidos com a lista real de modelos disponíveis no provedor, configurar uma `base_url` opcional para OpenAI-compatible, configurar a URL opcional do webhook e escolher o modo de busca. O modo `free` deve ser o padrão e não pedir chave de busca. O modo `jina_proxy` deve pedir somente URL do Worker/relay e segredo de autenticação do Worker; a UI não deve pedir nem exibir o pool interno de Jina API keys do relay.
- **A8. Tratamento de erros:** a interface deve tratar autenticação expirada, erros de rede, respostas 401/403, falhas no SSE, falhas de request e respostas vazias, exibindo mensagens claras e mantendo a experiência do usuário em fluxo seguro.
- **A9. Acessibilidade e usabilidade:** os componentes devem seguir princípios de acessibilidade e usabilidade: contraste adequado, focos visíveis, labels claras, feedback de carregamento, espaçamento consistente e estados visuais para sucesso, alerta e erro.
- **A10. Validação do frontend:** a entrega deve cobrir pelo menos login bem-sucedido, envio de pesquisa, aprovação do briefing, stream de progresso, auditoria final, visualização do relatório, teste de chave, seleção de modelos reais, configuração de `base_url` OpenAI-compatible, modos `free`/`jina_proxy`, webhook, retomada de pesquisa e confirmação de que falha no webhook não impede acesso ao relatório pelo frontend.
- **A11. Estado da pesquisa:** a aplicação deve manter o estado da pesquisa de forma consistente no frontend, com cache local de sessões, itens ativos, detalhes por pesquisa e atualizações em fila, sem duplicação de mensagens ou perda de sincronismo durante o streaming.
- **A12. Organização da tela principal:** a tela deve organizar o trabalho em três áreas:
  - Barra lateral esquerda recolhível com pesquisas recentes, acesso a projetos, ícone de configurações e ícone de perfil do usuário.
  - Área central dedicada à conversa com o agente de pesquisa profunda.
  - Painel lateral direito para artefatos produzidos pelo chat, como briefing, evidências e relatório.
- **A13. Painéis adaptáveis:** a barra de pesquisas e o painel de artefatos devem poder ser recolhidos e reabertos sem perder o contexto da pesquisa ou a conversa ativa. Em telas menores, essas áreas devem se adaptar como painéis ou gavetas acessíveis sem sobrepor o conteúdo de forma inutilizável.
- **A14. Prioridade da conversa:** a área central deve priorizar a conversa e a composição de mensagens, exibindo o estado do agente e o progresso da pesquisa no contexto do chat. Os artefatos gerados devem permanecer acessíveis no painel direito sem interromper ou substituir a conversa.
- **A15. Linha do tempo recuperável:** a conversa deve apresentar uma linha do tempo dos eventos da execução com atualização em tempo real e ordem consistente, indicando as ações do agente e o resultado resumido de cada etapa. Após reconexão, reabertura ou retomada da pesquisa, o frontend deve recuperar os eventos anteriores e continuar do ponto mais recente sem duplicações.
