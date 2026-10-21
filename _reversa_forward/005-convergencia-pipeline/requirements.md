# Requirements: Convergência do pipeline e entrega segura do relatório

> Identificador: `005-convergencia-pipeline`
> Data: `2026-10-20`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 decisões aprovadas; 🟡 premissas técnicas; 🔴 exceções operacionais ainda pendentes.
> Execução autônoma autorizada: requirements até sync, sem deploy, commit ou mudanças em produção.

## 1. Resumo executivo

Implementar as diretrizes documentais aprovadas em 2026-10-19, ligando investigação, auditoria e redação nos caminhos HTTP efetivamente usados. Cada persona lê material integral e entrega aprendizado rastreável. Quatro análises da mesma rodada precedem merge e auditoria. Quatro reprovações encerram busca, não a entrega. Relatórios honestos de limitações podem ser curtos e não exigem fontes inexistentes.

## 2. Contexto a partir do legado

Definições usadas neste documento:

- **SERP** (*Search Engine Results Page*): resultados resumidos de busca usados pelo Scout do briefing, sem leitura integral das páginas. **SSRF** (*Server-Side Request Forgery*): requisições induzidas pelo servidor a destinos indevidos; a proteção outbound impede esse acesso. **LLM** (*Large Language Model*): modelo de linguagem que formula queries e análises.
- **Persona investigativa**: perspectiva de análise executada por um dos quatro workers (`historian`, `skeptic`, `pragmatist`, `futurist`). **Rodada**: ciclo de investigação e auditoria de um ponto. **Merge**: consolidação persistida das quatro análises válidas da mesma rodada, anterior à auditoria; não é novo estado.
- **Estados e entidades**: `ResearchPoint.status = AUDIT_CAVEAT` significa ponto conclusivo com ressalvas após o teto de reprovações; `AUDIT_APPROVED` significa ponto conclusivo aprovado. `Research.status = WRITE` é etapa do Redator, não terminal nem garantia de relatório pronto; `DONE` é conclusão terminal com relatório persistido. `Evidence` é armazenamento legado de evidência atribuída a ponto/persona/fonte, com trecho e afirmação sujeitos à verificação de citação; sua existência não prova veracidade por si só. `Report` é saída persistida da pesquisa em `content_markdown`. Referências: `app/models/domain_models.py`, `app/audit/domain.py` e `app/services/pipeline/worker.py`.
- **Síncrono/assíncrono**: no contrato com o cliente, criação e revisão devolvem briefing pronto na resposta HTTP; investigação executa internamente em background. Uso interno de operações assíncronas não torna a geração do briefing assíncrona para o cliente.

| Fonte | Trecho relevante | Confidência |
|---|---|---|
| `_reversa_sdd/prd.md#4-escopo-in` | Briefing, identidade e decisão única do operador, com notas históricas de precedência | 🟢 |
| `_reversa_sdd/sdd/briefing.md#12-segurança-e-privacidade` | Autenticação e privacidade preservadas | 🟢 |
| `_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md#1-contrato-de-coleta-integral-jina-e-limpeza-de-html` | Dez corpos integrais limpos, primeira query obrigatória, até três queries distintas | 🟢 |
| `_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md#2-persistência-individual-barreira-de-sincronização-e-merge-das-4-personas` | Quatro resultados persistidos por ponto e rodada antes do merge persistido e auditoria | 🟢 |
| `_reversa_sdd/addenda/diretrizes-20261019-workers-jina-briefing.md#3-gestão-de-ciclo-de-vida-da-auditoria-e-teto-de-tentativas` | Quatro tentativas totais e Writer após todos conclusivos | 🟢 |
| `_reversa_sdd/addenda/004-modulo-redator-webhook.md#resumo-da-entrega` | Writer e persistência de relatório existentes; aprovação histórica não comprova esta alteração | 🟢 |

