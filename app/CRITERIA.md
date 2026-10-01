#CRITERIOS ACEITOS PARA ESTE SISTEMA DE DEEP RESEARCH

1. BACKEND:
    A. briefing:
        schemas deve validar que a chamada esteja correta, esteja autenticada, o seguintes campos são obrigatorios:
        chave api
        token de usuario jwt
        tema da pesquisa
        a URL de webhook de callback é opcional e deve ser configurada na página de configurações, junto com as chaves e os modelos; ela não deve ser enviada no payload de criação de cada pesquisa.
    A1. guardrails devem proteger o agente de responder algo que não deveria, segredos, funcionamento interno, prompts de sistema etc.
    A2. o agente de briefing não deve fazer pesquisas extensas nem demoradas, ele deve fazer um maximo de 3 a 5 pesquisas em sites diferentes apenas coletando informação central sobre o assunto para criar o rascunho da pesquisa
    A3. o rascunho da pesquisa deve ser enviado apenas 1 vez ao usuario para editar ou aprovar com uma unica tentativa, a resposta de aprovação não deve voltar ao briefing, continuando com o fluso, a resposta de edição do usuario deve voltar ao agente de briefing para refazer o rascunho e não ser mais encaminhado ao usuario, continuando assim com o fluxo
    A4. apos o rascunho ser enviado ao usuario e a resposta ter sido recebida deve ser persistida no banco, consolidando assim a pesquisa iniciada oficialmente.
    A5. apos a persistencia no banco da pesquisa deve ser roteado cada ponto de acordo com o seu paralelismo, se todos forem pesquisas independentes devem ser executadas de forma paralela, se todas forem sequenciais devem ser iniciadas uma por vez e se algumas forem sequenciais e outras paralelas, as paralelas iniciam em paralelo e as sequenciais inicia a primeira e quando essa finalizar vai a proxima dependente

    B. workers: todos os workers devem pesquisar o mesmo assunto em paralelo focando no seu vies, aprender com a informação encontrada e continuar com sua pesquisa até no maximo 3 queries por assunto.
    B1. todos os agentes devem ter memoria basada no assunto, nunca na pesquisa inteira, tambem não memoria persistente longa, ele deve ter memoria dinamica focada apenas no assunto do momento para aprender com as pesquisas, uma vez satisfeitas as perguntas do subagente, ou finalizado o contador de 3 queries, o worker deve entregar um resumo do que aprendeu e encontrou durante a pesquisa com suas urls fonte.
    B2. a resposta desse worker deve ser persistida no banco, e se um dos 4 workers finalizar antes a pipeline deve esperar todos os 4 workers finalizarem a pesquisa para continuar para a auditoria desse ponto especifico.
    B3. auditor deve analisar as 4 perspectivas por vez, nunca deve receber varios pontos diferentes por vez, apenas um ponto com as 4 perspectivas do agente, ele apenas responde as seguintes perguntas: 
    A pergunta original foi realmente respondida?
            O resultado responde diretamente ao que foi pedido ou só fala do assunto de forma geral?

            Todos os pontos essenciais da pergunta foram cobertos?
            Existe alguma lacuna importante que impeça considerar a resposta completa?

            As afirmações importantes possuem evidência?
            Dados, números, datas e fatos relevantes estão apoiados por fontes identificáveis?

            As fontes são adequadas para cada afirmação?
            Priorizar fonte primária/oficial quando existir. Blog ou agregador não deveria sustentar algo que pode ser confirmado em documentação oficial.

            As fontes realmente dizem aquilo que o worker afirma?
            Essa é crucial. Não basta ter URL: a evidência precisa sustentar a conclusão.

            As informações estão atuais o suficiente para a pergunta?
            Se o assunto é NVIDIA em 2026, uma fonte de 2022 pode servir para histórico, mas não para afirmar estado atual.

            Há contradições entre as fontes?
            Se houver, elas foram identificadas e tratadas corretamente em vez de o worker escolher silenciosamente uma versão?

            O worker separou fato, inferência e incerteza?
            Algo deduzido pelo agente não pode aparecer como fato confirmado.

            A pesquisa permaneceu dentro do escopo?
            Ela encontrou informação relevante ou começou a perseguir assuntos interessantes, porém desnecessários para responder à pergunta?

            Há alguma informação crítica que justificaria uma nova busca?
            Não “seria legal pesquisar mais”, mas algo cuja ausência realmente prejudique a resposta.

            É possível encerrar esta pesquisa agora?
            Aqui o auditor precisa dar uma decisão explícita: APPROVED ou RETRY.

            Se for RETRY, exatamente o que falta pesquisar?
            O auditor deve devolver instruções concretas ao worker, por exemplo:
            Confirmar o limite gratuito atual da NVIDIA API em fonte oficial e verificar se o limite é por conta ou por modelo.
            E não algo vago como “pesquise mais”.
    a auditoria é baseada nessas perguntas e a saida deve responder: todos os requisitos foram cumpridos? se sim persiste no banco e avança para o redator final, se não persiste no banco e chama novamente os workers com o assunto e oq falta pesquisar com um maximo de 3 retries.

    C. redator deve iniciar apenas quando todos os pontos estiverem completos e a informação ja estiver consolidada, apenas focando na qualidade do relatorio a apresentar ao usuario final.
    D. o relatorio final deve ser persistido no backend e disponibilizado ao usuario pelo frontend como canal principal. Quando houver uma URL de callback configurada, o backend também deve enviar o relatorio para esse destino como canal adicional; falha ou indisponibilidade do webhook não pode impedir nem remover o acesso ao relatorio no sistema, e deve permitir nova tentativa de envio.
    E. deve existir um serviço de eventos do backend para publicar em tempo real o ciclo de execução da pesquisa, incluindo mudanças de status, início e conclusão de etapas, uso de ferramentas (tipo de ferramenta e resultado resumido), progresso de cada agente, auditoria, retries e geração do relatório. Os eventos devem ser associados à pesquisa, persistidos em ordem e disponibilizados por stream autenticado, com retomada após reconexão a partir do último evento recebido.
    E1. eventos podem apresentar resumos seguros do que o agente está fazendo ou concluiu, mas nunca devem transmitir chain-of-thought, pensamento interno bruto, prompts de sistema, conteúdo privado de ferramentas, credenciais ou outros segredos.


