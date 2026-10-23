"""Orquestrador da etapa 2: Busca com Personas (historiador, visionario, cetico, futurista).

Executa varredura profunda concorrente via asyncio.gather sobre os N pontos de investigação,
aplicando as quatro personas analíticas configuradas via ambiente (sem fallback hardcoded).
Cada persona opera como agente autônomo com ReAct, formulando suas próprias queries (máx 3),
consultando o Jina SERP e Reader e mantendo memória conversacional indexada por (id_pesquisa, ponto_id).
Atende a RF-003, RF-004 do PRD e RF-01 a RF-08 da SDD de busca (T027).
"""

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional, Set
from app.config import get_settings
from app.db.models import Ponto
from app.db.research_repository import ResearchRepository
from app.tools.jina_client import JinaClient
from app.tools.errors import JinaError
from app.tools.llm_client import LLMClient

STATUS_FALHA_COLETA = "falha_coleta"

# RF-05/CA-05.4: nenhum prompt pode pedir síntese sobre evidências inexistentes.
TEXTO_FALHA_COLETA = (
    "COLETA FALHOU: não foi possível obter nenhuma evidência web para esta persona. "
    "A análise abaixo NÃO é resultado de pesquisa e não deve ser tratada como conteúdo apurado."
)


def _diagnostico_falha(erro: JinaError) -> str:
    """RF-04/CA-04.2: mensagem acionável com categoria e ação corretiva."""
    return str(erro)

PERSONA_PROMPTS: Dict[str, str] = {
    "historiador": (
        "Você é a persona Historiador do sistema Deep Research. "
        "Sua missão é investigar as raízes, antecedentes, marcos temporais e a evolução histórica "
        "do ponto temático, destacando precedentes e como o cenário atual foi construído ao longo do tempo."
    ),
    "visionario": (
        "Você é a persona Visionário do sistema Deep Research. "
        "Sua missão é investigar as fronteiras de inovação, tendências emergentes, oportunidades futuras "
        "e o potencial transformador do ponto temático, buscando saltos evolutivos e novas possibilidades."
    ),
    "cetico": (
        "Você é a persona Cético do sistema Deep Research. "
        "Sua missão é investigar com rigor crítico as vulnerabilidades, riscos, falhas, "
        "limitações práticas, contradições e controvérsias do ponto temático, trazendo contra-argumentos e ressalvas."
    ),
    "futurista": (
        "Você é a persona Futurista do sistema Deep Research. "
        "Sua missão é projetar cenários prospectivos de longo prazo, impactos sistêmicos, "
        "implicações sociais, econômicas e tecnológicas aprofundadas do ponto temático."
    ),
}

TOOLS_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "jina_search",
            "description": (
                "Executa busca na web via Jina SERP e raspa as páginas novas relevantes para aprofundamento investigativo. "
                "Em caso de ausência de resultados ou falha de conectividade/saldo, retorna mensagem explícita de aviso ou erro."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca otimizado formulado pela persona para a SERP",
                    }
                },
                "required": ["query"],
            },
        },
    }
]


