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

            # Resposta estruturada conforme persona solicitada no prompt
            if "planejador" in messages_text or "pontos" in messages_text:
                content = json.dumps(
                    {
                        "pontos": [
                            "Adoção de tutores inteligentes baseados em IA e impactos no letramento",
                            "Desafios de plágio, integridade acadêmica e novas diretrizes de avaliação",
                            "Desigualdade no acesso digital e assimetrias regionais de infraestrutura",
                            "Formação continuada e capacitação do corpo docente para uso pedagógico de IA",
                            "Marcos regulatórios internacionais e políticas públicas de proteção à infância",
                        ]
                    },
                    ensure_ascii=False,
                )
            elif "auditor" in messages_text or "12 perguntas" in messages_text:
                content = json.dumps(
                    {
                        "status": "aprovado",
                        "pontos_fracos": None,
                        "resumo_auditoria": "Ponto com evidências sólidas, citações canônicas da UNESCO e dados consistentes.",
                        "criterios": {
                            "clareza_tematica": True,
                            "corroboracao_canonica": True,
                            "atualidade": True,
                            "ausencia_contradicoes": True,
                            "embasamento_factual": True,
                            "aderencia_escopo": True,
                            "profundidade_analitica": True,
                            "precisao_numerica": True,
                            "neutralidade": True,
                            "densidade_evidencias": True,
                            "declaracao_incertezas": True,
                            "solidez_logica": True,
                        },
                    },
                    ensure_ascii=False,
                )
            else:
                # Persona redator final ou padrão
                content = (
                    "# Dossiê Analítico: Impacto da IA na Educação\n\n"
                    "## 1. Sumário Executivo\n"
                    "A integração de IA generativa traz ganhos significativos no letramento personalizado.\n\n"
                    "## 2. Desenvolvimento dos Eixos Temáticos\n"
                    "Análise detalhada sobre infraestrutura, capacitação pedagógica e integridade acadêmica.\n\n"
                    "## 3. Ressalvas e Limitações Metodológicas\n"
                    "Persistem assimetrias regionais não documentadas com dados censitários atualizados.\n\n"
                    "## 4. Referências e Fontes Canônicas\n"
                    "1. https://unesdoc.unesco.org/ark:/48223/pf0000377897\n"
                    "2. https://www.oecd.org/education/ai-in-classrooms.htm\n"
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
