# Inspeção independente — T009/T016

## Gate

**PASS somente para T009/T016: adapter SERP Jina isolado e validação local de configuração. Feature NÃO concluída.** Zero defeitos funcionais confirmados; duas observações LOW, confiança alta, `promoted_to: null`. Não registrados bugs nem alterados produto, testes, actions ou progress.

## Pré-checagem e mapa do recorte

- Skills `reversa-depth-inspection` e `delegated-code-delivery` carregadas. Lentes executadas sequencialmente neste worker leaf. Restrição específica substitui bootstrap/catálogo/views de bugs por este único relatório; `_reversa_bugs/` não consultado.
- Raiz/workdir de todos comandos: `/root/projects/deep-research`. `.reversa/state.json:3-6,10` define pt-BR e estado global antigo; `.reversa/active-requirements.json:3-12` identifica feature em coding. Estado global `forward-complete` não encerra esta feature.
- `AGENTS.md` lido como índice, não como verdade de produto. `execution-policy.md:11,18` exige inspeção independente e limita operações.
- Git: `git status --short --branch; git diff --stat; git diff --name-status; git ls-files --others --exclude-standard; git log -3 --oneline`, exit 0. Branch `main...origin/main`, HEAD `c741ce7`. Árvore já suja com alterações/deleções fora do recorte: não atribuídas ao adapter. Adapter, testes e pasta da feature são untracked; `git diff` não comprova conteúdo destes arquivos, por isso lidos integralmente.
- `git log -3 --oneline -- app/briefing/serp_client.py tests/test_briefing_serp_client.py`, exit 0, saída vazia. Sem histórico versionado do recorte para comparar baseline ou autenticar RED antigo.

| Camada | Fonte / símbolos | Papel |
|---|---|---|
| Produto aprovado | `requirements.md:32-35,51-60,67-70,155-162` | Tema 3–300; SERP exclusiva sem Reader; erro seguro; até quatro tentativas; parser tolerante; timeout 30s configurável |
| Âncoras planejadas | `_reversa_sdd/prd.md:33-41,46,67-68,99-107`; `_reversa_sdd/sdd/briefing.md:54-63,75-76,85-87,118,124-130` | Escopo e limites; não substituem execução nem comprovam SaaS |
| Implementação | `app/briefing/serp_client.py:11-144`: `JinaSerpClient`, `search`, `_single_attempt`, `_parse`, `_valid_url`, `SerpSearchError` | HTTP e serialização local |
| Dependência congelada | `app/briefing/domain.py:27-33`: `validate_theme` | Strip e limite de caracteres antes de transporte |
| Testes duráveis | `tests/test_briefing_serp_client.py:20-210` | Dez testes importam produção; fixtures sintéticas com MockTransport |
| Contrato local | `interfaces/jina-serp.md:168-176` | Assinatura, whitelist, falhas retentáveis, ownership, lock local, limites |
| Rastreabilidade | `actions.md:52,58,64-71`; `progress.jsonl:8-12`; `legacy-impact.md:17-22`; `regression-watch.md:40-48` | T009/T016 fechadas localmente; integração pendente; W006–W009 |
| Dados | JSON efêmero `q` / `data[]`, chave em memória e header Bearer | Nenhuma tabela, cache persistido, fila, DB, LLM ou página de resultado tocada |

Caminhos abreviados de documentos pertencem a `_reversa_forward/001-modulo-briefing/`.

## Matriz de aceite e lentes

