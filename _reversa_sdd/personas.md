# Personas e Jornadas

> Selo 🟡 PLANEJADO em todos os itens.

## Persona 1: Analista de Research
- **Perfil:** 🟡 Profissional de pesquisa de mercado que precisa validar hipóteses com fontes confiáveis rapidamente.
- **Contexto:** 🟡 Está em uma consulta ao briefing de campanha ou no início do planejamento estratégico, quando surge a necessidade de embasar uma decisão com dados de terceiros.
- **Nível técnico:** 🟡 Intermediário, em análise de dados e triangulação de fontes; conhece métricas de qualidade, mas não escreve código.
- **Dor principal:** 🟡 Pesquisas manuais levam dias, fontes não são auditadas e o relatório final perde a rastreabilidade das fontes canônicas.
- **Objetivo final:** 🟡 Produzir um dossier auditado com fontes canônicas, N pontos aprovados, em menos de 10 minutos.

### Jornada principal
1. 🟡 Enviar o tema ou hipótese para a API de plano de investigação (`/api/v1/plan`).
2. 🟡 Receber a lista de pontos relevantes persistidos no banco para análise.
3. 🟡 Disparar a busca automatizada em paralelo (`/api/v1/search`) para coletar conteúdos.
4. 🟡 Verificar o resultado do conteúdo coletado e validar se as fontes foram lidas.
5. 🟡 Executar a auditoria de qualidade (`/api/v1/audit`) para aprovar ou rejeitar cada ponto.
6. 🟡 Gerar o dossier final completo (`/api/v1/writer`) com fontes marcadas e webhook callback.

---

## Persona 2: Redator/Dev integrador
- **Perfil:** 🟡 Profissional que redige textos ou integra a API de pesquisa profunda dentro de pipelines próprios.
- **Contexto:** 🟡 Durante o desenvolvimento de um produto que depende de pesquisa (relatórios corporativos, blog, conteúdo institucional) ou quando precisa consultar o dossier gerado.
- **Nível técnico:** 🟡 Avançado, em integração de APIs e automação; escreve scripts Python e configura variáveis de ambiente.
- **Dor principal:** 🟡 Ferramentas existentes são caixas pretas (Perplexity, GPT Deep Research) que não permitem auditoria por ponto nem rastreabilidade de fontes.
- **Objetivo final:** 🟡 Integrar os 4 endpoints como serviço reusável e consumir o dossier final via webhook ou banco.

### Jornada principal
1. 🟡 Cadastrar a pesquisa e carregar configuração (chaves, base URLs, preferências) via endpoint administrativo.
2. 🟡 Submeter o tema via `/api/v1/plan` e obter o ID da pesquisa gerado.
3. 🟡 Consultar os pontos no banco e disparar a busca paralela via `/api/v1/search`.
4. 🟡 Ler o conteúdo coletado persistido no banco e validar URLs já lidas.
5. 🟡 Rodar a auditoria via `/api/v1/audit` para garantir qualidade antes da redação.
6. 🟡 Receber o dossier final via webhook de callback configurado (`/api/v1/writer`).

---

Gerado por reversa-researcher em 2026-10-21
Fonte: newproject-brief.md