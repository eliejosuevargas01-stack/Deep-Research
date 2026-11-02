"""Utilitário de simulação de rede com httpx.MockTransport.

Proêve simulação determinística de Jina SERP, Jina Reader, inferência LLM
OpenAI-compatible (modelos leve e forte) e despacho de Webhook com captura de headers.
Atende a DT-11, RNF-06 e RNF-11.
"""

from collections import deque
import json
from typing import Any, Callable, Dict, List, Optional
import httpx


class MockNetwork:
    """Simulador determinístico de integrações HTTP externas."""

    def __init__(self) -> None:
        self.requests: List[httpx.Request] = []
        self._jina_status_queue: deque[int] = deque()
        self._llm_status_queue: deque[int] = deque()
        self._webhook_status_queue: deque[int] = deque()
        self.custom_handlers: Dict[str, Callable[[httpx.Request], httpx.Response]] = {}

    def record_request(self, request: httpx.Request) -> None:
        """Registra a requisição efetuada para fins de asserção em testes."""
        self.requests.append(request)

    def set_jina_status_sequence(self, statuses: List[int]) -> None:
        """Configura sequência de códigos de resposta para chamadas Jina (ex: [429, 429, 200])."""
        self._jina_status_queue = deque(statuses)

    def set_llm_status_sequence(self, statuses: List[int]) -> None:
        """Configura sequência de códigos de resposta para chamadas LLM."""
        self._llm_status_queue = deque(statuses)

    def set_webhook_status_sequence(self, statuses: List[int]) -> None:
        """Configura sequência de códigos de resposta para chamadas Webhook."""
        self._webhook_status_queue = deque(statuses)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Roteia deterministicamente a requisição HTTP mockada."""
        self.record_request(request)
        url_str = str(request.url)

        # 1. Roteamento de Handlers Customizados
        for pattern, handler in self.custom_handlers.items():
            if pattern in url_str:
                if "chat/completions" in pattern or "chat/completions" in url_str:
                    try:
                        req_body = json.loads(request.content.decode("utf-8"))
                        msgs_text = str(req_body.get("messages", []))
                    except Exception:
                        msgs_text = ""
                    is_eval_request = (
                        "Avaliador Semântico" in msgs_text
                        or "avaliador_semantico" in msgs_text
                        or "avaliação semântica" in msgs_text.lower()
                        or "sobreposição de eixos" in msgs_text.lower()
                    )
                    if is_eval_request and "avaliador_semantico" not in self.custom_handlers:
                        # Executa o handler customizado para verificar se ele especificamente proveu resposta de avaliação
                        res = handler(request)
                        try:
                            res_json = json.loads(res.content.decode("utf-8"))
                            choices = res_json.get("choices", [])
                            content_str = choices[0].get("message", {}).get("content", "") if choices else ""
                            parsed_content = json.loads(content_str) if content_str else {}
                        except Exception:
                            parsed_content = {}
                        if isinstance(parsed_content, dict) and "eixos" in parsed_content and "aprovado" not in parsed_content:
                            # Caso o handler customizado trate apenas geração de plano (mock legado),
                            # delega ao mock padrão do avaliador semântico
                            break
                        return res
                return handler(request)

        # 2. Jina SERP (s.jina.ai ou api.jina.ai/v1/search)
        if "s.jina.ai" in url_str or "api.jina.ai" in url_str:
            status = self._jina_status_queue.popleft() if self._jina_status_queue else 200
            if status >= 400:
                return httpx.Response(status, json={"error": f"Jina SERP Error {status}"})

            serp_data = {
                "code": 200,
                "data": [
                    {
                        "title": "A Inteligência Artificial na Educação Básica: Diretrizes da UNESCO",
                        "url": "https://unesdoc.unesco.org/ark:/48223/pf0000377897",
                        "description": "Relatório analítico sobre integração pedagógica de modelos generativos...",
                        "content": "# Relatório UNESCO\nA inteligência artificial generativa transforma dinâmicas escolares. Estudos da UNESCO indicam a urgência de capacitação docente e redução de assimetrias.",
                    },
                    {
                        "title": "Impactos do Uso de IA em Salas de Aula: Evidências Recentes",
                        "url": "https://www.oecd.org/education/ai-in-classrooms.htm",
                        "description": "Estudo comparativo da OCDE sobre desempenho acadêmico e equidade digital...",
                        "content": "# Estudo OCDE\nEstudo comparativo da OCDE sobre desempenho acadêmico e equidade digital...",
                    },
                    {
                        "title": "Políticas Públicas para IA Responsável no Ensino",
                        "url": "https://mec.gov.br/ia-educacao",
                        "description": "Marcos regulatórios e diretrizes para aplicação de IA na educação pública...",
                        "content": "# Políticas Públicas MEC\nMarcos regulatórios e diretrizes para aplicação de IA na educação pública...",
                    },
                ],
            }
            return httpx.Response(200, json=serp_data)

        # 3. Jina Reader (r.jina.ai)
        if "r.jina.ai" in url_str:
            status = self._jina_status_queue.popleft() if self._jina_status_queue else 200
            if status >= 400:
                return httpx.Response(status, json={"error": f"Jina Reader Error {status}"})

            sample_markdown = (
                "# Conteúdo Web Integral Coletado\n\n"
                "A inteligência artificial generativa transforma dinâmicas escolares. "
                "Estudos da UNESCO indicam a urgência de capacitação docente e redução "
                "de assimetrias de conectividade em regiões rurais. A fonte primária atesta "
                "que 68% das escolas carecem de diretrizes formais para integridade acadêmica."
            )
            return httpx.Response(
                200,
                text=sample_markdown,
                headers={"Content-Type": "text/markdown; charset=utf-8"},
            )

        # 4. OpenAI-Compatible LLM (/chat/completions)
        if "chat/completions" in url_str:
            status = self._llm_status_queue.popleft() if self._llm_status_queue else 200
            if status >= 400:
                return httpx.Response(status, json={"error": {"message": f"LLM Error {status}"}})

            try:
                payload = json.loads(request.content.decode("utf-8"))
            except Exception:
                payload = {}

            tools = payload.get("tools")
            messages = payload.get("messages", [])
            messages_text = str(messages)

            # Suporte ao loop agêntico com tools do Searcher
            if tools:
                has_tool_res = any(m.get("role") == "tool" for m in messages if isinstance(m, dict))
                if not has_tool_res:
                    return httpx.Response(
                        200,
                        json={
                            "id": "chatcmpl-mock-tool",
                            "object": "chat.completion",
                            "created": 1729530000,
                            "model": payload.get("model", "gemini-3.5-flash-lite"),
                            "choices": [
                                {
                                    "index": 0,
                                    "message": {
                                        "role": "assistant",
                                        "content": None,
                                        "tool_calls": [
                                            {
                                                "id": "call_mock_1",
                                                "type": "function",
                                                "function": {
                                                    "name": "jina_search",
                                                    "arguments": json.dumps({"query": "busca formulada pela persona"}),
                                                },
                                            }
                                        ],
                                    },
                                    "finish_reason": "tool_calls",
                                }
                            ],
                        },
                    )

            # Roteamento priorizado pela persona específica declarada no SYSTEM role
            # (regressão R5): o contexto legítimo do avaliador auditor_redacao contém
            # plano/pontos/eixos da pesquisa; regras amplas por texto integral
            # direcionariam o avaliador do artigo ao JSON do planejador. A persona
            # específica do system vem ANTES das regras amplas; o texto integral
            # permanece disponível dentro do branch para extrair refs/URLs.
            system_text = " ".join(
                m.get("content", "") for m in messages
                if isinstance(m, dict) and m.get("role") == "system"
            )

            # Resposta estruturada conforme persona solicitada no prompt
            if "auditor_redacao" in system_text:
                import re as _re_match
                found_claims = _re_match.findall(r"\"claim_id\":\s*\"([^\"]+)\"", messages_text)
                found_sources = _re_match.findall(r"\"source_id\":\s*\"([^\"]+)\"", messages_text)
                if not found_sources:
                    found_urls = _re_match.findall(r"https?://[^\s)\]\"'>]+", messages_text)
                    valid_urls = [u for u in found_urls if not any(x in u for x in ("api.openai.com", "webhook", "callback"))]
                    found_sources = valid_urls[:1] if valid_urls else []
                claim_ref = [found_claims[0]] if found_claims else []
                source_ref = [found_sources[0]] if found_sources else []
                content = json.dumps(
                    {
                        "resumo_avaliacao": "Artigo avaliado e aprovado com mérito analítico e rigor metodológico.",
                        "criterios": [
                            {
                                "id": i,
                                "aprovado": True,
                                "justificativa": f"Critério {i} integralmente satisfeito com fontes verificáveis.",
                                "claim_ids": claim_ref,
                                "source_ids": source_ref,
                                "correcao": None,
                            }
                            for i in range(1, 13)
                        ],
                    },
                    ensure_ascii=False,
                )
            elif (
                "avaliador_semantico" in messages_text
                or "avaliacao_semantica" in messages_text
                or "avaliação semântica" in messages_text.lower()
                or "avaliador do plano" in messages_text.lower()
                or "sobreposição de eixos" in messages_text.lower()
            ):
                user_msgs = [m.get("content", "") for m in (payload.get("messages") or []) if isinstance(m, dict) and m.get("role") == "user"]
                user_content = " ".join(user_msgs).lower()
                has_overlap = "forçar_sobreposicao" in user_content or "paráfrase intencional" in user_content or "duplicidade intencional" in user_content
                import re as _re_mock
                eixo_matches = _re_mock.findall(r"eixo\s+(\d+):", user_content)
                n_eixos = max([int(m) for m in eixo_matches]) if eixo_matches else 1
                if n_eixos > 1:
                    eval_pairs = [
                        {
                            "eixo_1": i,
                            "eixo_2": j,
                            "sobreposto": (has_overlap and i == 1 and j == 2),
                            "justificativa": (
                                "Eixos redundantes com paráfrases de mesmo escopo"
                                if (has_overlap and i == 1 and j == 2)
                                else f"Eixos {i} e {j} são complementares"
                            ),
                        }
                        for i in range(1, n_eixos)
                        for j in range(i + 1, n_eixos + 1)
                    ]
                else:
                    eval_pairs = []

                content = json.dumps(
                    {
                        "aprovado": not has_overlap,
                        "preservacao_publico": True,
                        "preservacao_escopo": True,
                        "preservacao_tempo": True,
                        "sobreposicao_eixos": eval_pairs,
                        "justificativa": "Sobreposição detectada em teste" if has_overlap else "Plano investigativo aprovado sem redundâncias.",
                    },
                    ensure_ascii=False,
                )
            elif (
                "protocolo de ações em json" in messages_text.lower()
                or "protocolo de acoes em json" in messages_text.lower()
                or "você é a persona historiador" in messages_text.lower()
                or "você é a persona visionário" in messages_text.lower()
                or "você é a persona visionario" in messages_text.lower()
                or "você é a persona cético" in messages_text.lower()
                or "você é a persona cetico" in messages_text.lower()
                or "você é a persona futurista" in messages_text.lower()
            ):
                import re as _re_search
                has_delivered_evidence = "trecho id: chk_" in messages_text.lower() or "trechos id" in messages_text.lower()
                if has_delivered_evidence:
                    user_msgs_text = " ".join([m.get("content", "") for m in messages if isinstance(m, dict) and m.get("role") == "user"])
                    chk_ids = _re_search.findall(r"\[Trecho ID:\s*(chk_[a-zA-Z0-9_\-]+)\]", user_msgs_text)
                    if not chk_ids:
                        chk_ids = [c for c in _re_search.findall(r"chk_[a-zA-Z0-9_\-]+", user_msgs_text) if c != "chk_id"]
                    chk_ref = chk_ids[0] if chk_ids else "chk_1"
                    content = json.dumps(
                        {
                            "acao": "concluir",
                            "analise_final": "Síntese analítica detalhada com base em fontes canônicas e evidências primárias apuradas na investigação.",
                            "conclusoes": [
                                {
                                    "claim_id": "clm_1",
                                    "afirmacao": "Evidência comprovada em fontes canônicas primárias.",
                                    "tipo": "fato",
                                    "evidencias": [chk_ref],
                                    "confianca": "alta",
                                    "limitacoes": "Ressalvas metodológicas documentadas.",
                                }
                            ],
                            "lacunas": [],
                            "motivo_parada": "Evidências canônicas suficientes obtidas.",
                        },
                        ensure_ascii=False,
                    )
                else:
                    content = json.dumps(
                        {
                            "acao": "buscar",
                            "consulta": "consulta formulada pela persona",
                            "objetivo": "buscar fontes canônicas na web",
                        },
                        ensure_ascii=False,
                    )
            elif "redator final" in messages_text or "dossiê analítico final" in messages_text.lower():
                import re as _re_url
                found_urls = _re_url.findall(r"https?://[^\s)\]\"',]+", messages_text)
                valid_doc_urls = [u for u in found_urls if not any(x in u for x in ("api.openai.com", "webhook", "callback", "localhost"))]
                ref_urls = list(dict.fromkeys(valid_doc_urls))
                if not ref_urls:
                    ref_urls = ["https://unesdoc.unesco.org/ark:/48223/pf0000377897"]
                ref_lines = "\n".join(f"{idx}. {u}" for idx, u in enumerate(ref_urls[:3], 1))
                content = (
                    "# Dossiê Analítico: Impacto da IA na Educação\n\n"
                    "## 1. Sumário Executivo\n"
                    "A integração de IA generativa traz ganhos significativos no letramento personalizado.\n\n"
                    "## 2. Desenvolvimento dos Eixos Temáticos\n"
                    "Análise detalhada sobre infraestrutura, capacitação pedagógica e integridade acadêmica.\n\n"
                    "## 3. Ressalvas e Limitações Metodológicas\n"
                    "Persistem assimetrias regionais não documentadas com dados censitários atualizados.\n\n"
                    "## 4. Referências e Fontes Canônicas\n"
                    f"{ref_lines}\n"
                )
            elif "planejador" in messages_text or "pontos" in messages_text or "eixos" in messages_text:
                import re as _re_eixos
                m_exact = _re_eixos.search(r"exatamente\s+(\d+)\s+eixos", messages_text, _re_eixos.IGNORECASE)
                if m_exact:
                    n_count = int(m_exact.group(1))
                elif "exatamente 1 " in messages_text or "1 eixos" in messages_text or "1 pontos" in messages_text:
                    n_count = 1
                else:
                    n_count = 5
                sample_eixos = [
                    {
                        "pergunta_principal": "Adoção de tutores inteligentes baseados em IA e impactos no letramento",
                        "subperguntas": ["Como ferramentas de IA apoiam a alfabetização em turmas heterogêneas?"],
                        "hipoteses": ["Tutores de IA reduzem o tempo de aquisição de leitura básica em 20%."],
                        "consultas_iniciais": ["ia generativa letramento unesco relatorio"],
                        "fontes_primarias_desejadas": ["Relatórios de avaliação pedagógica e diretrizes UNESCO"],
                        "riscos_de_vies": ["Superestimação de benefícios por fornecedores de software"],
                        "evidencias_que_refutariam": ["Estudo empírico independente demonstrando estagnação"],
                        "criterio_de_conclusao": "Corroboração com pelo menos dois estudos independentes",
                        "investigabilidade": "Viável via repositórios acadêmicos e bases abertas da UNESCO",
                        "eixo_essencial": True,
                    },
                    {
                        "pergunta_principal": "Desafios de plágio, integridade acadêmica e novas diretrizes de avaliação",
                        "subperguntas": ["Quais mecanismos institucionais foram adotados contra fraudes?"],
                        "hipoteses": ["Instituições substituem testes remotos por avaliações orais."],
                        "consultas_iniciais": ["integridade academica ia diretrizes ocde"],
                        "fontes_primarias_desejadas": ["Regulamentos de universidades e diretrizes da OCDE"],
                        "riscos_de_vies": ["Foco desproporcional em punição em detrimento de formação"],
                        "evidencias_que_refutariam": ["Aumento de casos sem qualquer alteração avaliativa"],
                        "criterio_de_conclusao": "Mapeamento de 3 marcos institucionais vigentes",
                        "investigabilidade": "Documentação pública disponível em portais acadêmicos",
                        "eixo_essencial": True,
                    },
                    {
                        "pergunta_principal": "Desigualdade no acesso digital e assimetrias regionais de infraestrutura",
                        "subperguntas": ["Como a disparidade de conectividade afeta escolas rurais?"],
                        "hipoteses": ["Escolas sem banda larga ficam excluídas de ferramentas avançadas."],
                        "consultas_iniciais": ["censo escolar conectividade assimetrias mec"],
                        "fontes_primarias_desejadas": ["Dados censitários e relatórios governamentais de infraestrutura"],
                        "riscos_de_vies": ["Subnotificação de carências regionais"],
                        "evidencias_que_refutariam": ["Universalização comprovada de acesso em todas as regiões"],
                        "criterio_de_conclusao": "Dados estatísticos oficiais comprovando a cobertura",
                        "investigabilidade": "Dados abertos em microdados censitários do MEC",
                        "eixo_essencial": True,
                    },
                    {
                        "pergunta_principal": "Formação continuada e capacitação do corpo docente para uso pedagógico de IA",
                        "subperguntas": ["Quais programas formais de capacitação existem para professores?"],
                        "hipoteses": ["Menos de 30% dos professores receberam treinamento estruturado."],
                        "consultas_iniciais": ["capacitacao docente ia unesco pesquisa"],
                        "fontes_primarias_desejadas": ["Pesquisas com amostras representativas de docentes"],
                        "riscos_de_vies": ["Amostragem concentrada em grandes centros urbanos"],
                        "evidencias_que_refutariam": ["Programas governamentais obrigatórios com 100% de adesão"],
                        "criterio_de_conclusao": "Pesquisa amostral canônica com metodologia transparente",
                        "investigabilidade": "Relatórios de pesquisa disponíveis publicamente",
                        "eixo_essencial": True,
                    },
                    {
                        "pergunta_principal": "Marcos regulatórios internacionais e políticas públicas de proteção à infância",
                        "subperguntas": ["Quais salvaguardas de privacidade de dados infantis são exigidas?"],
                        "hipoteses": ["Regulamentações impõem consentimento parental estrito para menores."],
                        "consultas_iniciais": ["regulacao ia protecao dados infancia gdpr lgpd"],
                        "fontes_primarias_desejadas": ["Legislação vigente (LGPD, AI Act, GDPR) e pareceres jurídicos"],
                        "riscos_de_vies": ["Interpretação abstrata da lei sem jurisprudência consolidada"],
                        "evidencias_que_refutariam": ["Inexistência de cláusulas específicas para menores"],
                        "criterio_de_conclusao": "Citação dos artigos canônicos das leis pertinentes",
                        "investigabilidade": "Textos oficiais das leis em diários oficiais",
                        "eixo_essencial": True,
                    },
                ]
                base_len = len(sample_eixos)
                while len(sample_eixos) < n_count:
                    idx = len(sample_eixos) + 1
                    base = sample_eixos[(idx - 1) % base_len].copy()
                    base["pergunta_principal"] = f"{base['pergunta_principal']} (Dimensão {idx})"
                    sample_eixos.append(base)
                sample_eixos = sample_eixos[:n_count]

                user_msgs = [m.get("content", "") for m in (payload.get("messages") or []) if isinstance(m, dict) and m.get("role") == "user"]
                user_text = " ".join(user_msgs).lower()
                is_crianca = (
                    "criança" in user_text
                    or "crianca" in user_text
                    or "infantil" in user_text
                    or "criança de 5 anos" in user_text
                    or "para o meu filho de 5 anos" in user_text
                )
                publico = "Infantil (criança de 5 anos)" if is_crianca else "Educadores e pesquisadores"
                formato = "Explicação didática com analogias simples" if is_crianca else "Dossiê analítico com citações"

                content = json.dumps(
                    {
                        "pedido_original": "Tema Investigado",
                        "pedido_normalizado": "Escopo investigativo delimitado",
                        "publico": publico,
                        "formato_entrega": formato,
                        "recorte_temporal": "Últimos 3 anos",
                        "pressupostos": ["Metadados SERP tratados como pistas preliminares"],
                        "ambiguidades": [],
                        "eixos": sample_eixos,
                        "pontos": [e["pergunta_principal"] for e in sample_eixos],
                    },
                    ensure_ascii=False,
                )
            elif "auditor" in messages_text or "12 perguntas" in messages_text:
                found_claims = []
                found_sources = []
                try:
                    user_msgs = [m.get("content", "") for m in (payload.get("messages") or []) if isinstance(m, dict) and m.get("role") == "user"]
                    if user_msgs:
                        parsed_ctx = json.loads(user_msgs[-1])
                        for r_p in parsed_ctx.get("resultados_personas", {}).values():
                            if isinstance(r_p, dict):
                                for c_it in r_p.get("conclusoes", []):
                                    if isinstance(c_it, dict) and c_it.get("claim_id"):
                                        found_claims.append(str(c_it["claim_id"]))
                        fontes_ctx = parsed_ctx.get("fontes", {})
                        if isinstance(fontes_ctx, dict):
                            found_sources = list(fontes_ctx.keys())
                        elif isinstance(fontes_ctx, list):
                            found_sources = [
                                str(f.get("url")) for f in fontes_ctx
                                if isinstance(f, dict) and f.get("url")
                            ]
                except Exception:
                    pass

                claims_to_use = found_claims or [f"claim_{i}" for i in range(1, 5)]
                sources_to_use = found_sources or ["https://php.net/security-2026"]

                content = json.dumps(
                    {
                        "status": "aprovado",
                        "pontos_fracos": None,
                        "resumo_auditoria": "Ponto com evidências sólidas e fontes canônicas verificadas.",
                        "criterios": [
                            {
                                "id": i,
                                "aprovado": True,
                                "justificativa": f"Critério {i} atendido com evidências canônicas verificáveis.",
                                "claim_ids": [claims_to_use[0]],
                                "source_ids": [sources_to_use[0]],
                                "lacuna": None,
                                "correcao": None,
                                "personas_pertinentes": [],
                            }
                            for i in range(1, 13)
                        ],
                    },
                    ensure_ascii=False,
                )
            else:
                # Persona redator final ou padrão
                import re as _re_url
                found_urls = _re_url.findall(r"https?://[^\s)\]\"'>]+", messages_text)
                ref_urls = list(dict.fromkeys(found_urls))
                if not ref_urls:
                    ref_urls = ["https://unesdoc.unesco.org/ark:/48223/pf0000377897"]
                ref_lines = "\n".join(f"{idx}. {u}" for idx, u in enumerate(ref_urls[:3], 1))
                content = (
                    "# Dossiê Analítico: Impacto da IA na Educação\n\n"
                    "## 1. Sumário Executivo\n"
                    "A integração de IA generativa traz ganhos significativos no letramento personalizado.\n\n"
                    "## 2. Desenvolvimento dos Eixos Temáticos\n"
                    "Análise detalhada sobre infraestrutura, capacitação pedagógica e integridade acadêmica.\n\n"
                    "## 3. Ressalvas e Limitações Metodológicas\n"
                    "Persistem assimetrias regionais não documentadas com dados censitários atualizados.\n\n"
                    "## 4. Referências e Fontes Canônicas\n"
                    f"{ref_lines}\n"
                )

            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-mock-12345",
                    "object": "chat.completion",
                    "created": 1729530000,
                    "model": payload.get("model", "gpt-4o-mini"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": content,
                                "reasoning_content": "Raciocínio simulado para validação analítica.",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

        # 5. Callback Webhook (despacho com HMAC-SHA256)
        if "webhook" in url_str or "callback" in url_str:
            status = self._webhook_status_queue.popleft() if self._webhook_status_queue else 200
            if status >= 400:
                return httpx.Response(status, json={"error": f"Webhook Error {status}"})
            return httpx.Response(200, json={"status": "recebido", "evento": "research.completed"})

        # Fallback genérico para rotas não mapeadas
        return httpx.Response(200, json={"status": "ok", "url": url_str})


def create_mock_transport(mock_network: Optional[MockNetwork] = None) -> httpx.MockTransport:
    """Cria instância de MockTransport conectada ao simulador MockNetwork."""
    network = mock_network or MockNetwork()
    return httpx.MockTransport(network.handle_request)


def create_mock_client(mock_network: Optional[MockNetwork] = None) -> httpx.AsyncClient:
    """Cria AsyncClient com transporte de simulação determinística isolada."""
    network = mock_network or MockNetwork()
    transport = create_mock_transport(network)
    return httpx.AsyncClient(transport=transport)
