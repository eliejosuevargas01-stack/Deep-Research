# Questions — Deep Research Engine

> Dúvidas registradas durante análise (modo autônomo, answer_mode=file).  
> Responda para desbloquear as LACUNAs correspondentes.

## ✅ LACUNA 1 RESOLVIDA — Status `revising` (2026-10-05)
- **Decisão**: Adicionar `REVISING = "revising"` ao enum.
- **Aplicada**: `domain_models.py` — enum agora tem 10 valores. Testes verificados.

## ✅ LACUNA 2 RESOLVIDA — prompts .md (2026-10-05)
- **Decisão**: Migrar prompts de `personas.json` para `app/prompts/{persona}.md`.
- **Aplicada**: Criados 7 arquivos (scout, historian, skeptic, pragmatist, futurist, auditor, writer). `__init__.py` vazio removido. Alinha com T002-T009 do actions.md.

## ✅ LACUNA 3 RESOLVIDA — truncamento de fonte (2026-10-05)
- **Decisão**: Modelo lê a página completa; devolve apenas trecho relevante verbatim (citação idêntica ao original).
- **Aplicada**: `MAX_SOURCE_CHARS = 50000` em `search_pipeline.py` (era 8000). Fonte quase completa disponível ao LLM; trecho exato vem do texto original.

## ✅ LACUNA 4 RESOLVIDA — pytest (2026-10-05)
- **Decisão**: `pip install -r requirements.txt`.
- **Aplicada**: pytest 9.1.1 + fastapi 0.142.2 instalados. Suíte roda; observação: `test_settings_test_and_models_endpoints` depende de DNS real (socket.gaierror em sem-rede) — teste de integração com rede, não regressão.

## ✅ LACUNA 5 RESOLVIDA — frontend (2026-10-05)
- **Decisão**: Backend agora, frontend depois. Refactoring de `main.tsx` adiado para fase futura.
