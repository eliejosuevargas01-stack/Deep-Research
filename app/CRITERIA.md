eu quero# Critérios Aceitos para o Sistema de Deep Research

## 1. Backend

### A. Briefing

- **Autenticação:** cada chamada deve usar o mecanismo adequado ao tipo de cliente, sem exigir os dois mecanismos simultaneamente:
  - Clientes backend-to-backend devem enviar a chave de API no header `X-API-Key`. Essa chave não deve ser exigida nem exposta ao frontend.
  - O frontend deve autenticar o usuário com JWT em cookie `HttpOnly`, com proteção CSRF nas rotas mutantes. O token não deve ser exposto ao JavaScript do cliente.
- **Payload de criação:** apenas o tema é obrigatório. As credenciais são validadas pela camada de autenticação, não pelo schema do briefing.
- **Callback para o frontend:** a URL de webhook é opcional, configurada e persistida na página de configurações. Ela não deve ser enviada no payload de criação da pesquisa.
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
- **B2. Persistência e sincronização:** a resposta de cada worker deve ser persistida no banco. Se um dos 4 workers terminar antes, a pipeline deve esperar os quatro workers concluírem a pesquisa antes de continuar para a auditoria daquele ponto.
- **B3. Auditoria por ponto:** o auditor deve analisar as 4 perspectivas de um único ponto por vez, nunca vários pontos diferentes simultaneamente. Para cada ponto, deve responder às perguntas abaixo:

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

- **Resultado da auditoria:** se todos os requisitos forem cumpridos, o resultado deve ser persistido no banco e o fluxo avança para o redator final. Caso contrário, o resultado deve ser persistido e os workers devem ser chamados novamente com o assunto e o que falta pesquisar, por no máximo 3 retries além da execução inicial, totalizando até 4 execuções por ponto.

### C. Redator

- O redator deve iniciar apenas quando todos os pontos estiverem completos e as informações consolidadas, focando na qualidade do relatório apresentado ao usuário final.

### D. Relatório e callback

- O relatório final deve ser persistido no backend e consultável por ID via endpoint autenticado. Usuários do frontend também devem acessá-lo pela interface.
- Para o frontend, a URL de callback opcional vem das configurações persistidas. Para clientes backend-to-backend, `callback_url` opcional vem em cada request de criação de pesquisa e deve ser persistida associada à pesquisa.
- Quando disponível por qualquer um desses meios, o backend envia o relatório para esse destino como canal adicional. Falha ou indisponibilidade do webhook não pode impedir nem remover o acesso ao relatório no sistema, e deve ser possível tentar o envio novamente.

### E. Serviço de eventos

- Deve existir um serviço de eventos do backend para publicar em tempo real o ciclo de execução da pesquisa, incluindo mudanças de status, início e conclusão de etapas, uso de ferramentas (tipo de ferramenta e resultado resumido), progresso de cada agente, auditoria, retries e geração do relatório.
- Os eventos devem ser associados à pesquisa, persistidos em ordem e disponibilizados por stream autenticado, com retomada após reconexão a partir do último evento recebido.

#### E1. Privacidade dos eventos

- Os eventos podem apresentar resumos seguros do que o agente está fazendo ou concluiu, mas nunca devem transmitir chain-of-thought, pensamento interno bruto, prompts de sistema, conteúdo privado de ferramentas, credenciais ou outros segredos.

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

## 2. Frontend

### A. Interface e experiência