| Lente / critério | Implementação | Evidência real | Veredito |
|---|---|---|---|
| Conformidade: endpoint, POST, q normalizado, quatro headers | Adapter:11,82-92 | Teste `test_success_posts_only_to_jina_and_exports_required_fields`: método, URL, JSON, Bearer, Accept, Content-Type, no-content, timeout; uma chamada | PASS |
| Contratos: sem Reader/fetch de resultados/redirect | Adapter:82-93; sem outro transporte | Teste de sucesso + `test_redirect_is_not_followed_and_does_not_leak_authorization`, inclusive cliente caller configurado para seguir redirect; quatro requisições só para endpoint fixo | PASS local; SaaS não verificado |
| Fluxo de dados: exportar só title/url/description não vazios, extras ignorados | Adapter:124-144 | Teste sucesso e canary excluído; teste campos inválidos; probe mixed conserva somente item válido com strip e whitelist | PASS |
| Erros: até quatro tentativas reais, sucesso encerra | Adapter:63-74,94-105 | Testes sucesso inicial, sucesso na quarta, esgotamento, JSON/shape/vazio e timeout; probe ConnectError faz quatro chamadas | PASS |
| Configuração: tema 3–300 antes de I/O | Adapter:61-62; domain:27-33 | Teste invalid_theme; probe rejeita None/123/2/301 e aceita 3/300, sem chamadas inválidas | PASS |
| Configuração: chave ASCII 33–126, mensagem fixa antes de I/O | Adapter:46-50 | Teste T016 + probe 39 inválidas, transporte zero; todos caracteres 33–126 juntos aceitos com uma chamada | PASS |
| Configuração: timeout positivo, finito, não bool | Adapter:51-56,81,91 | Teste default 30, teste timeout 0.02 e probe sete inválidos | PASS |
| Segurança: mensagem/contagem pública sem corpo/chave/query/repr interno | Adapter:18-23,74,94-102 | Teste exhaustion; probe ConnectError: `str` exato, `repr` seguro, attempts=4; nenhum logger no adapter | PASS para mensagem pública; cadeia em O-02 |
| Erro de programação não retenta | Adapter:71,116-118 | Probe RuntimeError propaga, uma chamada | PASS |
| Concorrência: lock por instância, tentativas sequenciais | Adapter:58,61,65-68 | Testes retries e two_operations: max_active=1 | PASS local |
| Cancelamento: propaga e libera lock | Adapter:61,69-70,114-115 | Teste cancellation cancela operação bloqueada e próxima busca sucede; total duas chamadas | PASS |
| Isolamento / ownership | Adapter:77-78,119-121; testes:28-31 | MockTransport em todos testes; caller não fechado; probe próprio fechado | PASS; lacuna durável O-01 |
| Rastreabilidade | Actions/progress/watch/impact | Probe 12 objetos JSON válidos, newline final; 16 ações, oito [X]; T009/T016 [X], T010/T011 pendentes | PASS do estado atual |

Não há provider alternativo, leitura de URL SERP, log, model ou persistência no adapter. Timeout wall-clock cobre POST, não inclui criação/fechamento do cliente nem espera pelo lock; estes limites não são SLA ou deadline global de geração. Sem backoff obrigatório conforme decisão local registrada, não defeito neste recorte.

## Execução real

### E1 — testes duráveis

```sh
python3 -B -m unittest discover -s tests -p test_briefing_serp_client.py -v
python3 -B -m unittest discover -s tests -p 'test_briefing_*.py' -v
```

Saída real: `Ran 10 tests in 0.077s`, `OK`; `Ran 30 tests in 0.087s`, `OK`. Nenhum failed/skipped. Todos dez nomes do adapter reconciliados com inventário físico e saída `ok`. Camada ampla é suíte local briefing, NÃO suíte legada inteira nem integração HTTP/DB. Comando combinado terminou exit 0; ambos runners exibiram OK.

### E2 — compilação e whitespace

```sh
PYTHONPYCACHEPREFIX=/root/.hermes/profiles/orchestrator/cache/scratch/audit-t009-pycache python3 -B -m py_compile app/briefing/serp_client.py tests/test_briefing_serp_client.py
printf 'compile_exit=%s\n' "$?"
git diff --check
printf 'diff_exit=%s\n' "$?"
```

Saída literal: `compile_exit=0`, `diff_exit=0`. Pycache em scratch, não repo. Diff-check de Git não verifica whitespace de untracked; leitura semântica cobre recorte novo.

### E3 — configuração, tema e timeout (probe inline Python -B)

Código efetivamente executado na primeira probe, trecho completo da fase de configuração:

```python
import asyncio, httpx
from app.briefing.serp_client import JinaSerpClient
P = {"data": [{"title": " t ", "url": "https://example.org", "description": " d ", "extra": "synthetic"}]}
async def main():
    calls = 0
    def handler(r):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=P)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as h:
        bad = [None, 123, ""] + ["key" + chr(i) for i in range(33)] + ["key" + chr(i) for i in (127, 160, 233)]
        for k in bad:
            try:
                JinaSerpClient(k, http_client=h)
            except ValueError as e:
                assert str(e) == "Chave de API inválida"
            else:
                raise AssertionError("accepted invalid key")
        assert calls == 0
        print("config_invalid", len(bad), "transport_calls", calls)
        await JinaSerpClient("".join(chr(i) for i in range(33, 127)), http_client=h).search("abc")
        assert calls == 1
        print("config_printable_success transport_calls", calls)
        for t in (None, 123, "ab", "x" * 301):
            try:
                await JinaSerpClient("fake", http_client=h).search(t)
            except ValueError:
                pass
            else:
                raise AssertionError("accepted invalid theme")
        assert calls == 1
        for t in ("abc", "x" * 300):
            await JinaSerpClient("fake", http_client=h).search(t)
        assert calls == 3
        print("theme_boundaries invalid_zero_io valid_3_300 OK")
        for timeout in (True, None, "30", 0, -1, float("nan"), float("inf")):
            try:
                JinaSerpClient("fake", timeout, http_client=h)
            except ValueError as e:
                assert str(e) == "Timeout inválido"
            else:
                raise AssertionError("accepted invalid timeout")
        print("timeout_config 7 rejected")
asyncio.run(main())
```