Evidência observada em disco, não regra de produto: existem dois caminhos de execução, `app/services/research.py` e `app/investigation/service.py`. O segundo não chama Writer após `WRITE`. O primeiro usa cinco fontes por consulta, cortes de conteúdo e não persiste síntese individual. `research_step_results` não registra rodada. O Writer exige evidência, link e 200 palavras incondicionalmente e interpreta negrito como marcador de lista. Preservar os diffs locais capturados em `scratch/forward-005-baseline`.

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---|---|---|
| Operador | Receber briefing pronto e relatório honesto | Iniciar investigação direta ou revisar uma única vez |
| Personas investigativas | Aprender e atribuir fontes por ponto | Consultar páginas e persistir análise mesmo com cobertura incompleta |
| Auditor | Avaliar material consolidado da rodada correta | Reprovar até quatro tentativas, sem aceitar persona ausente |
| Redator | Sintetizar evidências e explicitar limites | Entregar relatório após conclusões com ressalvas, inclusive sem conteúdo aproveitável |

## 4. Regras de negócio novas ou alteradas

1. **RN-501, coleta:** 🟢 Tool investigativa solicita dez resultados com corpos integrais, faz limpeza antes da entrega e preserva URL, título e associação à consulta. Snippet ou descrição não substituem corpo. Não há corte silencioso de corpo nem busca alternativa apresentada como dez leituras Jina. Origem: adendo normativo §1. Tipo: alterada.
2. **RN-502, autonomia limitada:** 🟢 Persona e ponto orientam a primeira query formulada pelo modelo. Uma busca é obrigatória; até três queries distintas por persona/ponto/rodada; repetição da mesma query não abre novo orçamento. Retries técnicos são internos ao transporte. Parada antecipada após aprendizado é válida. Tipo: alterada, adendo §1.5.
3. **RN-503, resultado:** 🟢 Sucesso implica análise estruturada não vazia, preservação do aprendizado relevante e fontes realmente lidas. Erro técnico não é análise válida. Fontes inventadas ou URLs nunca lidas são rejeitadas. Tipo: alterada, adendo §1.4.
4. **RN-504, barreira:** 🟢 Persistir cada persona antes do merge. Exigir as quatro personas distintas, com sucesso e resultado não vazio, no mesmo ponto e rodada. Dados antigos, duas linhas da mesma persona ou diagnóstico de falha não completam barreira. Tipo: alterada, adendo §2.
5. **RN-505, merge:** 🟢 Persistir consolidação identificável antes de chamar auditor. Manter análises e atribuição, contradições e lacunas; concatenação estruturada sem gerar fatos novos é aceitável. Auditor consome somente rodada correspondente. Tipo: nova, adendo §2.3.
6. **RN-506, tentativas:** 🟢 Máximo de quatro ciclos de investigação e auditoria por ponto, incluindo inicial. Quarta reprovação produz `AUDIT_CAVEAT`; todos pontos devem estar conclusivos antes de `WRITE`. Falha técnica de persona não é reprovação do auditor e não pode acelerar esse teto. Tipo: alterada, adendo §3.
7. **RN-507, redação:** 🟢 Todos pontos conclusivos disparam Writer e persistência de `Report`, inclusive todos com ressalvas. Ausência de conteúdo aproveitável permite relatório curto por ponto, sem mínimo de 200 palavras, sem links/evidências fictícios. Afirmação factual exige fonte conhecida. Declaração de limitação não exige fonte inexistente. Aprovação humana registrada no intake/diagnóstico da execução `fdd70d5c-9133-41e3-869c-3f27fec06655`. Tipo: alterada, complementa RF-401/RF-402 da 004.
8. **RN-508, guardrails:** 🟢 Negrito não equivale a lista factual. Propostas não factuais não devem sofrer esse falso positivo; texto factual em negrito continua sujeito a citação. Não isentar arbitrariamente todo trecho com rótulo ou toda URL quando não houver evidência. Tipo: alterada, diagnóstico do Writer e princípio I.
9. **RN-509, briefing:** 🟢 Manter criação 201 e revisão 200 síncronas, Scout SERP-only, revisão única autoaprova e dispara investigação em background, alternativa ao investigate 202. Sem novo polling ou endpoint approve. Tipo: preservada, adendo §4.
10. **RN-510, segurança:** 🟢 Fontes e entrada do operador são dados não confiáveis. Preservar anti-SSRF, ausência de segredos/prompts internos nos resultados, sanitização e callbacks existentes. Sem novo modelo, provedor ou dependência por conveniência. Tipo: preservada, princípios I, II e IV.

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|---|---|---|---|---|
| RF-501 | Entregar dez corpos limpos sem cortes silenciosos à investigação | Must | Fixture de dez páginas com final marcador além de 100000 caracteres chega integral ao contexto; boilerplate removido e URLs preservadas | 🟢 |
| RF-502 | Query inicial pelo modelo, até três distintas e parada cedo | Must | Chamadas gravadas mostram primeira query do modelo, nenhuma quarta query, duplicata não gera busca adicional e sucesso sem busca é rejeitado | 🟢 |
| RF-503 | Persistir sínteses não vazias por persona e rodada | Must | Banco isolado contém quatro linhas válidas antes do merge; nulo/branco, fonte não lida e falha não contam | 🟢 |
| RF-504 | Executar e persistir merge antes de auditoria | Must | Auditor não é chamado com 3/4 nem linhas de outra rodada; registro do merge referencia quatro resultados e preserva conteúdos | 🟢 |
| RF-505 | Encerrar após quarta reprovação e continuar redação | Must | Quatro chamadas de auditor por ponto, nenhuma quinta investigação; Writer só após todos conclusivos | 🟢 |
| RF-506 | Produzir relatório limitado sem evidências aproveitáveis | Must | Relatório curto com seção por ponto é persistido em `DONE`, sem fato ou URL inventado, inclusive com zero linhas de Evidence | 🟢 |
| RF-507 | Corrigir falso positivo de Markdown sem liberar fatos sem fonte | Must | Proposta didática do diagnóstico não é tratada como lista; fatos sem citação em prosa, negrito, lista e tabela continuam negativos | 🟢 |
| RF-508 | Ligar caminho modular e legado à redação conclusiva | Must | Testes dos entrypoints reais comprovam Report e DONE, não apenas chamada de helper; sem reconstruir frontend | 🟢 |
| RF-509 | Preservar contratos HTTP síncronos e decisão única | Must | Regressões API mostram briefing concluído na resposta, 409 em revisão repetida, 202 somente investigação | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|---|---|---|---|
| Segurança | Sanitizar saídas antes da persistência; URLs de citação pertencem às fontes; sem dados externos executáveis | Princípios I e II | 🟢 |
| Concorrência | Resultados append-only por rodada; sem compartilhar transação aberta durante rede; barreira baseada em banco, não só gather | Princípio IV e adendo §2 | 🟢 |
| Integridade | Evoluir schema sem apagar registros históricos; migração local testada com downgrade sem manipular produção | Resultado atual não possui rodada | 🟡 |
| Eficiência | Stdlib e dependências existentes; sem novo framework de agentes, busca ou parser | Escopo mínimo da evolução | 🟡 |
| Observabilidade | Eventos e relatórios com estados, contagens e erros seguros, sem corpos de páginas ou raciocínio privado nos logs | Princípio II | 🟢 |
| Validação | Testes determinísticos com HTTP/LLM simulados e banco efêmero; identificar claramente ausência de execução com provedores live | Evitar confundir fixtures com pesquisa real | 🟢 |

