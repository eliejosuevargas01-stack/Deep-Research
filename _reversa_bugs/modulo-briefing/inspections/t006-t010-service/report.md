# Sprint 5 — T006/T010: contratos e fluxo do serviço

## Veredicto

**FINDINGS** — 1 achado confirmado LOW; critical 0, high 0, medium 0, low 1. Sem correções, bugs novos ou atualização de views. `promoted_to: null`.

## Preflight e mapa

Repositório `/root/projects/deep-research`, branch `main`, árvore previamente suja. AGENTS.md contém mapa legado; produto vigente vem de `_reversa_forward/001-modulo-briefing/requirements.md`. `.reversa/state.json` define pt-BR e `_reversa_sdd`; active-requirements resolve feature `001-modulo-briefing`, estágio coding. Config lida: `allowLegacyEdits: true`; não alterada. Recorte exclusivo: contratos e fluxo de `app/briefing/service.py`, 97 linhas.

Fontes: requirements.md:51–60,67–70,161–162; roadmap.md:23,85–160; data-delta.md:78–105; actions.md:45,65–66; audit/cross-check.md (histórico documental, não evidência de execução própria). Código: service.py; helpers consumidos domain.py, prompt_loader.py, serp_client.py; instrução app/prompts/briefing.md. Testes: tests/test_briefing_generation.py. Dados: um Briefing em memória; SERP e payload locais; saída validada vira tupla de pontos; sem storage.

## Spec → código → checks

Caminhos de spec nesta tabela relativos à pasta da feature; caminhos de código relativos à raiz.

| Contrato | Implementação | Evidência executada |
|---|---|---|
| roadmap:91–105,155: assinatura/defaults, limites e zero I/O | service:30–36,54–65; domain:31–37,94–104 | generation:37–59; probe de int gigante abaixo |
| roadmap:124–126: criação, prompt síncrono, validação e busca única | service:65–75; prompt_loader:10–23 | generation:20–43,61–115,347–356; 29 testes OK |
| roadmap:114–119,127: LLM sequencial, SERP reutilizada, deadline versus TimeoutError interno | service:76–96 | generation:117–162,193–249,297–307; testes de timeout interno e externo OK |
| roadmap:118–119: erros desconhecidos/cancelamento propagam | service:66–75,82–96; captura limitada | generation:95–103,218–249,309–317 OK |
| roadmap:116,158; data-delta:86,103: lista integral, cerca única opcional, 3–7 pontos | service:39–51,93–96; domain:107–131 | generation:164–191,251–267,358–362; probe adicional 8 formas OK |
| roadmap:128; data-delta:87: erro final fixo seguro | service:12–15,70–75,97 | generation:134–147,347–380 OK; inspeção estática não encontra logs nem payload bruto nos erros tratados |
| roadmap:132: sequencial por invocação, sem lock global | service:80–84; adapter:58–61 (lock por instância) | generation:269–295 OK; ausência de lock no serviço por leitura integral |
| roadmap:105; data-delta:89: mesmo id, versão via domínio | service:65,94,97; domain:127–139 | generation:364–386 OK |

O teste generation:283–295 usa cancelamento na primeira tentativa, portanto isoladamente não prova várias retentativas sem sobreposição. Fluxo estático do `for` com `await` encadeado sustenta garantia por invocação. Canary em generation:388–398 não é enviado ao serviço; não considerado prova de resistência a vazamento desse canary. Essas limitações de evidência não são defeitos do serviço.

## Achado confirmado

- finding_id: F-contratos-01
- lens: Contratos e fluxo do serviço
- summary: Timeout inteiro negativo muito grande levanta OverflowError, não ValueError contratual.
- confidence: alta
- suspected_severity: low
- evidence: roadmap.md:23,99,104; service.py:33–36; probe executado abaixo.
- signals: operational-risk
- promoted_to: null

**Esperado:** `llm_timeout_s <= 0` é configuração inválida; `ValueError` antes de I/O. **Observado:** `-10**1000` passa checagem de tipo e `math.isfinite` tenta conversão para float, levantando `OverflowError` antes da checagem de sinal. Cadeia completa: int aceito → math.isfinite → conversão não representável → exceção errada. Zero I/O preservado. Não cria FAILED nem retenta, mas viola tipo de erro previsto para configuração inválida. Impacto limitado a valor extremo de configuração, sem perda de dados.

