# Varredura de strings: o que mudou

Base: 293 strings visíveis extraídas de 9 rotas em 1440 e 390, mais o shell
Capacitor (`frontend/android`, `capacitor.config.ts`). O app mobile usa a mesma
base React; as strings nativas são só o nome do app.

## Aplicado

| Arquivo | Antes | Depois |
| --- | --- | --- |
| `App.tsx:872` | Planejador — abrindo a varredura | Planejador: abrindo a varredura |
| `App.tsx:1255` | pipeline em background + travessão | "a pesquisa roda no servidor. O dossiê vai para o webhook configurado." |
| `App.tsx:1019` | não foi concluída com sucesso | "A redação deste relatório não terminou. O plano e as fontes continuam salvos." |
| `Composer.tsx:126` | Plano formulado — novo tema elabora outro plano | Plano formulado. Um novo tema cria outro plano. |
| `LinearTimeline.tsx:586` | {n}/{t} pontos aprovados — redação bloqueada | {n} de {t} pontos aprovados. A redação espera os demais. |
| `LinearTimeline.tsx:340` | reprovou o ponto número {n} por ... — reenviado | reprovou o ponto {n}: {motivo} ({pct}% · {ok}/{min}). Reenviado. |
| `DocsView.tsx:15` | Guia Operacional e Documentação do Deep Research | Como o Deep Research funciona |
| `DocsView.tsx:17` | Manual de referência técnica ... (Checkpoint 1) | As quatro etapas, do plano ao dossiê. |
| `DocsView.tsx:24` | pipeline autônomo e modular desenhado para ... | pega um tema, divide em pontos, busca fontes públicas e audita cada ponto nos 12 critérios |
| `DocsView.tsx:34` | Formula eixos investigativos estruturados, hipóteses falseáveis ... | Divide o tema em pontos e define o que cada um precisa provar. |
| `DocsView.tsx:42` | Varredura concorrente com subconjunto selecionável ... via Jina AI | Quatro personas varrem a web em paralelo: Historiador, Visionário, Cético e Futurista. |
| `DocsView.tsx:50` | Avaliação cumulativa ... vetor estrito de 12 critérios formais | Cada ponto é julgado nos 12 critérios. Se não atingir o limiar, volta para a busca com o motivo. |
| `DocsView.tsx:58` | Consolidação de evidências em dossiê Markdown com citações canônicas verificáveis | Escreve o dossiê em Markdown com a fonte de cada trecho. |
| `DocsView.tsx` | Para obter o máximo proveito da varredura analítica ... | Quanto mais claro o recorte, melhor o plano: diga o período, o lugar ou a decisão que o tema precisa responder. |
| `DocsView.tsx:136` | O sistema realiza a conciliação pública e contábil rigorosa ... | Toda referência do ciclo entra nesta conta: |
| `DocsView.tsx:149` | Registros Legados e Valores Desconhecidos ... zero fictício | Pesquisas antigas e valores desconhecidos: quando a contagem não existe, a tela mostra `não disponível` em vez de zero. |
| `DocsView.tsx:140/146` | corpus obtido com sucesso / consultadas com sucesso | texto obtido pelo Jina Web Reader / Fontes lidas na varredura |
| `SettingsView.tsx` | Configurações e Conexão do Workspace | Configurações |
| `SettingsView.tsx` | Gerencie parâmetros ... sem exigir chave manual no cliente | Chaves dos provedores e da busca ficam no servidor. A sessão abre sozinha, sem chave manual no navegador. |
| `SettingsView.tsx` | Comunicação com o Backend e Sessão | Conexão e sessão |
| `SettingsView.tsx` | O workspace opera integrado ao backend FastAPI com cookies ... | As chaves ficam no servidor e não chegam ao navegador. |
| `SettingsView.tsx` | Parâmetros dos Provedores e Banco Cifrado (AES-128-CBC) | Chaves dos provedores |
| `SettingsView.tsx` | Regra de Precedência RN-10 (Adendo 002) + parágrafo | Qual valor vale: o que está salvo aqui vence o .env. Sem valor salvo, vale o .env. A chave-mestra fica só no ambiente. |
| `SettingsView.tsx` | Parâmetros Registrados e Origem Ativa | Credenciais salvas |
| `SettingsView.tsx` | Origem Ativa / Valor Sanitizado / Atualizado Em | Origem / Valor / Atualizado em |
| `SettingsView.tsx` | Nenhum parâmetro customizado cadastrado ainda no banco cifrado ... | Nenhuma credencial salva. Enquanto isso, valem as variáveis do .env. |
| `SettingsView.tsx` | Salvar alterações no banco cifrado | Salvar credenciais |
| `SettingsView.tsx` | Testar Conexão com API | Testar conexão |

## Recusado (não é slop)

- `ExecutionView.tsx:294` — `Ponto {n} — {ok}/{min} critérios`: travessão é
  separador de dado num badge curto, não pausa explicativa.
