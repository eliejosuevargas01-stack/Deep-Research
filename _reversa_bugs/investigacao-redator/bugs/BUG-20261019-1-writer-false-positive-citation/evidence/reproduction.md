# Reproduction Capsule — BUG-20261019-1 (false positive citação)

## Commit base
`582ed04abd3f03de8d38f8d162d1d945534e6b54` (branch `main`)

## Ambiente
- OS: Linux 6.8.0-147-generic
- Python: 3.11+
- Runtime: isolado (sem DB, sem rede)

## Comando reprodução
```python
# Teste isolado reproduzindo o predicado exato do writer.py:60
import re

line = "**Proposta didática:** desenhe dois cartões, 0 e 1; use moeda parada."

stripped = line.lstrip("-*| \t")
has_substance = bool(re.search(r"[a-zA-Z]{3,}", stripped)) and len(stripped.split()) >= 4
is_factual_candidate = (
    line.startswith(("-", "*", "|"))
    or bool(re.search(r"[.!?]\s*$", line))
)

print(f"starts_with_asterisk={line.startswith('*')}")
print(f"has_substance={has_substance}")
print(f"is_factual_candidate={is_factual_candidate}")
print(f"rejected={has_substance and is_factual_candidate and not re.search(r'\]\(https?://[^\s)]+\)', line)}")
```

## Saída esperada (bug confirmado)
```
starts_with_asterisk=True
has_substance=True
is_factual_candidate=True
rejected=True
```

## Exit code
0

## Classificação
deterministic — 10/10 reprodutível

## Taxa
100% — toda linha iniciada por `**` ou `*` negrito é capturada incorretamente

## Verificação pós-fix
Após correção (função `_is_factual_list_or_table`):
```
**Proposta didática:** ... -> False (não é lista)
- Fato sem fonte -> True (lista real)
| Coluna | -> True (tabela)
1. Item -> True (lista numerada)
```