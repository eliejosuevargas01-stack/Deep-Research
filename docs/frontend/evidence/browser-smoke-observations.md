# Browser smoke observations — initial implementation

Browser: Codex in-app browser, real frontend at localhost:3001, real FastAPI app at localhost:8011, isolated SQLite and existing mocked external providers. These observations are evidence of this initial build, not final approval.

## Completed interaction

Opened settings, entered the public fixture `frontend-contract-key` into the memory-only access field, selected “Definir em memória”, then “Testar Conexão com API”. The page confirmed communication/authentication. Navigated to Pesquisa, entered `Transição Energética Global`, pressed Enter, and received five backend plan points with the explicit “Iniciar pesquisa” action. Clicked it and observed the search request state followed by the report returned by the actual writer endpoint.

The existing provider fixture supplies an education dossier regardless of theme. This is a known fixture limitation, not proof of thematic quality from real models.

## Initial observations for independent verification

- Immediately after setting and testing the access key, the top badge remained “Sem Chave (Aberto)”. After navigating to Pesquisa it changed to “Chave em Memória”. Authentication itself worked.
- Sidebar state displayed raw English `searching` and later `completed` in the Portuguese interface.
- Report metadata displayed `Fontes canônicas citadas: 0`, while the rendered report contained three HTTPS reference links (UNESCO, OECD, MEC).
- The UI displayed the actual report and exposed copy/download controls. Clipboard/download behavior was not exercised by this smoke interaction.
- The settings intro claimed “garantindo segurança total em ambientes compartilhados”. This assertion requires editorial review; memory-only storage alone does not establish total security.

These items should be verified against the final source and tests before deciding whether they remain findings.