Inteiro positivo `10**1000` também provoca OverflowError antes de I/O. Registrado como observação da mesma fronteira, não como segundo achado: não foi inventado teto adicional de timeout; data-delta.md:99 explicitamente não fixa teto. Nenhum requisito de newline imposto à cerca: ` ```json` e fechamento exatos aceitam lista sem newline; oito formas testadas conforme lista integral, sem extrair fragmentos.

## Execução própria e reprodução

Todos comandos abaixo executados em `/root/projects/deep-research`, sem `.env`, imports do stack DB/provider, pip ou rede real. Testes usam fakes/MockTransport. `python3 -B` evita bytecode implícito; compile explícito escreve somente scratch autorizado.

```sh
cd /root/projects/deep-research
python3 -B -m unittest tests.test_briefing_generation -v
python3 -B -m unittest discover -s tests -p 'test_briefing_*.py'
python3 -B -m unittest tests.test_briefing_domain tests.test_briefing_schemas tests.test_briefing_prompt_loader tests.test_briefing_serp_client tests.test_briefing_validation tests.test_briefing_lifecycle tests.test_briefing_lifecycle_qa
mkdir -p /root/.hermes/profiles/orchestrator/cache/scratch/briefing-verify-pycache
PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/briefing-verify-pycache python3 -B -m py_compile app/briefing/service.py tests/test_briefing_generation.py
git diff --check
```

Resultados: generation **29 OK** (0.162s); suíte briefing **78 OK** (0.261s); baseline anterior **49 OK** (0.087s); py_compile sem saída; bloco compile/suítes/diff exit 0. Contagens sobrepostas, não somadas. Os checks próprios repetiram execução; não atribuídos exclusivamente ao parent.

Probe executado integralmente:

```sh
cd /root/projects/deep-research
python3 -B -c 'import asyncio,json; from app.briefing.service import generate_briefing; events=[]; payload=json.dumps([{"title":"T","description":"D"}]*3)
class S:
 async def search(self,theme): events.append("search"); return []
async def llm(system,user): events.append("llm"); return payload
def loader(): events.append("prompt"); return "system"
async def main():
 for timeout in (-10**1000,10**1000):
  events.clear()
  try: await generate_briefing("valid theme",serp_client=S(),llm_complete=llm,prompt_loader=loader,llm_timeout_s=timeout)
  except Exception as exc: print("negative" if timeout<0 else "positive",type(exc).__name__,str(exc),"io",events)
 for raw,expected in [(payload,True),("```json"+payload+"```",True),("```json\n"+payload+"\n```",True),("```JSON\n"+payload+"\n```",False),("```jsonx"+payload+"```",False),("prefix "+payload,False),(payload+payload,False),("```json"+payload+"``````json"+payload+"```",False)]:
  async def output(system,user): return raw
  result=await generate_briefing("valid theme",serp_client=S(),llm_complete=output,prompt_loader=loader,llm_attempts=1)
  assert (result.status=="draft")==expected,(raw,result.status)
 print("parser 8 cases OK; newline not imposed")
asyncio.run(main())'
```

Saída real, exit 0:

```text
negative OverflowError int too large to convert to float io []
positive OverflowError int too large to convert to float io []
parser 8 cases OK; newline not imposed
```

## Preservação e limites

Snapshot próprio antes dos checks comparou SHA-256 dos **32 arquivos** de `progress.jsonl`, registro físico **35**, chave `inspection_readset_sha256`: zero diferenças contra snapshot pós-coding do parent. JSONL: 35 objetos válidos, newline final presente. Hash de progress capturado separadamente para comparação posterior. Relatórios irmãos mutáveis não lidos nem incluídos nesse readset. Nenhuma alegação de preservação de hashes pré-coding: baseline97 perdido pelo parent não foi reconstruído.

Única escrita de projeto permitida: este report. Sem editar app, tests, forward, config, SDD, bugs ou views; sem fechar ações. Conferência após escrita: 32/32 hashes idênticos antes/depois e contra snapshot pós-coding; progress inalterado. `git diff --check` final executado separadamente, resultado no retorno da inspeção.

## Fora do escopo e clusters

Um achado isolado na validação numérica; nenhum cluster estrutural confirmado. Não auditados DB, HTTP, auth, storage, migrations, binding LLM real, settings secretos, runtime SaaS, segurança de logs de integração, concorrência cross-process, semântica de conclusões ou SLA. Serviço usa asyncio.timeout cooperativo; não certifica callable que bloqueia event loop ou suprime cancelamento. Helpers lidos para contrato consumido, sem reauditoria independente. Não lidos relatórios paralelos. Fakes verdes não fecham T011/T012/T013 nem aceite runtime do produto.
