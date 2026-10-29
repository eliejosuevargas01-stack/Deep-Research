# Delta de paridade vs. referência (rodada 2)

A rodada 1 fechou o que era **mensurável por sonda** (contraste, piso tipográfico,
overflow, alvos, tema). Não fechou **arquitetura de tela**. Comparando as capturas
do gabarito (`frontend/references/13-20-03 … 13-23-27`) com o app em `:3002`, as
divergências abaixo são estruturais, não cosméticas.

## D1. O painel direito é um inspetor permanente; a referência é um painel flutuante com modo

Referência (`13-21-45`, `13-22-52`, `13-23-03`):

- painel flutuante sobre a conversa (cantos ~16-24px, sombra), não uma coluna do grid;
- cabeçalho próprio: título da pesquisa + alternador **"Mostrar razonamiento" /
  "Fuentes exploradas"** + fechar (X);
- conteúdo mostra **um** modo por vez (raciocínio OU fontes), não seções empilhadas.

App hoje: coluna fixa de 360px sempre visível, com 4 seções empilhadas —
`TOKENS DA SESSÃO`, `STATUS` (3 pontos, 4 personas, ciclo, pontos coletados, ID,
auditoria), `FONTES EXPLORADAS`, `ESCOPO`. Nenhuma dessas seções existe na referência.

## D2. A linha do passo tem três rótulos; a referência tem um

Referência: ícone + **uma frase densa** (persona inline, ex.: "Historiador —
investigando …") + chevron para expandir. Sem coluna de hora, sem chip de persona,
sem parágrafo de resumo.

App hoje: coluna de hora (`00:02:00`, 58px), chip de persona (`Historiador`),
título de ação, parágrafo de análise, chips de fonte e "N páginas lidas",
toggle "ver reasoning". Altura de linha 72-96px contra ~44px da referência.

## D3. O composer carrega uma faixa de status e uma barra inferior paralela

Referência: um composer único (pill), com `+`, pill "Deep Research", seletor de
modelo, enviar; rodapé só com o aviso legal.

App hoje: composer + faixa `1 ponto • 4 pessoas • Auto • Rigor 11/12` +
`Enter planeja / Shift+Enter nova linha` + contador `0/500` + aviso, e **outra**
barra fixa (`Parâmetros`, `Aparência`, `Atalhos`, `Sessão`). Duas barras para a
mesma tarefa.

## D4. A navegação esquerda não tem histórico

Referência (`13-20-03`): logo, pill "Nuevo chat", destinos, seção de cadernos,
filtro e **lista de conversas**. App hoje: `Sessão ativa`, 3 itens de investigação,
2 de sistema e um rodapé com "Dados ficam neste navegador" — sem histórico.

## D5. Tema

As capturas do gabarito são escuras (`#131314`). O produto tem contrato próprio
(`DESIGN.md`: canvas `#FBFCF9`, acento `#6D28D9`). **Não** é tratado como defeito
nesta rodada: mudar o tema é decisão de marca, não correção de paridade estrutural.

## Escopo desta rodada

D1, D2, D3, D4. Cada frente em worktree própria, arquivos disjuntos, merge
sequencial e reauditoria com a mesma sonda da rodada 1.