- **A. Stack e experiência:** a interface deve ser implementada em React 19 com TanStack Router e Tailwind CSS. A experiência visual de chat de inteligência artificial pode se inspirar nos padrões de uso de Gemini, Kimi, Grok e ChatGPT, sem copiar literalmente suas marcas ou telas.
- **A1. Telas e estados:** a aplicação deve possuir telas para login, dashboard de pesquisas, visualização de pesquisa em andamento e página de configurações, com roteamento seguro e estados de vazio, erro e carregamento.
- **A2. Chat:** a tela de chat deve permitir que o usuário envie um tema, inicie a pesquisa, acompanhe o progresso em tempo real e visualize o status dos agentes e pontos de investigação. Não deve solicitar a URL do webhook nessa tela ou no envio da pesquisa.
- **A3. Editor de briefing:** o fluxo de briefing deve apresentar um rascunho de 5 pontos em um único card editor, permitindo revisar, reordenar, editar texto, ativar ou desativar paralelismo e aprovar ou enviar ajustes antes de continuar.
- **A4. Segurança do cliente:** a interface deve consumir o backend autenticada pelo JWT do usuário em cookie `HttpOnly`, com CSRF em rotas mutantes. Não deve expor o JWT ou chaves de API no bundle, no `localStorage` ou ao JavaScript do navegador, nem usar headers client-side como `X-Tenant-ID`. O header `X-API-Key` é reservado a clientes backend-to-backend.
- **A5. Acompanhamento ao vivo:** a interface deve acompanhar a execução por meio do serviço de eventos, exibindo status da pesquisa e de cada agente, etapas em andamento, ferramentas utilizadas e resultados resumidos, retries, auditoria e conclusão, sem expor reasoning interno, chain-of-thought, prompts do sistema ou dados privados.
- **A6. Relatório:** a tela de resultados deve buscar e renderizar o relatório final disponibilizado pelo backend, em texto limpo, com estrutura de tópicos, evidências, citações, links de fontes, badges de auditoria e opção de copiar ou exportar o conteúdo, sem quebrar o layout em pesquisas muito longas. A disponibilidade do relatório no frontend independe da entrega ao webhook.
- **A7. Configurações:** a página de configurações do frontend deve permitir cadastrar chaves de provedores externos, testar cada chave antes de salvá-la, selecionar modelos por agente a partir de selects preenchidos com a lista real de modelos disponíveis no provedor, configurar uma `base_url` opcional para OpenAI-compatible e configurar, atualizar ou remover a URL opcional do webhook de callback. A URL de callback configurada nessa tela deve ser persistida no backend. Clientes backend-to-backend podem informar seu `callback_url` por request, sem depender dessa tela. A ausência de callback não pode impedir a consulta autenticada do relatório por ID. As alterações devem ser aplicadas sem reinício; dados sensíveis não podem ser salvos em `localStorage` ou no cliente.
- **A8. Tratamento de erros:** a interface deve tratar autenticação expirada, erros de rede, respostas 401/403, falhas no SSE, falhas de request e respostas vazias, exibindo mensagens claras e mantendo a experiência do usuário em fluxo seguro.
- **A9. Acessibilidade e usabilidade:** os componentes devem seguir princípios de acessibilidade e usabilidade: contraste adequado, focos visíveis, labels claras, feedback de carregamento, espaçamento consistente e estados visuais para sucesso, alerta e erro.
- **A10. Validação do frontend:** a entrega deve cobrir pelo menos login bem-sucedido, envio de pesquisa, aprovação do briefing, stream de progresso, auditoria final, visualização do relatório, teste de chave, seleção de modelos reais, configuração de `base_url` OpenAI-compatible e webhook, e confirmação de que falha no webhook não impede acesso ao relatório pelo frontend.
- **A11. Estado da pesquisa:** a aplicação deve manter o estado da pesquisa de forma consistente no frontend, com cache local de sessões, itens ativos, detalhes por pesquisa e atualizações em fila, sem duplicação de mensagens ou perda de sincronismo durante o streaming.
- **A12. Organização da tela principal:** a tela deve organizar o trabalho em três áreas:
  - Barra lateral esquerda recolhível com pesquisas recentes, acesso a projetos, ícone de configurações e ícone de perfil do usuário.
  - Área central dedicada à conversa com o agente de pesquisa profunda.
  - Painel lateral direito para artefatos produzidos pelo chat, como briefing, evidências e relatório.
- **A13. Painéis adaptáveis:** a barra de pesquisas e o painel de artefatos devem poder ser recolhidos e reabertos sem perder o contexto da pesquisa ou a conversa ativa. Em telas menores, essas áreas devem se adaptar como painéis ou gavetas acessíveis sem sobrepor o conteúdo de forma inutilizável.
- **A14. Prioridade da conversa:** a área central deve priorizar a conversa e a composição de mensagens, exibindo o estado do agente e o progresso da pesquisa no contexto do chat. Os artefatos gerados devem permanecer acessíveis no painel direito sem interromper ou substituir a conversa.
- **A15. Linha do tempo recuperável:** a conversa deve apresentar uma linha do tempo dos eventos da execução com atualização em tempo real e ordem consistente, indicando as ações do agente e o resultado resumido de cada etapa. Após reconexão ou reabertura da pesquisa, o frontend deve recuperar os eventos anteriores e continuar do ponto mais recente sem duplicações.