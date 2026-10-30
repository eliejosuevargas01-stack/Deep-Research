# Erros do frontend: um aviso, texto humano

Regra: toda falha visível passa por `utils/erros.ts` e `components/ErrorNotice.tsx`.
O aviso diz **o que falhou**, **o que aconteceu com o trabalho** e **o próximo
passo**. Código HTTP, nome de provedor e stack ficam em "Detalhes técnicos".

## Superfícies cobertas

| Superfície | Onde | Recuperação |
| --- | --- | --- |
| Sessão inicial | `App.tsx` (`sessionBootstrapError`) | Tentar de novo, Abrir Configurações |
| Planejamento | `App.tsx` (`planningError`), `PlanningView` | Tentar de novo (reenvia o tema) |
| Execução | `ExecutionView` (`falhaDaExecucao`) | Repetir busca/auditoria ou escrever dossiê |
| Queda do SSE | `ExecutionView` (`streamError`) | Reconectar |
| Fontes do relatório | `SourceBreakdown` | Carregar de novo |
| Credenciais (lista) | `SettingsView` | Carregar de novo; suprimido quando a sessão já falhou |
| Credenciais (gravação) | `SettingsView` | Salvar de novo, com chave e motivo nos detalhes |
| Andamento assíncrono | `App.tsx` | Consultar de novo |
| Histórico local bloqueado | `historyService` → `App.tsx` | Aviso dispensável |
| Andamento do histórico | `HistoryView` | Atualizar andamento |
| Dossiê incompleto | `ReportView` | Informativo |
| Exceção de render | `ErrorBoundary` | Recarregar o app |

## Textos por status

| Situação | Título | Mensagem |
| --- | --- | --- |
| Rede fora | Sem conexão com o servidor | Confira sua internet e tente de novo. |
| 401 | Sua sessão expirou | Recarregue a página para entrar de novo. Suas pesquisas continuam salvas neste navegador. |
| 404 | Não encontramos essa pesquisa | Ela pode ter sido apagada. Abra o Histórico e escolha outra. |
| 422 | Faltou informação para continuar | Confira os campos indicados e envie de novo. |
| 429 | Muitas tentativas em pouco tempo | Espere um minuto e tente de novo. |
| 500 | O servidor travou no meio do caminho | Nada foi perdido. Tente de novo. Se repetir, copie os detalhes técnicos e avise o suporte. |
| 502/503 | O serviço está fora do ar | Costuma voltar em minutos. Tente de novo daqui a pouco. |
| 504/timeout | A resposta demorou demais | Tente de novo. Se repetir, reduza o número de pontos da pesquisa. |
| provedor de IA | O provedor de IA não respondeu | O que já foi coletado continua salvo. Tente de novo em instantes. |
| fallback | Não foi possível {ação} | Tente de novo. Se continuar, veja os detalhes técnicos. |

Nenhum texto de usuário usa "backend", "FastAPI", "HTTP", "stack" nem
"com sucesso". Esses termos só aparecem dentro de "Detalhes técnicos".

## Evidência

- `node --import tsx src/tests/erros.test.ts` → 10/10.
- `node --import tsx src/tests/historico-storage.test.ts` → 3/3.
- Fluxo real com `/app/session` em 500: aviso aparece, compositor desabilita,
  nenhum POST de plano sai, retry reativa o compositor.
- Fluxo real com `/api/v1/plan` em 422: "Faltou informação para continuar",
  campo e motivo nos detalhes, retry gera plano.
- `impeccable detect` → 0 nas rotas testadas; sem overflow em 390/768/1440;
  nenhum texto abaixo de 12px no aviso; contraste no escuro 10,85:1.