Saída literal destas asserts:

```text
config_invalid 39 transport_calls 0
config_printable_success transport_calls 1
theme_boundaries invalid_zero_io valid_3_300 OK
timeout_config 7 rejected
```

**Falha de ferramenta/probe declarada:** primeira chamada combinava esta fase com probe ownership e terminou exit 1 por `TypeError: main.<locals>.factory() got an unexpected keyword argument 'transport'`. Patch de `httpx.AsyncClient` atingiu também fábrica da própria probe. Não defeito do adapter; não atribuído exit 0 à chamada. Fase acima passou antes da falha. Segunda probe preservou `RealClient=httpx.AsyncClient` antes de patch e terminou exit 0.

### E4 — ownership, programação, erro de transporte, parser e rastreabilidade

Comando real `python3 -B -c '<código abaixo>'`, exit **0**. Código completo da segunda probe:

```python
import asyncio, httpx, traceback, json, re
from pathlib import Path
from unittest.mock import patch
from app.briefing.serp_client import JinaSerpClient, SerpSearchError
RealClient = httpx.AsyncClient
P = {"data": [{"title": " t ", "url": "https://example.org", "description": " d ", "extra": "synthetic"}]}
async def main():
    owned = []
    def factory():
        c = RealClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=P)))
        owned.append(c)
        return c
    with patch("app.briefing.serp_client.httpx.AsyncClient", side_effect=factory):
        await JinaSerpClient("fake").search("abc")
    assert len(owned) == 1 and owned[0].is_closed
    print("ownership owned_closed OK")
    pc = 0
    def programming(r):
        nonlocal pc
        pc += 1
        raise RuntimeError("synthetic programming")
    async with RealClient(transport=httpx.MockTransport(programming)) as h:
        try:
            await JinaSerpClient("fake", http_client=h).search("abc")
        except RuntimeError:
            pass
        else:
            raise AssertionError("programming swallowed")
        assert not h.is_closed
    assert pc == 1
    print("programming_error propagated transport_calls", pc, "caller_open OK")
    fc = 0
    def failure(r):
        nonlocal fc
        fc += 1
        raise httpx.ConnectError("SYNTHETIC-ERROR-CANARY", request=r)
    async with RealClient(transport=httpx.MockTransport(failure)) as h:
        try:
            await JinaSerpClient("fake", http_client=h).search("abc")
        except SerpSearchError as e:
            assert e.attempts == 4 and str(e) == "Busca SERP indisponível após 4 tentativas"
            assert "SYNTHETIC-ERROR-CANARY" not in str(e) and "SYNTHETIC-ERROR-CANARY" not in repr(e)
            print("transport_failure attempts", e.attempts, "public_str_repr_safe", True, "traceback_contains_internal_canary", "SYNTHETIC-ERROR-CANARY" in "".join(traceback.format_exception(e)))
    assert fc == 4
    mixed = {"data": [None, {}, {"title": "bad", "url": "https://example.org", "description": " "}, P["data"][0]]}
    assert JinaSerpClient._parse(mixed) == [{"title": "t", "url": "https://example.org", "description": "d"}]
    print("parser_mixed_keeps_valid_whitelist OK")
asyncio.run(main())
p = Path("_reversa_forward/001-modulo-briefing/progress.jsonl").read_bytes()
rows = [json.loads(l) for l in p.splitlines()]
assert len(rows) == 12 and p.endswith(b"\n")
print("progress objects", len(rows), "final_newline", True)
a = Path("_reversa_forward/001-modulo-briefing/actions.md").read_text()
rows = [l for l in a.splitlines() if re.match(r"\| (?:\[//\] )?T\d{3} \|", l)]
assert len(rows) == 16 and sum("[X]" in l for l in rows) == 8
print("actions total", len(rows), "done", 8)
```

