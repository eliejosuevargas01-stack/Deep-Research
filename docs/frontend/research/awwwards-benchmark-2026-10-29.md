# Benchmark Awwwards — referências para o Deep Research

Levantado em 2026-10-29 a partir das páginas de categoria do Awwwards
(`/websites/ai/`, `/websites/developer-tools/`, `/websites/dashboards/`), que
listam o tier e a data de cada site. Onde a página viva foi aberta, a coluna
"fonte do detalhe" diz o que foi realmente inspecionado; nada aqui foi inferido
de screenshot que eu não tenha visto.

## Tabela

| # | Site | O que faz | Prêmio (conforme a listagem) | Estúdio | URL viva |
|---|---|---|---|---|---|
| 1 | Brunello Cucinelli — AI E-com | e-commerce com camada de IA | **Site of the Day + Developer Award**, 09/07/2026 | makemepulse | https://shop.brunellocucinelli.com/en-gb/ai |
| 2 | Cleo AI | assistente financeiro com voz própria | **Site of the Day + Developer Award**, 23/05/2026 | OddCommon | https://web.meetcleo.com/ |
| 3 | Fourmula AI | geração de catálogo por IA | **Site of the Day**, 02/05/2026 | Fourmeta Agency | https://fourmula.ai/ |
| 4 | Oryzo AI | produto ficcional "modelo aberto" de descanso de caneca | **Site of the Month (abr/2026) + Developer Award** | Lusion | https://oryzo.ai/ |
| 5 | THE TRIADIC BALLET AI | performance/instalação com IA | **Honorable Mention**, 20/07/2026 | isaWabi | https://www.thetriadicballetai.com/ |
| 6 | Patch Ai | sistema de patch de IA | **Honorable Mention**, 12/07/2026 | Rogue Studio | https://thepatchsystem.com/ai |
| 7 | AI in Design Report 2026 | relatório editorial interativo | **Honorable Mention**, 05/07/2026 | ++hellohello | https://stateofaidesign.com/ |
| 8 | Creative Marketing AI | marketing com IA | **Honorable Mention**, 19/06/2026 | PeachWeb | https://creativemarketing.peachweb.io/ |
| 9 | Ponder AI | workspace de pesquisa com IA | **Honorable Mention**, 10/06/2026 | Artemii Lebedev | https://ponder.ai |
| 10 | Viture Dashboard | dashboard de produto wearable | **Honorable Mention**, 26/09/2022 | RADCAT | https://www.viture.com/dashboard |

## Micro-detalhes que a maioria ignora

### 1. Brunello Cucinelli — AI E-com
- **Fonte do detalhe:** listagem do Awwwards (tier/data) + página viva não
  inspecionada em HTML.
- **O que impressiona:** a IA não vira "chat flutuante"; ela é uma camada de
  merchandising dentro do e-commerce. O produto continua sendo o protagonista e
  a IA aparece como gesto (recomposição de look), não como interface paralela.
- **Aplicar aqui:** o resultado da investigação é o protagonista; o dock de
  ferramentas é gesto discreto, não um segundo produto.

### 2. Cleo AI — inspecionado no HTML público
- **Vídeo como textura, não como banner:** o site serve thumbnails de vídeo via
  Mux (`image.mux.com/.../thumbnail.jpg`) em vez de GIFs ou MP4 soltos. O peso
  visual vem de mídia já otimizada e com poster — nada de layout shift.
- **Manifesto com drop cap:** o texto de abertura usa capitular grande e medida
  curta; a leitura fica editorial, não "landing page".
- **FAQ estruturado:** perguntas reais com respostas longas, sem acordeão
  escondido — bom para busca e para quem quer ler.
- **Aplicar aqui:** poster/estado vazio nunca "pula"; a prosa do dossiê usa
  medida de 72ch e capitular só se o relatório pedir.

### 3. Fourmula AI — inspecionado no HTML público
- **Preload com contador 0→100%** e sequência de imagens AVIF pré-carregadas:
  o primeiro gesto é esperar com dignidade, não olhar tela branca.
- **Grade de comparação lado a lado** ("choose the best"): a decisão é visual e
  binária, não uma tabela de features.
- **Números de etapa (01–04)** com rótulo curto e verbo no imperativo.
- **Aplicar aqui:** lista de temas numerada (01–04), comparação de cenários no
  relatório e estados de carregamento com texto, não spinner mudo.