- `1. Planejamento (Plan)`, `2. Busca Agêntica (Search)`, `3. Auditoria (Audit)`,
  `4. Redação (Writer)`: o nome em inglês é o stage real do backend e aparece em
  logs e respostas da API. Remover quebraria a correspondência.
- Badge de origem `Banco cifrado`: testei "Salvo aqui" e ficou ambíguo na
  coluna. O nome do armazenamento é mais claro.
- `ReportView.tsx:399` — `—` como marcador de valor ausente.

## Segunda onda: todos os arquivos

Varredura completa depois do guia: 535 strings inventariadas em 31 arquivos
(`tsx`/`ts`, sem testes nem dev harness), revisadas contra o texto que aparece na
tela em 9 rotas × 1440/390. 24 arquivos de produção alterados.

Padrões corrigidos além dos anteriores:

| Antes | Depois |
| --- | --- |
| Pesquisa reprovada na auditoria técnica de qualidade. | A auditoria reprovou esta pesquisa. |
| Planejamento e Decomposição em Eixos Canônicos | Planejamento: o tema vira pontos |
| Síntese Executiva e Redação do Dossiê | Redação do dossiê |
| Auditoria de 12 Critérios — Ponto 3 (Ciclo 2) | Auditoria · Ponto 3 (Ciclo 2) |
| Exibindo parecer da última auditoria disponível enquanto a nova busca está em andamento. | Mostrando a auditoria anterior enquanto a nova busca roda. |
| Investigação bloqueada na auditoria de qualidade: limiar mínimo não atendido. | A auditoria barrou a investigação: os pontos não atingiram o mínimo de critérios. |
| Distribuindo os pontos analíticos entre as personas ativas e preparando as consultas web. O primeiro evento de cada persona aparece aqui assim que a coleta começa. | Distribuindo os pontos entre as personas e preparando as buscas. Cada persona aparece aqui assim que começa. |
| Eixos investigativos do plano / contexto metodológico | Pontos do plano / contexto da pesquisa |
| Subperguntas analíticas / hipóteses a verificar / fontes canônicas prioritárias / critério de conclusão | Subperguntas / hipóteses / fontes prioritárias / quando o ponto está concluído |
| Contabilidade e proveniência de fontes da investigação | De onde vêm as fontes |
| Evidências brutas de leitura indisponíveis para este relatório | Este relatório não guardou as leituras brutas |
| Fontes Utilizadas no Dossiê / Consultadas mas Não Citadas | Fontes citadas no dossiê / Consultadas, não citadas |
| Telemetria indisponível / telemetria parcial | Sem dados de tokens / dados parciais |
| Backend sincronizado — pronto para investigar | Sessão sincronizada. Pode investigar. |
| Credenciais ficam cifradas no servidor; nada de provedor é chamado sem a sua submissão. | As chaves ficam cifradas no servidor. Nenhum provedor é chamado sem você enviar o tema. |
| Status: {report.status} (enum cru) | Status: Concluído / Reprovado / Parcial (via `rotuloStatus`) |
| andamento: ● concluido · 4/4 | Andamento: ● Concluído · 4/4 |
| pipeline_id / callback | ID da pesquisa / Entrega |
| Falha no cálculo local de integridade do artefato publicado. | Não foi possível conferir a integridade do dossiê. |
| Dossiê Concluído / Copiar texto Markdown para a área de transferência | Dossiê concluído / Copiar Markdown |
| Cenários prospectivos e impactos sistêmicos | Cenários futuros e efeitos em cadeia |
| Force o estado atual da web / Preserva o recorte temporal do pedido | Só o que está no ar hoje / Mantém o período que você pediu |

Acrescentado `rotuloStatus()` em `utils/texto.ts` para que nenhum estado do
servidor vaze em inglês ou snake_case. Ajustado o fixture do harness que exibia
"10/9 critérios" (limiar real é 12).

Mantidos: títulos de aba (`Pesquisa — Deep Research`), marcador `—` de valor
ausente, chaves de ambiente (`N_PONTOS`, `WEBHOOK_HMAC_SECRET`) e intervalos de
ano (`2010–2026`), que usam travessão como tipografia, não como pausa.

Testes que citavam a copy antiga foram atualizados:
`sources-accounting`, `gdr-exec-step`, `gdr-timelog-step`,
`docs-history-remediation`, `plan-settings-polish`.

## Evidência anterior


- `tsc --noEmit` exit 0; `npm run build` ok (189,74 kB / gzip 53,71).
- `erros.test.ts` 10/10, `historico-storage.test.ts` 3/3.
- `impeccable detect` 0 em `/`, `#docs`, `#settings`.
- 0 travessões no texto renderizado de `#docs` e `#settings`; overflow 0 em
  1440 e 390; backend 8010 no ar durante a checagem.