Saída literal:

```text
ownership owned_closed OK
programming_error propagated transport_calls 1 caller_open OK
transport_failure attempts 4 public_str_repr_safe True traceback_contains_internal_canary True
parser_mixed_keeps_valid_whitelist OK
progress objects 12 final_newline True
actions total 16 done 8
```

Todas requisições destas probes usam MockTransport; fábrica própria também substituída por cliente MockTransport. Valores fictícios; nenhuma chave real ou .env lido.

## Consolidação dos achados

### O-01 — parte da cobertura local não é durável

- **Tipo:** observação de cobertura; **severidade LOW**, confiança alta; `promoted_to: null`.
- **Evidência:** `tests/test_briefing_serp_client.py:21-210` cobre caller aberto, contrato, retries HTTP, timeout, cancelamento, lock e redirects; não possui teste de cliente próprio fechado, RuntimeError sem retry, ConnectError seguro ou lista mista inválida/válida. E4 prova esses comportamentos hoje, mas não deixa regressão mantida.
- **Impacto:** alteração futura nesses caminhos pode passar nos dez testes atuais. Não demonstrado desvio funcional atual; não bloqueia gate isolado.
- **Ação sugerida ao implementador:** persistir casos de E4 no teste existente quando autorizado, mantendo MockTransport e sem rede. Auditor não corrige.

### O-02 — chaining preserva detalhe interno; sink futuro deve sanitizar

- **Tipo:** observação de fronteira de erro; **severidade LOW**, confiança alta; `promoted_to: null`.
- **Evidência:** `app/briefing/serp_client.py:74,94-102` usa chaining; `interfaces/jina-serp.md:172` o declara interno. E4 confirma `traceback_contains_internal_canary True`, mas `str` e `repr` do erro público continuam seguros.
- **Causalidade:** `traceback.format_exception(SerpSearchError)` inclui mensagem da causa ConnectError. Consumidor que responder/logar traceback integral pode expor detalhes internos. Nenhum logger/HTTP sink implementado neste recorte: vazamento real em resposta/log NÃO observado, não finding HIGH.
- **Impacto:** T010/T011/T013 devem verificar serializer e logs reais com canaries de chave, corpo e tema. Não remover chaining por preferência sem avaliar consumidor; não declarar proteção integral de logs a partir de `str` seguro.

Contagens por lente: conformidade 0, dados 0, contratos 0, erros/segurança O-02, testes O-01, concorrência 0, rastreabilidade 0. Observações deduplicadas; nenhum cluster funcional confirmado. CRITICAL/HIGH/MEDIUM: zero achados confirmados.

## Rastreabilidade e limites históricos

- `actions.md:52,58` mantém T009/T016 [X]; 16 ações, oito [X], oito pendentes. T010/T011 e QA/segurança finais permanecem pendentes: não alterados pelo relatório.
- `progress.jsonl:9` registra nove testes T009; linha 10 registra falha de configuração e reparo estrutural do separador T015/T009; linhas 11–12 registram T016 e dez testes/30 totais. Sequência não apaga falha anterior e é consistente com estado atual.
- Doze linhas físicas são objetos JSON válidos e há newline final. Preservação byte-a-byte dos objetos anteriores ao reparo e RED histórico não podem ser reautenticados sem snapshot anterior; são afirmações históricas do log, não execução reproduzida nesta inspeção.
- `legacy-impact.md:17-22` identifica componente novo, chave ASCII restrita e ausência de router/storage nesta rodada; W006–W009 apontam testes existentes. W007 remete §6 de interface onde fontes são listadas; regra executável consta §5/§7 e requisitos RF-10, sem ambiguidade funcional bloqueante.

## Fora da inspeção

Sem rede real/Jina, leitura de páginas, verificação do schema hospedado ou garantia de comportamento interno SaaS. Sem coordenação cross-process/cross-instance, LLM, service, router HTTP, persistência, DB, frontend, commit/push/deploy ou migração. Não executada suíte legada geral, por ser fora do recorte e não fonte de verdade de produto. Domínio/schemas/prompt congelados, apenas dependência `validate_theme` consultada. Credenciais não lidas. Mudanças sujas anteriores fora do recorte não auditadas nem atribuídas ao adapter.

Gate local PASS não conclui feature, não prova reuso SERP após falha LLM, registro estável, segurança HTTP/log integrada ou QA funcional final.