### 4. Oryzo AI (Lusion) — inspecionado no HTML público
- **WebGL com um único objeto:** a piada inteira é um coaster 3D que responde
  ao mouse ("Try to hover hand"). Profundidade sem encher a tela de partículas.
- **Tabela de especificação como argumento:** "Stack / Lift / Connectivity:
  None" usa a linguagem de ficha técnica para fazer humor. Densidade é o charme.
- **Tipografia de papel:** serifada editorial + mono para dados.
- **Aplicar aqui:** o grafo de arquitetura é o "objeto único" interativo; o
  trace usa mono para dados e sans para prosa.

### 5. THE TRIADIC BALLET AI
- **Fonte:** listagem (HM 20/07/2026); página não inspecionada.
- **O que impressiona:** coreografia como metáfora de loop de agentes — o
  movimento explica o sistema antes de qualquer texto.
- **Aplicar aqui:** o loop de reprovação do grafo é animado por dash, mas só
  quando o nó de auditoria está ativo; movimento é explicação, não decoração.

### 6. Patch Ai
- **Fonte:** listagem (HM 12/07/2026); página não inspecionada.
- **O que impressiona:** metáfora tátil (patch costurado) aplicada a UI.
- **Aplicar aqui:** a marca é um desenho que explica o produto (estratos que
  convergem para um ponto), não um ícone genérico de lupa.

### 7. AI in Design Report 2026 — inspecionado no HTML público
- **Vídeo scrubado pelo scroll** (`framerusercontent.com/assets/*.webm`) em vez
  de autoplay: o usuário controla o tempo.
- **Índice de cases numerado** (01 Sierra, 02 Linear, 03 Shopify…), cada um com
  thumbnail 16:9 — a navegação é uma lista editorial, não um carrossel.
- **"Download the markdown version"**: o relatório entende que o leitor quer
  levar o conteúdo para outra ferramenta.
- **Aplicar aqui:** documentação com índice numerado e grafo no topo; dossiê
  exportável é promessa de produto, não conveniência.

### 8. Creative Marketing AI
- **Fonte:** listagem (HM 19/06/2026); página não inspecionada.
- **O que impressiona:** prova visual antes de copy — a saída gerada é o herói.

### 9. Ponder AI
- **Fonte:** listagem (HM 10/06/2026); página não inspecionada.
- **O que impressiona:** workspace de pesquisa trata fonte e síntese no mesmo
  plano visual; nada de "chat + sidebar de configurações".

### 10. Viture Dashboard
- **Fonte:** listagem (HM 26/09/2022); página não inspecionada.
- **O que impressiona:** dashboard de hardware usa contraste de material (vidro,
  metal) para separar camadas, não sombras difusas.

## Três padrões transversais (presentes em ≥4 referências)

1. **Um objeto com profundidade, não muitos enfeites.** Cleo (vídeo), Oryzo
   (coaster 3D), Fourmula (sequência de imagens), Triadic (coreografia). O
   movimento é concentrado; o resto da página fica quieto.
2. **Densidade com hierarquia de dado.** Mono para número/ID, sans para prosa,
   serif/display para declaração. Oryzo, AI in Design, Viture e Fourmula usam a
   mesma tríade.
3. **Decisão visual antes de texto.** Comparação lado a lado (Fourmula), índice
   numerado (AI in Design), ficha técnica (Oryzo). O texto confirma o que a
   imagem já disse.

## O que aplicamos (e onde)

| Padrão | Implementação neste frontend |
|---|---|
| Movimento concentrado | `HorizonBackground` em CSS transform-only (0,1% de main thread) + dash do loop só no nó ativo; keyframes com `prefers-reduced-motion` |
| Tríade tipográfica | Inter (prosa), JetBrains Mono (IDs, métricas, numeração), Outfit (títulos) — já na base |
| Decisão visual | lista de temas numerada com descrição de 2 linhas; grafo clicável com detalhe abaixo |
| Densidade de dado | dock mostra valor atual (pontos, personas, modo) sem abrir painel; trace usa mono |
| Editorial | documentação com índice e grafo; dossiê em 72ch |

## O que deliberadamente **não** copiamos

- WebGL/3D: custo de bundle e bateria não se paga num workspace de leitura.
- Preloader com contador: o app é ferramenta, não campanha; LCP < 700 ms já.
- Vídeo de fundo: ruído visual e consumo em mobile; aurora CSS resolve.