class Searcher:
    """Orquestrador do domínio para varredura web concorrente agêntica com personas."""

    def __init__(
        self,
        research_repo: ResearchRepository,
        jina_client: JinaClient,
        llm_client: LLMClient,
        personas: Optional[List[str]] = None,
    ) -> None:
        self.research_repo = research_repo
        self.jina_client = jina_client
        self.llm_client = llm_client
        # Memória das investigações indexada pela chave primária (id_pesquisa, ponto_id)
        self.memoria: Dict[str, Dict[str, Any]] = {}

        # RN-02, RN-04: Personas sem fallback hardcoded (filtra estritamente as 4 personas de busca)
        candidatas = personas
        if candidatas is None:
            personas_config = get_settings().personas_config or os.environ.get("PERSONAS_CONFIG")
            if not personas_config or not str(personas_config).strip():
                raise ValueError("Configuração ausente: PERSONAS_CONFIG não informada no ambiente.")
            candidatas = [p.strip() for p in str(personas_config).split(",") if p.strip()]

        self.personas = [p for p in candidatas if p in ("historiador", "visionario", "cetico", "futurista")]

        if not self.personas:
            raise ValueError(
                "Configuração ausente: nenhuma persona válida (historiador, visionario, cetico, futurista) encontrada."
            )

    def __repr__(self) -> str:
        return f"Searcher(personas={self.personas})"

    async def execute_search(
        self,
        id_pesquisa: str,
        ponto_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executa a busca concorrente dos pontos da pesquisa com asyncio.gather e deduplicação."""
        if not id_pesquisa or not id_pesquisa.strip():
            raise ValueError("O identificador id_pesquisa não pode ser vazio.")

        pesquisa = await self.research_repo.get_research(id_pesquisa)
        if not pesquisa:
            raise ValueError(f"RESEARCH_NOT_FOUND: Pesquisa não localizada: {id_pesquisa}")

        todos_pontos = await self.research_repo.list_points(id_pesquisa)
        if not todos_pontos:
            raise ValueError(f"RESEARCH_NOT_FOUND: Nenhum ponto de investigação encontrado para {id_pesquisa}.")

        if ponto_id:
            pontos_alvo = [p for p in todos_pontos if p.ponto_id == ponto_id]
            if not pontos_alvo:
                raise ValueError(f"Ponto {ponto_id} não localizado na pesquisa {id_pesquisa}.")
        else:
            pontos_alvo = [p for p in todos_pontos if p.status in ("pendente", "em_andamento", "reprovado")]
            if not pontos_alvo:
                # Caso todos já tenham sido processados, permite reprocessamento
                pontos_alvo = todos_pontos

        # Validação estrita de limite máximo de 4 passagens (1 inicial + 3 retries) por ponto
        for p in pontos_alvo:
            if (p.tentativas or 0) >= 4:
                raise ValueError(
                    f"MAX_ATTEMPTS_EXCEEDED: O ponto {p.ponto_id} já esgotou o limite máximo de 4 tentativas "
                    "de busca (1 inicial + 3 retentativas pós-reprovação)."
                )

        # Deduplicação de URLs por pesquisa (RN-04)
        urls_lidas_existentes = await self.research_repo.get_read_urls(id_pesquisa)
        seen_urls: Set[str] = set(urls_lidas_existentes)
        urls_lock = asyncio.Lock()
        session_lock = asyncio.Lock()
        content_cache: Dict[str, str] = {}

        async def _executar_persona(
            ponto: Ponto,
            persona: str,
            coletas_anteriores: List[Any],
        ) -> Dict[str, Any]:
            """Executa a investigação agêntica sob a ótica de uma persona (máx 3 queries ReAct)."""
            memory_key = f"{id_pesquisa}:{ponto.ponto_id}"

            feedback_auditor = ""
            if ponto.pontos_fracos and str(ponto.pontos_fracos).strip():
                feedback_auditor = (
                    f"\n\nATENÇÃO - DIRETRIZ PRIORITÁRIA DE RE-PESQUISA:\n"
                    f"A rodada anterior deste ponto investigativo foi AUDITADA E REPROVADA. "
                    f"O auditor apontou as seguintes lacunas e deficiências a corrigir:\n"
                    f"{ponto.pontos_fracos}\n\n"
                    "Seu objetivo PRIORITÁRIO nesta nova rodada de busca é aprofundar e suprir "
                    "especificamente esses pontos fracos identificados, obtendo fontes e evidências concretas."
                )

            # Histórico do que já foi apurado por esta persona nas rodadas anteriores
            resumo_anterior = ""
            if coletas_anteriores:
                trechos_persona: List[str] = []
                for c in coletas_anteriores:
                    padrao = rf"### Perspectiva {persona.capitalize()}[\s\S]*?(?=(### Perspectiva|\Z))"
                    match = re.search(padrao, getattr(c, "conteudo_coletado", "") or "")
                    if match:
                        trecho = match.group(0).split("---\n**Evidências Brutas")[0].strip()
                        if trecho:
                            trechos_persona.append(f"[Rodada {getattr(c, 'rodada', 1)}]:\n{trecho[:1500]}")
                if trechos_persona:
                    resumo_anterior = (
                        f"\n\nO QUE VOCÊ JÁ INVESTIGOU NAS RODADAS ANTERIORES:\n"
                        f"{chr(10).join(trechos_persona)}\n\n"
                        "DIRETRIZ DE CONTINUIDADE: Não repita as buscas e fatos acima já conhecidos. "
                        "Foque sua nova pesquisa exclusivamente no que está faltando segundo os pontos fracos apontados."
                    )

            system_instruction = (
                f"{PERSONA_PROMPTS.get(persona, '')}\n\n"
                f"Você está investigando o tema '{ponto.tema}', especificamente o ponto focal: '{ponto.ponto}'.\n"
                f"{feedback_auditor}\n"
                f"{resumo_anterior}\n"
                "DIRETRIZES AGÊNTICAS OBRIGATÓRIAS:\n"
                "1. Formule de forma autônoma suas próprias queries de busca focadas exclusivamente na sua perspectiva temática.\n"
                "2. Faça UMA query por vez utilizando a ferramenta `jina_search` (no MÁXIMO 3 queries de busca).\n"
                "3. PRIORIDADE DE FONTES CANÔNICAS: Priorize relatórios oficiais, pesquisas primárias, comunicados e portais setoriais confiáveis. Evite redes sociais para dados quantitativos.\n"
                "4. ANCORAGEM OBRIGATÓRIA: Ao citar qualquer métrica, número, percentual, estudo ou caso empírico de empresa, SEMPRE ancore no corpo do texto com o link canônico em Markdown: [Nome da Fonte/Estudo](url).\n"
                "5. A cada resultado recebido da web, leia criticamente as evidências: se já dispõe de dados suficientes, "
                "apresente diretamente sua síntese analítica final aprofundada (sem chamar a ferramenta novamente).\n"
                "6. Se ainda faltar informação essencial e não tiver esgotado as 3 queries, formule uma nova query refinada.\n"
                "7. RESPOSTA EXPLÍCITA EM CASO DE FALHA OU AUSÊNCIA DE CONTEÚDO: "
                "Caso a ferramenta `jina_search` falhe, retorne erro (ex.: erro de autenticação, saldo insuficiente, indisponibilidade) "
                "ou não traga conteúdo/fontes utilizáveis após suas tentativas, você DEVE responder com uma mensagem explícita declarando a impossibilidade "
                "de realizar a investigação devido à falha ou ausência de fontes web. "
                "É ESTRITAMENTE PROIBIDO inventar fatos, simular evidências ou produzir análise baseada apenas em conhecimento interno para mascarar a falha da ferramenta."
            )
            user_prompt = (
                f"Identificador da Pesquisa: {id_pesquisa}\n"
                f"Identificador do Ponto: {ponto.ponto_id}\n"
                f"Tema: {ponto.tema}\n"
                f"Ponto de Investigação: {ponto.ponto}\n"
                f"Perspectiva da Persona: {persona.capitalize()}\n"
                f"{feedback_auditor}\n"
                f"{resumo_anterior}\n\n"
                "Por favor, inicie sua investigação agêntica formulando a query de busca inicial para a ferramenta `jina_search`."
            )

            # Memória conversacional inicial da persona
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ]

            query_count = 0
            max_queries = 3
            persona_read_urls: List[str] = []
            persona_source_urls: List[str] = []
            raw_evidence_chunks: List[str] = []
            persona_reasonings: List[str] = []
            analise_final = ""
            erro_provedor: Optional[JinaError] = None

            # Loop ReAct agêntico: máximo de 3 queries por ponto
            while query_count < max_queries:
                available_tools = TOOLS_DEFINITIONS if query_count < max_queries else None
                tool_choice = "auto" if available_tools else None

                try:
                    msg = await self.llm_client.chat_completion_message(
                        model=self.llm_client.model_light,
                        messages=messages,
                        tools=available_tools,
                        tool_choice=tool_choice,
                    )
                except Exception:
                    break

                tool_calls = msg.get("tool_calls") or []
                content = msg.get("content") or msg.get("reasoning_content") or ""
                reasoning_chunk = msg.get("reasoning_content")
                if reasoning_chunk:
                    persona_reasonings.append(reasoning_chunk)

                if not tool_calls:
                    # Modelo julgou que possui evidências suficientes ou emitiu a resposta analítica final
                    if content and content.strip():
                        analise_final = content.strip()
                    messages.append({"role": "assistant", "content": content or None})
                    break

                # Modelo solicitou chamada de ferramenta (1 query por vez)
                tool_call = tool_calls[0]
                call_id = tool_call.get("id") or f"call_{query_count + 1}"
                fn = tool_call.get("function") or {}
                fn_name = fn.get("name") or "jina_search"
                fn_args_raw = fn.get("arguments") or "{}"

                try:
                    fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                except Exception:
                    fn_args = {"query": str(fn_args_raw)}

                query_formulada = (fn_args.get("query") or f"{ponto.tema} {ponto.ponto} {persona}").strip()
                query_count += 1

                # Execução da busca via Jina com a query formulada pelo próprio LLM
                # s.jina.ai já entrega o conteúdo raspado diretamente quando include_content=True
                falha_tool = False
                serp_results = []
                tool_response_text = ""
                try:
                    serp_results = await self.jina_client.search(query=query_formulada, include_content=True)
                except JinaError as erro_jina:
                    # RF-01/RF-03: a falha do provedor é preservada, não virará "sem resultados".
                    erro_provedor = erro_jina
                    falha_tool = True
                    tool_response_text = f"ERRO NA FERRAMENTA {fn_name}: {erro_jina}"
                except Exception as erro_inesperado:
                    # RF-03/CA-03.2: texto extenso não mascara a ausência total de fonte.
                    erro_provedor = JinaError(
                        f"falha inesperada ao consultar o provedor: {erro_inesperado}",
                        categoria="desconhecido",
                    )
                    falha_tool = True
                    tool_response_text = f"ERRO NA FERRAMENTA {fn_name}: {erro_provedor}"

                if falha_tool:
                    messages.append({
                        "role": "assistant",
                        "content": content or None,
                        "tool_calls": [tool_call],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": fn_name,
                        "content": tool_response_text[:8000],
                    })
                    break

                scraped_for_this_query: List[str] = []
                for item in serp_results:
                    if not isinstance(item, dict):
                        continue
                    u = str(item.get("url", "")).strip()
                    if not u:
                        continue

                    is_new = False
                    async with urls_lock:
                        if u not in seen_urls:
                            seen_urls.add(u)
                            is_new = True

                    if is_new:
                        # Extrai o conteúdo raspado diretamente retornado pelo s.jina.ai (sem chamada duplicada ao reader)
                        page_text = str(item.get("content") or item.get("description") or "").strip()
                        if page_text:
                            content_cache[u] = page_text
                            persona_read_urls.append(u)
                            persona_source_urls.append(u)
                            scraped_for_this_query.append(f"Fonte ({u}):\n{page_text}")
                            raw_evidence_chunks.append(page_text)
                    else:
                        # URL já foi lida em rodada anterior ou por outra persona: não re-raspa
                        persona_source_urls.append(u)
                        if u in content_cache:
                            scraped_for_this_query.append(f"Fonte [já conhecida] ({u}):\n{content_cache[u][:1000]}")

                if not serp_results:
                    aviso_vazio = (
                        f"Aviso: a busca por '{query_formulada}' não retornou nenhuma URL ou resultado na web. "
                        "Por favor, formule uma query com termos alternativos ou mais específicos."
                    )
                    scraped_for_this_query.append(aviso_vazio)
                elif not scraped_for_this_query:
                    aviso_repeticao = (
                        f"Aviso: as {len(serp_results)} URLs retornadas para a busca '{query_formulada}' já foram lidas anteriormente "
                        "ou não contêm conteúdo utilizável. Formule uma query com termos diferentes para localizar novas fontes primárias."
                    )
                    scraped_for_this_query.append(aviso_repeticao)

                tool_response_text = "\n\n---\n\n".join(scraped_for_this_query)

                # Atualização da memória conversacional
                messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [tool_call],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": fn_name,
                    "content": tool_response_text[:8000],
                })

            # RF-05/CA-05.1 e CA-05.4: sem evidência bruta não há síntese possível.
            # O caminho anterior pedia "síntese com base nas evidências coletadas"
            # mesmo com zero evidências, produzindo dossiê inventado com aparência legítima.
            if not raw_evidence_chunks:
                detalhe = _diagnostico_falha(erro_provedor) if erro_provedor else (
                    "Nenhuma fonte web retornou conteúdo utilizável nas queries desta persona."
                )
                analise_final = (
                    f"{TEXTO_FALHA_COLETA}\n\n"
                    f"Diagnóstico: {detalhe}\n\n"
                    f"Queries executadas sem retorno de evidência: {query_count}."
                )
            # Caso tenha esgotado o limite de 3 queries sem emissão da síntese, solicita a redação final
            elif not analise_final:
                messages.append({
                    "role": "user",
                    "content": (
                        "Você concluiu suas rodadas de busca agêntica. "
                        "Com base em todas as evidências coletadas, produza agora sua síntese analítica final "
                        f"completa e aprofundada sob a ótica da sua persona ({persona.capitalize()})."
                    ),
                })
                try:
                    analise_res, final_reas = await self.llm_client.chat_completion_with_reasoning(
                        model=self.llm_client.model_light,
                        messages=messages,
                    )
                    analise_final = analise_res
                    if final_reas:
                        persona_reasonings.append(final_reas)
                except Exception:
                    analise_final = "\n\n".join(raw_evidence_chunks[:3])

            # Persistência na memória do Searcher indexada pela chave {id_pesquisa}:{ponto_id}
            if memory_key not in self.memoria:
                self.memoria[memory_key] = {}
            self.memoria[memory_key][persona] = {
                "messages": messages,
                "queries_executadas": query_count,
                "urls_lidas": persona_read_urls,
                "urls_fonte": persona_source_urls,
            }

            raw_evidence = "\n\n".join(raw_evidence_chunks)
            reasoning_persona = "\n\n---\n\n".join(persona_reasonings) if persona_reasonings else None

            return {
                "persona": persona,
                "analise": analise_final.strip(),
                "raw_evidence": raw_evidence,
                "reasoning": reasoning_persona,
                "urls_lidas": persona_read_urls,
                "urls_fonte": persona_source_urls,
                "queries_executadas": query_count,
                "evidencia_vazia": not raw_evidence_chunks,
                "erro_provedor": _diagnostico_falha(erro_provedor) if erro_provedor else None,
            }

        async def _processar_ponto(ponto: Ponto) -> Dict[str, Any]:
            """Processa a busca de um ponto disparando em paralelo as 4 personas agênticas."""
            coletas_anteriores = await self.research_repo.get_collected_content_for_point(id_pesquisa, ponto.ponto_id)
            persona_tasks = [
                _executar_persona(ponto, persona, coletas_anteriores)
                for persona in self.personas
            ]
            persona_results = await asyncio.gather(*persona_tasks)

            # Consolidação dos conteúdos das 4 personas para o mesmo ponto
            blocos_personas: List[str] = []
            blocos_reasonings: List[str] = []
            todas_urls_lidas: List[str] = []
            todas_urls_fonte: List[str] = []
            total_queries_ponto = 0

            for res in persona_results:
                persona_name = res["persona"].capitalize()
                total_queries_ponto += res.get("queries_executadas", 0)
                blocos_personas.append(
                    f"### Perspectiva {persona_name}\n\n{res['analise']}\n\n"
                    f"---\n**Evidências Brutas ({persona_name}):**\n{res['raw_evidence']}"
                )
                if res.get("reasoning"):
                    blocos_reasonings.append(f"### Raciocínio ({persona_name}):\n{res['reasoning']}")
                todas_urls_lidas.extend(res["urls_lidas"])
                todas_urls_fonte.extend(res["urls_fonte"])

            conteudo_consolidado = "\n\n".join(blocos_personas)
            reasoning_consolidado = "\n\n====================\n\n".join(blocos_reasonings) if blocos_reasonings else None

            # Deduplicação das URLs do ponto preservando ordem
            urls_lidas_dedup = list(dict.fromkeys(todas_urls_lidas))
            urls_fonte_dedup = list(dict.fromkeys(todas_urls_fonte))

            # Gravação sem truncamento em conteudo_coletado (RN-05, RF-07)
            async with session_lock:
                await self.research_repo.save_collected_content(
                    id_pesquisa=id_pesquisa,
                    ponto_id=ponto.ponto_id,
                    tema=ponto.tema,
                    ponto=ponto.ponto,
                    conteudo_coletado=conteudo_consolidado,
                    urls_lidas=urls_lidas_dedup,
                    urls_fonte=urls_fonte_dedup,
                    reasoning_coleta=reasoning_consolidado,
                )

            # RF-03/CA-03.1: zero URLs efetivamente lidas em TODAS as personas é falha
            # de coleta, não resultado aceitável. A classificação ignora o tamanho do
            # texto analítico (CA-03.2), porque texto pode ter sido inventado sem fonte.
            falha_coleta = len(urls_lidas_dedup) == 0
            status_ponto = STATUS_FALHA_COLETA if falha_coleta else "coletado"

            # RF-04/CA-04.1 e CA-04.2: diagnóstico acionável por ponto
            if falha_coleta:
                motivos = [
                    f"- {res['erro_provedor']}"
                    for res in persona_results
                    if res.get("erro_provedor")
                ]
                if not motivos:
                    motivos = [
                        f"- {res['persona']}: nenhuma fonte retornou conteúdo utilizável "
                        f"em {res.get('queries_executadas', 0)} queries."
                        for res in persona_results
                    ]
                diagnostico = (
                    "Nenhuma URL foi efetivamente lida para este ponto.\n"
                    + "\n".join(dict.fromkeys(motivos))
                )
            else:
                diagnostico = None

            # Estruturação do resumo analítico por persona para retorno imediato na API
            personas_lista = [
                {
                    "persona": res["persona"],
                    "analise": res["analise"],
                    "reasoning": res.get("reasoning"),
                    "urls_fonte": res["urls_fonte"],
                    "queries_executadas": res.get("queries_executadas", 0),
                    "falha_coleta": res.get("evidencia_vazia", False),
                    "diagnostico": res.get("erro_provedor"),
                }
                for res in persona_results
            ]
            sintese_consolidada = "\n\n".join(
                f"### Perspectiva {res['persona'].capitalize()}\n\n{res['analise']}"
                for res in persona_results
            )

            # RF-06/CA-06.1 e CA-06.2: status de falha e justificativa persistidos
            # sem apagar coletas anteriores (CA-06.3).
            async with session_lock:
                await self.research_repo.update_point_status(
                    ponto.ponto_id,
                    status=status_ponto,
                    pontos_fracos=diagnostico,
                )

            return {
                "ponto_id": ponto.ponto_id,
                "ponto_n": ponto.ponto_n,
                "status": status_ponto,
                "tentativas": (ponto.tentativas or 0) + 1,
                "total_personas": len(self.personas),
                "total_queries_executadas": total_queries_ponto,
                "total_urls_lidas": len(urls_lidas_dedup),
                "total_urls_fonte": len(urls_fonte_dedup),
                "tamanho_conteudo_caracteres": len(conteudo_consolidado),
                "falha_coleta": falha_coleta,
                "diagnostico": diagnostico,
                "personas": personas_lista,
                "conteudo_relevante": sintese_consolidada,
            }

        # Processamento ordenado por ponto, garantindo paralelismo concorrente das 4 personas
        # dentro de cada ponto sem colisão de locks na sessão assíncrona do banco
        resumos = []
        for ponto in pontos_alvo:
            resumos.append(await _processar_ponto(ponto))

        pontos_falhados = [r for r in resumos if r["falha_coleta"]]

        return {
            "id_pesquisa": id_pesquisa,
            "total_pontos_processados": len(resumos),
            "status_pesquisa": "coletado",
            "total_falhas_coleta": len(pontos_falhados),
            "resumo_coletas": resumos,
        }
