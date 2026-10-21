# Reproduction Capsule — BUG-20261019-2 (rejeição gap report)

## Commit base
`582ed04abd3f03de8d38f8d162d1d945534e6b54` (branch `main`)

## Ambiente
- OS: Linux 6.8.0-147-generic
- Python: 3.11+
- Runtime: isolado (mock DB)

## Gatilhos (três caminhos de rejeição)

### 1. writer.py:38-39 — `not evidence` incondicional
```python
if not text.strip() or not evidence:
    raise RuntimeError("Writer cannot produce a report without evidence")
```
Gap report válido: `text="## Lacuna\nNenhuma evidência disponível"` + `evidence=[]` → RuntimeError

### 2. writer.py:41-43 — `cited == 0` incondicional
```python
cited = sum(1 for row in evidence if row.source_url in text)
if cited == 0:
    raise RuntimeError("Writer produced report without source citations")
```
Gap report com evidence mas sem links no texto → RuntimeError

### 3. writer.py:45-48 — `not linked_urls` incondicional
```python
linked_urls = set(re.findall(r"\]\((https?://[^\s)]+)\)", text))
known_urls = {row.source_url for row in evidence}
if not linked_urls or not linked_urls.issubset(known_urls):
    raise RuntimeError("Writer used uncollected citation URLs")
```
Gap report sem links → RuntimeError

## Classificação
deterministic — 10/10 reprodutível (caminho de código direto)

## Evidência do diagnóstico
`_reversa_bugs/investigacao-redator/intake/diagnostico-fdd70d5c.md:34`:
> "writer.py:38-39 rejeita incondicionalmente `not evidence` mesmo se texto é relatório de lacunas válido"

## Comando reprodução (mock)
```python
# Simulação das três condições
async def test_gap_report_rejection():
    from app.services.pipeline.writer import _write_report
    from unittest.mock import MagicMock, AsyncMock
    
    mock_research = MagicMock()
    mock_research.id = "test-id"
    mock_research.theme = "Test"
    
    mock_points = [MagicMock()]
    mock_points[0].title = "Ponto 1"
    
    # Caso 1: evidence vazia
    mock_db = AsyncMock()
    mock_db.scalars.return_value.all.return_value = []
    
    with patch("app.services.pipeline.writer.complete", return_value="## Lacuna\nSem dados."):
        try:
            await _write_report(mock_research, mock_points)
            print("Caso 1: PASSOU (inesperado)")
        except RuntimeError as e:
            print(f"Caso 1: REJEITADO - {e}")  # Esperado hoje
    
    # Caso 2: evidence existe, mas texto sem links
    mock_db.scalars.return_value.all.return_value = [MagicMock(source_url="https://real.com")]
    
    with patch("app.services.pipeline.writer.complete", return_value="## Ponto 1\nTexto sem links."):
        try:
            await _write_report(mock_research, mock_points)
            print("Caso 2: PASSOU (inesperado)")
        except RuntimeError as e:
            print(f"Caso 2: REJEITADO - {e}")  # Esperado hoje
```

## Verificação pós-fix
Após correção:
- Caso 1: PASSA — report persistido com `citation_metrics.report_type="gap"`
- Caso 2: PASSA — report persistido com `citation_metrics.gap_report=True`
- Caso 3: MANTIDO — URL não coletada ainda levanta RuntimeError