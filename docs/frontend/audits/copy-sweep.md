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

## Evidência

- `tsc --noEmit` exit 0; `npm run build` ok (189,74 kB / gzip 53,71).
- `erros.test.ts` 10/10, `historico-storage.test.ts` 3/3.
- `impeccable detect` 0 em `/`, `#docs`, `#settings`.
- 0 travessões no texto renderizado de `#docs` e `#settings`; overflow 0 em
  1440 e 390; backend 8010 no ar durante a checagem.