2. FRONTEND:
    A. a interface deve ser implementada em React 19 com TanStack Router e Tailwind CSS, com experiência visual de chat de inteligência artificial inspirada nos padrões de uso de Gemini, Kimi, Grok e ChatGPT, sem copiar suas marcas ou telas literalmente.
    A1. a aplicação deve possuir telas para login, dashboard de pesquisas, visualização de pesquisa em andamento e pagina de configurações, com roteamento seguro e carregamento de estados de vazio, erro e loading.
    A2. a tela de chat deve permitir que o usuario envie um tema de pesquisa e inicie a pesquisa, acompanhe o progresso em tempo real e visualize o status dos agentes e dos pontos de investigação; não deve solicitar a URL do webhook nessa tela ou no envio da pesquisa.
    A3. o fluxo de briefing deve apresentar ao usuario um rascunho de 5 pontos em um unico card editor, permitindo revisar, reordenar, editar texto, ativar/desativar paralelismo e aprovar ou enviar ajustes antes de continuar.
    A4. a interface deve consumir o backend via requests autenticadas por cookie HttpOnly, com CSRF em rotas mutantes, sem expor segredos da API no bundle, no localStorage ou no navegador, e sem usar headers client-side como X-Tenant-ID.
    A5. a interface deve acompanhar a execução ao vivo por meio do event service, exibindo status da pesquisa e de cada agente, etapas em andamento, ferramentas utilizadas e resultados resumidos, retries, auditoria e conclusão, sem expor reasoning interno, chain-of-thought, prompts do sistema ou dados privados.
    A6. a tela de resultados deve buscar e renderizar o relatorio final disponibilizado pelo backend, em texto limpo, com estrutura de topicos, evidencias, citacoes, links de fontes, badges de auditoria e opcao de copiar ou exportar o conteudo, sem quebrar o layout em pesquisas muito longas. A disponibilidade do relatorio no frontend independe da entrega ao webhook.
    A7. a pagina de configuracoes deve permitir cadastrar chaves de provedores externos, selecionar modelos por agente e configurar, atualizar ou remover a URL opcional do webhook de callback. As alteracoes devem ser persistidas pelo backend e aplicadas sem reinicio; dados sensiveis nao podem ser salvos em localStorage ou no cliente.
    A8. a interface deve ter tratamento robusto para autenticação expirada, erros de rede, retorno 401/403, falhas no SSE, falhas de request e respostas vazias, exibindo mensagens claras e mantendo a experiencia do usuario em fluxo seguro.
    A9. os componentes devem seguir principios de acessibilidade e usabilidade: contraste adequado, focos visiveis, labels claras, feedback de carregamento, espaçamento consistente e estados visuais para sucesso, alerta e erro.
    A10. o frontend deve ser validado como parte da entrega completa, cobrindo pelo menos: login bem sucedido, envio de pesquisa, aprovação do briefing, stream de progresso, auditoria final, visualizacao do relatorio, configuracao de modelos e webhook, e confirmacao de que falha no webhook nao impede acesso ao relatorio pelo frontend.

    A11. a aplicacao deve manter o estado da pesquisa de forma consistente em frontend, com cache local de sessoes, items ativos, detalhes por pesquisa e atualizacoes em fila, sem duplicacao de mensagens ou perda de sincronismo durante o streaming.
    A12. a tela principal deve organizar o trabalho em tres areas: uma barra lateral esquerda recolhivel com pesquisas recentes, acesso a projetos, icone de configuracoes e icone de perfil do usuario; a area central dedicada à conversa com o agente de pesquisa profunda; e um painel lateral direito para os artefatos produzidos pelo chat, como briefing, evidencias e relatorio.
    A13. a barra de pesquisas e o painel de artefatos devem poder ser recolhidos e reabertos sem perder o contexto da pesquisa ou a conversa ativa. Em telas menores, essas areas devem se adaptar como paineis ou gavetas acessiveis sem sobrepor o conteudo de forma inutilizavel.
    A14. a area central deve priorizar a conversa e a composicao de mensagens, exibindo o estado do agente e o progresso da pesquisa no contexto do chat; os artefatos gerados devem permanecer acessiveis no painel direito sem interromper ou substituir a conversa.
    A15. a conversa deve apresentar uma linha do tempo dos eventos da execução com atualização em tempo real e ordem consistente, indicando quais ações o agente realizou e o resultado resumido de cada etapa. Após reconexão ou reabertura da pesquisa, o frontend deve recuperar os eventos anteriores e continuar do ponto mais recente sem duplicações.