Referência existente para RN-502 (Q-015), não nova regra ou orçamento: a emenda da Feature 002 no Princípio IV (`.reversa/principles.md:33`) estabelece 90s por chamada LLM/Jina, 600s globais por worker/persona e até três tentativas técnicas de transporte, distintas do limite de queries. Defaults observados: `app/investigation/llm_binding.py:26`, `app/investigation/tools.py:110` e `app/investigation/worker.py:19`. A referência não redefine Scout nem timeout HTTP do briefing, não prova aplicação em todos os caminhos e não registra nova aprovação humana.

## 7. Critérios de Aceitação

```gherkin
Cenário: RF-501 coleta completa e limpa
  Dado dez páginas com header, footer, nav, script e texto informativo longo
  Quando a ferramenta entrega material ao worker
  Então os dez corpos completos e suas URLs estão presentes sem os elementos descartados

Cenário: RF-502 busca obrigatória e orçamento
  Dado uma persona e um ponto
  Quando o modelo formula queries, repete uma e tenta uma quarta distinta
  Então a primeira query é executada e no máximo três distintas chegam à ferramenta
  E uma resposta final anterior à primeira busca não é aceita

Cenário: RF-503 e RF-504 barreira da rodada
  Dado três sucessos atuais e um sucesso de rodada anterior
  Quando o orquestrador tenta auditar
  Então não existe merge válido nem chamada ao auditor
  Quando a quarta persona atual persiste resultado válido
  Então o merge é persistido antes da auditoria e mantém quatro atribuições

Cenário: RF-505 quatro reprovações não bloqueiam Writer
  Dado dois pontos com quatro reprovações cada
  Quando ambos se tornam AUDIT_CAVEAT
  Então nenhuma quinta rodada é iniciada
  E só então Writer recebe todos pontos conclusivos

Cenário: RF-506 entrega honesta sem evidência
  Dado todos pontos conclusivos sem conteúdo aproveitável e sem URLs verificadas
  Quando a redação termina
  Então existe Report curto com seção e limitação por ponto e Research DONE
  E não há preenchimento factual nem links inventados

Cenário: RF-507 formato não autoriza fatos
  Dado proposta didática imperativa não factual e afirmações factuais sem citação
  Quando o guardrail interpreta prosa, negrito, listas e tabelas
  Então a proposta não é rejeitada por marcador falso de lista
  E afirmações factuais sem fonte são rejeitadas inclusive em negrito

Cenário: RF-508 persistência pelos dois entrypoints
  Dado investigação modular e pesquisa legada executadas isoladamente
  Quando todos pontos atingem conclusão
  Então cada caminho persiste exatamente um Report e estado DONE

Cenário: RF-509 briefing síncrono e decisão única
  Dado briefing criado com SERP e LLM simulados
  Quando criar ou revisar
  Então a resposta contém briefing concluído com 201 ou 200, sem geração em background
  E revisão inicia investigação uma vez e a segunda revisão recebe 409
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|---|---|---|
| RF-501 a RF-509 | Must | Diretrizes e defeitos aprovados, rastreáveis e necessários à entrega |
| Provedores adicionais, mudança de modelo e frontend novo | Won't | Não necessários nem autorizados |
| Deploy e reparo de pesquisas de produção | Won't | Execução local apenas |

## 9. Esclarecimentos

Nenhuma nova entrevista. Pedido explícito de execução autônoma desde requirements até sync utiliza decisões já aprovadas. Premissas não aprovadas ficam identificadas em `questions.md` e no roadmap; não são registradas como respostas humanas.

## 10. Lacunas

- 🔴 [DÚVIDA] Política para menos de dez corpos, páginas ilegíveis e janela de contexto insuficiente. Premissa conservadora provisória: explicitar falha de coleta/contexto sem truncar, fabricar leituras ou promover resultado parcial para sucesso. Não definir nova recuperação automática ou orçamento.
- 🔴 [DÚVIDA] Recuperação de falha fatal individual de persona. Premissa provisória: persistir erro seguro, preservar resultados válidos e impedir merge/auditoria; sem contá-la como reprovação nem como quarta análise.
- 🟡 Protocolo concreto Jina: documentação pública do site descreve cinco resultados padrão; fonte oficial `src/api/searcher.ts` aceita `num`/`count` até 20. Solicitar dez explicitamente pelo Search existente é decisão técnica verificável com MockTransport, não garantia do provedor nem adoção compulsória de Reader. Execução com chave real e proxy configurado fica não comprovada sem autorização e credenciais seguras.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-10-20 | Início do ciclo autônomo para implementação, sem reabrir feature 004 ou apagar diffs locais | Reversa |
| 2026-10-20 | Emenda editorial Q-003/Q-016 e referência existente Q-015, sem nova regra, aprovação humana ou resolução de Q-501/Q-502 | Reversa |
