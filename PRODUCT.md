# PRODUCT.md — DeepResearch

## O que é

Aplicação web de pesquisa profunda com auditoria por ponto. O usuário descreve
um tema, o sistema formula um plano investigativo com N pontos, quatro personas
buscam evidência na web em paralelo, um auditor pontua cada ponto contra 12
critérios e só então um redator produz um dossiê com citações rastreáveis.

Não é um chat. É uma esteira de investigação com estados explícitos
(planejamento → busca → auditoria → redação), cada etapa visível e retomável.

## Usuário

- Analista, pesquisador ou gestor que precisa de um dossiê defensável, não de
  uma resposta rápida. Lê em desktop, 1280–1600px, sessões longas.
- Secundário: leitor em mobile consultando um dossiê já pronto.
- Nunca é um operador de infraestrutura: não configura credenciais, webhooks
  ou modelos.

## O que o produto promete, e onde a UI prova

| Promessa | Onde o produto prova na interface |
|---|---|
| "Cada frase tem fonte" | Painel direito de fontes exploradas com favicon, domínio e status por fonte |
| "A auditoria é real, com nota" | Timeline central mostra o auditor com contagem de critérios aprovados e o score do ponto |
| "Se reprovar, dá para refazer" | Ações de refazer busca / reauditar presas ao ponto reprovado |
| "Você vê o raciocínio" | Feed central de raciocínio por agente, com passo expansível e queries executadas |
| "Cada token é medido" | Medidor de tokens da sessão na barra direita (entrada, saída, total, modelo) |

## Referência de paridade

`frontend/references/` contém capturas do Google Gemini Deep Research (gabarito
estrutural) e capturas do próprio app (estado anterior). O gabarito manda em:
estrutura de zona, densidade, anatomia do bloco de reasoning (passo + ícone
abstrato de 24px, accordion, chips de fonte por passo) e posição do painel de
fontes/tokens na lateral direita.

## Fora de escopo

- Backend, pipeline, contratos de API, banco.
- Trocar a identidade cromática: o canvas quente claro + acento violeta é a
  marca do produto e permanece. Logos, ícones de marca e favicons mantêm suas
  cores originais exatamente.
- Tema escuro existe e deve continuar funcionando, mas não é o padrão.
