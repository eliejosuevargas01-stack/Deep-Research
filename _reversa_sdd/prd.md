# PRD: Módulo de Briefing (Backend)

> Selo 🟢 CONFIRMADO. Documento de Produto ancorado exclusivamente nos requisitos e decisões aprovados pelo operador em 2026-10-16.
>
> **Aviso de vigência documental:** Este PRD registra a concepção original da Feature 001 (Módulo de Briefing). Conforme os requisitos vigentes da Feature 002 (`_reversa_forward/002-investigacao-personas/requirements.md:134-137,231`), decisões de produto sucessoras superdimensionaram e ajustaram fluxos: (1) a reabertura de briefing aprovado foi descontinuada (retornando HTTP 409 em `POST /briefings/{research_id}/reopen` com status aprovado definitivo); (2) o endpoint de edição manual direta de lista de pontos foi substituído por revisão única assistida via `PATCH /briefings/{research_id}` com nota de feedback (`note`). As especificações originais da Feature 001 são preservadas abaixo como histórico com notas de vigência, sem antecipar a implementação de mudanças futuras de escopo (como a extinção de `/approve` de C8).

**Versão:** 1.0  
**Data:** 2026-10-11  
**Autor:** reversa-drafter  
**Status:** planejado; requisitos de produto aprovados, documento ainda sujeito a revisão  

---

## 1. Problema

🟢 O operador precisa definir e aprovar quais pontos uma pesquisa investigará antes da execução. Este módulo transforma um tema em proposta de foco, com controle de edição, aprovação e reabertura. Não responde ao tema nem inicia investigação. Essa necessidade deriva das decisões do usuário; não representa medição ou diagnóstico do código atual.

### Quem sente
🟢 O operador de pesquisa que precisa direcionar o escopo da investigação e os módulos consumidores a jusante que necessitam de um plano de pesquisa estável e aprovado.

---

## 2. Personas-alvo

- 🟢 **Operador de Pesquisa**: Usuário que submete o tema, revisa os pontos de foco propostos pela IA, edita/reordena e decide quando aprovar ou reabrir.
- 🟢 **Pipeline de Pesquisa (Consumidor futuro)**: Módulo posterior do backend que consome os pontos aprovados para iniciar a coleta profunda.

---

## 3. Métricas de sucesso

| Métrica | Unidade | Alvo | Prazo |
|---|---|---|---|
| 🟢 Conformidade de pontos gerados | % de briefings com 3 a 7 pontos (alvo 5) | 100% | Imediato |
| 🟢 Isolamento de busca externa | Chamadas SERP sem falhas / simultâneas por geração | 1 / máximo 1; até 4 tentativas sequenciais se houver falha | Na verificação da feature |
| 🟢 Zero vazamento de segredos | Ocorrências de chaves em logs/APIs | 0 | Imediato |

---

## 4. Escopo (in)

- 🟢 Validação estrita do tema (3 a 300 caracteres).
- 🟢 Uma única tool SERP via Jina, sem garantia de Google exclusivo, uma chamada por vez e sem leitura de páginas. Decisão de 2026-10-11 aceita parser tolerante (`title`, `url`, `description`; extras ignorados) e timeout Jina/LLM 30s configurável por tentativa. `X-Respond-With: no-content` tem evidência documental; resposta real não foi verificada.
- 🟢 Carregamento de system prompt diretamente de arquivo na pasta de prompts a cada geração. Caminho exato é decisão técnica, não regra herdada.
- 🟢 Geração de rascunho com 3 a 7 pontos focais (visando 5 como média/alvo habitual).
- 🟢 Edição e ajuste de rascunho: o operador envia tema -> scout gera rascunho -> operador envia feedback -> scout formula nova query com tema + feedback e ajusta pontos -> auto-aprova e avança. mantendo a restrição de 3 a 7 pontos. *(Nota de vigência: Requisito original da Feature 001 supersedido pelos requisitos vigentes de `_reversa_forward/002-investigacao-personas/requirements.md:136,231`, que extinguiram a edição manual de lista em favor de revisão única assistida via `PATCH /briefings/{research_id}` com campo `note`.)*
- 🟢 Aprovação definitiva: uma vez aprovado, o briefing nunca mais volta a ser rascunho (reabertura proibida com HTTP 409). Iniciar investigação aprova em etapa única. conteúdo aprovado e bloqueia edição direta; reabertura explícita retorna ao rascunho e libera edição. Aprovar ou reabrir não inicia pesquisa. *(Nota de vigência: A reabertura de briefing aprovado foi supersedida pela Feature 002 em `_reversa_forward/002-investigacao-personas/requirements.md:135,231`, tornando a aprovação definitiva e retornando HTTP 409 em tentativas de reabertura; a aprovação implícita de C8 permanece futura.)*
- 🟢 Retentativa automática sequencial de até 4 tentativas totais em falhas transitórias externas (SERP ou LLM), com reuso da SERP bem-sucedida em falhas de LLM.
- 🟢 Exposição de briefing aprovado via endpoint/consulta segura.

---

## 5. Não-objetivos (out)

- 🟢 Leitura de páginas completas, web scraping profundo ou Jina Reader (`r.jina.ai`).
- 🟢 Múltiplas ferramentas de busca, SerpAPI, DuckDuckGo ou fallbacks de provedores alternativos.
- 🟢 Execução de pesquisa profunda, workers de persona ou redação de relatórios.
- 🟢 Interface gráfica de usuário (frontend).
- 🟢 Alteração de contratos globais legados de pesquisa antes de sua respectiva modularização.

---

## 6. Restrições

| Tipo | Descrição |
|---|---|
| 🟢 Técnica | Backend modular; stack e reutilização de infraestrutura são decisões técnicas do plano, não fonte de regras funcionais. |
| 🟢 Provedor de Busca | Jina Search API (`s.jina.ai`) exclusiva. |
| 🟢 Concorrência e Retentativa | Uma chamada ativa por vez na geração. Máximo 4 tentativas totais por operação que falhar (inicial e 3 retentativas); não repetir operação bem-sucedida. |
| 🟢 Segurança | Chaves de API (`JINA_API_KEY`, chaves LLM) nunca retornadas em payloads ou expostas em logs. *(Nota de auditoria: Classificação inferida. Omissão em schemas e sanitização de exceções em `app/briefing/schemas.py:5` e `app/briefing/serp_client.py:19-23` tratam payloads e erros de busca conhecidos, mas não constituem garantia global comprovada em todo o sistema de logging.)* |

---

## 7. Dependências externas

- 🟢 Jina Search API (`https://s.jina.ai/`).
- 🟢 Provedor LLM compatível com o módulo de completude da aplicação.

---

## 8. Riscos

| Risco | Impacto | Probabilidade | Mitigação proposta |
|---|---|---|---|
| 🟢 Oscilação na API Jina Search | Alto | Média | Retentativa automática com até 4 tentativas totais e mensagem de erro 503 segura. |
| 🟢 Resposta do agente fora da faixa 3 a 7 pontos | Médio | Não medida | Rejeitar saída inválida sem publicar rascunho parcial. Falha de parse/conteúdo fora de 3..7 consome tentativa do teto de 4 tentativas totais e reutiliza SERP; esgotadas as 4 tentativas, briefing é marcado FAILED sem rascunho inválido. Requisito de pontos de foco sem conclusão permanece orientado pelo prompt; não há julgador semântico automático nem retry extra por qualidade/conclusividade. |
| 🟢 Validação de pontos <3 ou >7 pontos | Baixo | Alta | Validação 422 na API de edição preservando a versão anterior intacta. *(Nota de vigência: Validação presente nos schemas de domínio, mas endpoint HTTP de lista manual supersedido por `_reversa_forward/002-investigacao-personas/requirements.md:136,231` em favor de `PATCH` com `note`.)* |

---

## 9. Critérios de aceite (alto nível)

- 🟢 **Dado** um tema válido, **Quando** o operador solicita a criação do briefing, **Então** o sistema obtém resultados SERP via Jina, sem leitura de páginas, aciona a IA com o prompt de arquivo e grava rascunho com 3 a 7 pontos. Sem falhas, há uma busca; falhas podem causar até 4 tentativas sequenciais.
- 🟢 **Dado** um rascunho de briefing, **Quando** o operador edita pontos mantendo entre 3 e 7 itens, **Então** a nova versão é salva; se enviar <3 ou >7, o sistema rejeita com 422. *(Nota de vigência: Critério histórico da Feature 001 supersedido pela Feature 002 em `_reversa_forward/002-investigacao-personas/requirements.md:136,231`.)*
- 🟢 **Dado** um briefing aprovado, **Quando** o operador solicita reabertura, **Então** o briefing retorna ao estado de rascunho permitindo edições. *(Nota de vigência: Critério histórico da Feature 001 supersedido pela Feature 002 em `_reversa_forward/002-investigacao-personas/requirements.md:135,231`, que formalizou HTTP 409 na reabertura de aprovado.)*

---

## Pendências de cobertura

- 🟢 Regras de produto aprovadas: tema 3–300, briefing 3–7 em geração/edição/aprovação, alvo habitual 5, reabertura e até 4 tentativas por operação.
- 🟢 Escolhas de T003 resolvidas pelo usuário em 2026-10-11: SERP Jina sem motor exclusivo, parser tolerante e timeout 30s configurável. Evidência documental não substitui teste da integração; exemplos sintéticos não comprovam resposta real.
- 🟢 Rotas, autenticação, persistência, timeouts e erros devem ser congelados no plano; não são fatos de uma implementação entregue.

## Fontes e rastreabilidade

- `_reversa_forward/001-modulo-briefing/requirements.md`, RN-01–RN-07, RF-01–RF-10 e seção 9 (esclarecimentos).
- Decisão explícita do usuário: criar PRD e spec somente para este módulo a partir dos requisitos aprovados.
- Código e documentação Reversa antiga não foram usados como fonte de regras de produto.
