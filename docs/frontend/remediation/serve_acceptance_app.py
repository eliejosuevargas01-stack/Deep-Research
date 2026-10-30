"""Acceptance server and provider fixture wrapper for integrated frontend/backend validation.

Runs on localhost:8011 serving the actual app.main using its own native routes
(including /{full_path:path} and /app/session) with compiled frontend/dist and
actual browser-session auth. External providers (Jina, LLM, Webhook) are simulated
via AcceptanceMockNetwork, an enhanced subclass of tests.mocks.http_mock.MockNetwork
supporting dynamic requested point counts (1..5) while keeping the semantic evaluator,
searcher personas, auditor and writer branches untouched.

No synthetic routes, fallback handlers or auth overrides are added by this harness.
Missing real UI or session integration fails immediately with an explicit error.

Usage:
    .venv/bin/python docs/frontend/remediation/serve_acceptance_app.py --self-check
    .venv/bin/python docs/frontend/remediation/serve_acceptance_app.py --port 8011
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.mocks.http_mock import MockNetwork

# Extração preguiçosa dos 5 eixos canônicos gerados pelo MockNetwork original (sem duplicação estática)
_CANONICAL_SAMPLE_EIXOS: Optional[List[Dict[str, Any]]] = None

LONG_PLAN_TRIGGER_TOPIC = "Energia solar: plano extenso para verificação visual"
_LONG_PLAN_FIXTURE_PATH = ROOT / "docs/frontend/remediation/fixtures/long-plan-public.json"
_LONG_PLAN_CACHE: Optional[Dict[str, Any]] = None


def get_canonical_sample_eixos() -> List[Dict[str, Any]]:
    """Recupera os 5 eixos canônicos de teste gerados originalmente por MockNetwork."""
    global _CANONICAL_SAMPLE_EIXOS
    if _CANONICAL_SAMPLE_EIXOS is None:
        req = httpx.Request(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            json={"messages": [{"role": "system", "content": "planejador com 5 eixos"}]},
        )
        res = MockNetwork().handle_request(req)
        data = json.loads(json.loads(res.content.decode("utf-8"))["choices"][0]["message"]["content"])
        _CANONICAL_SAMPLE_EIXOS = [dict(e) for e in data.get("eixos", [])]
    return _CANONICAL_SAMPLE_EIXOS


def get_long_plan_data() -> Dict[str, Any]:
    """Carrega o plano longo público extraído de execução real, com cache em memória."""
    global _LONG_PLAN_CACHE
    if _LONG_PLAN_CACHE is None:
        if not _LONG_PLAN_FIXTURE_PATH.is_file():
            raise FileNotFoundError(f"Arquivo de fixture de plano longo ausente em {_LONG_PLAN_FIXTURE_PATH}")
        raw = json.loads(_LONG_PLAN_FIXTURE_PATH.read_text(encoding="utf-8"))
        plano = raw.get("plano_estruturado", raw)
        plano_copy = dict(plano)
        plano_copy["pedido_original"] = LONG_PLAN_TRIGGER_TOPIC
        plano_copy["pontos"] = [e["pergunta_principal"] for e in plano_copy["eixos"]]
        _LONG_PLAN_CACHE = plano_copy
    return dict(_LONG_PLAN_CACHE)


class AcceptanceMockNetwork(MockNetwork):
    """Simulador de rede para aceitação com contagem dinâmica de pontos (1..5).

    Subclasse de tests.mocks.http_mock.MockNetwork que inspeciona o prompt do planejador
    (app/core/planner.py) e ajusta a resposta determinística de eixos/pontos para a contagem
    solicitada (1..5), preservando intocados os branches do avaliador semântico, do searcher,
    do auditor e do redator.
    """

    COUNT_PATTERNS = [
        re.compile(r"decomponha a investiga[çc][ãa]o em exatamente\s+(\d+)\s+eixos", re.IGNORECASE),
        re.compile(r"formule o plano investigativo estruturado em json com exatamente\s+(\d+)\s+eixos", re.IGNORECASE),
        re.compile(r"gere novamente o objeto json (?:completo|estrito) com exatamente\s+(\d+)\s+eixos", re.IGNORECASE),
        re.compile(r"lista com exatamente\s+(\d+)\s+objetos", re.IGNORECASE),
        re.compile(r"exatamente\s+(\d+)\s+eixos investigativos", re.IGNORECASE),
        re.compile(r"\bexatamente\s+(\d+)\s+(?:eixos|pontos)\b", re.IGNORECASE),
    ]

    def extract_requested_count(self, messages_text: str) -> Optional[int]:
        """Extrai o número exato de pontos/eixos configurado pelo planejador no prompt.

        Ignora valores numéricos pertencentes ao tema do usuário buscando especificamente
        as frases estruturadas de diretriz emitidas por app/core/planner.py.
        """
        for pat in self.COUNT_PATTERNS:
            m = pat.search(messages_text)
            if m:
                try:
                    return int(m.group(1))
                except (ValueError, TypeError):
                    continue
        return None

    def extract_topic(self, messages: list) -> Optional[str]:
        """Extrai o tema da investigação enviado no prompt do usuário."""
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "user":
                content = str(m.get("content", ""))
                match = re.search(r"Tema da Investigação:\s*([^\n\r]+)", content)
                if match:
                    return match.group(1).strip()
        return None

    def is_long_plan_request(self, messages: list, messages_text: str) -> bool:
        """Identifica opt-in do tema específico de verificação visual de plano extenso."""
        topic = self.extract_topic(messages)
        if topic is not None:
            return topic == LONG_PLAN_TRIGGER_TOPIC
        return LONG_PLAN_TRIGGER_TOPIC in messages_text

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "chat/completions" not in url_str:
            return super().handle_request(request)

        try:
            body_data = json.loads(request.content.decode("utf-8"))
        except Exception:
            body_data = {}

        # 1. Ferramentas e chamadas de function do searcher
        if body_data.get("tools"):
            return super().handle_request(request)

        messages = body_data.get("messages", [])
        messages_text = " ".join(str(m.get("content", "")) for m in messages if isinstance(m, dict))
        system_text = " ".join(
            str(m.get("content", "")) for m in messages if isinstance(m, dict) and m.get("role") == "system"
        )

        # 2. Avaliador Semântico do Plano (preservar intacto)
        is_eval_request = (
            "avaliador_semantico" in messages_text
            or "avaliacao_semantica" in messages_text
            or "avaliação semântica" in messages_text.lower()
            or "avaliador do plano" in messages_text.lower()
            or "sobreposição de eixos" in messages_text.lower()
        )
        if is_eval_request:
            return super().handle_request(request)

        # 3. Auditor de Redação (preservar intacto)
        if "auditor_redacao" in system_text:
            return super().handle_request(request)

        # 4. Searcher / Personas de Investigação (preservar intacto)
        is_searcher = (
            "protocolo de ações em json" in messages_text.lower()
            or "protocolo de acoes em json" in messages_text.lower()
            or any(
                f"você é a persona {p}" in messages_text.lower()
                for p in ("historiador", "visionário", "visionario", "cético", "cetico", "futurista")
            )
        )
        if is_searcher:
            return super().handle_request(request)

        # 5. Redator Final / Dossiê (preservar intacto)
        if (
            "redator final" in messages_text.lower()
            or "dossiê analítico final" in messages_text.lower()
            or "dossie analitico final" in messages_text.lower()
        ):
            return super().handle_request(request)

        # 6. Auditor de Fatos / 12 Perguntas (preservar intacto)
        if "auditor" in messages_text.lower() and (
            "12 perguntas" in messages_text.lower() or "resultados_personas" in messages_text.lower()
        ):
            return super().handle_request(request)

        # 7. Geração do Planejador Investigativo
        is_planner = (
            "planejador" in messages_text.lower()
            or "planejador investigativo" in system_text.lower()
            or ("eixos" in messages_text.lower() and "pontos" in messages_text.lower())
        )
        if not is_planner:
            return super().handle_request(request)

        req_count = self.extract_requested_count(messages_text)

        # 8. Opt-in do tema específico de plano longo para verificação visual
        if self.is_long_plan_request(messages, messages_text):
            if req_count != 2:
                self.record_request(request)
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "message": (
                                f"Marker topic '{LONG_PLAN_TRIGGER_TOPIC}' requires requested count 2 "
                                f"(requested {req_count})."
                            ),
                            "type": "invalid_request_error",
                            "code": "invalid_marker_count",
                        }
                    },
                    headers={"content-type": "application/json"},
                )
            self.record_request(request)
            long_plan = get_long_plan_data()
            content = json.dumps(long_plan, ensure_ascii=False)
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-mock-long-plan",
                    "object": "chat.completion",
                    "created": 1729530000,
                    "model": body_data.get("model", "gpt-4o-mini"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": content,
                                "reasoning_content": "Raciocínio simulado para validação do plano longo.",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
                headers={"content-type": "application/json"},
            )

        # Rejeição explícita de contagens de pontos fora da faixa suportada pela fixture (1..5)
        if req_count is not None and (req_count < 1 or req_count > 5):
            self.record_request(request)
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": (
                            f"Simulated external provider fixture only supports 1..5 points "
                            f"(requested {req_count})."
                        ),
                        "type": "invalid_request_error",
                        "code": "unsupported_fixture_count",
                    }
                },
                headers={"content-type": "application/json"},
            )

        # Invoca a resposta determinística padrão da fixture
        resp = super().handle_request(request)
        if req_count is None or resp.status_code >= 400:
            return resp

        # Ajusta a contagem de eixos e pontos na resposta do provedor simulado
        try:
            resp_data = json.loads(resp.content.decode("utf-8"))
            choices = resp_data.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                raw_content = msg.get("content", "")
                if raw_content:
                    content_obj = json.loads(raw_content)
                    if "eixos" in content_obj and isinstance(content_obj["eixos"], list):
                        canonical = get_canonical_sample_eixos()
                        source_eixos = (
                            content_obj["eixos"]
                            if len(content_obj["eixos"]) >= req_count
                            else canonical
                        )
                        selected_eixos = [dict(e) for e in source_eixos[:req_count]]
                        content_obj["eixos"] = selected_eixos
                        content_obj["pontos"] = [e["pergunta_principal"] for e in selected_eixos]
                        msg["content"] = json.dumps(content_obj, ensure_ascii=False)
                        choices[0]["message"] = msg
                        resp_data["choices"] = choices
                        return httpx.Response(
                            resp.status_code,
                            content=json.dumps(resp_data, ensure_ascii=False).encode("utf-8"),
                            headers=dict(resp.headers),
                        )
        except Exception:
            pass

        return resp


def patch_mock_transport() -> None:
    """Aplica o wrapper AcceptanceMockNetwork em tests.mocks.http_mock.

    Deve ser executado ANTES de importar app.main para que os endpoints
    (_get_transport) utilizem este simulador durante PYTEST_CURRENT_TEST.
    """
    import tests.mocks.http_mock as http_mock_mod

    http_mock_mod.MockNetwork = AcceptanceMockNetwork

    def create_acceptance_mock_transport(mock_network: Optional[MockNetwork] = None) -> httpx.MockTransport:
        network = mock_network or AcceptanceMockNetwork()
        return httpx.MockTransport(network.handle_request)

    http_mock_mod.create_mock_transport = create_acceptance_mock_transport


def configure_acceptance_env(temp_dir_path: Path) -> Dict[str, str]:
    """Configura o ambiente com isolamento estrito de SQLite e credenciais públicas de fixture.

    Não carrega arquivos .env locais para evitar contaminação com credenciais de produção.
    """
    from cryptography.fernet import Fernet

    db_file = temp_dir_path / "acceptance.db"
    fixtures = {
        "PYTEST_CURRENT_TEST": "tests/integration/acceptance_test_harness (call)",
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_file}",
        "CREDENTIALS_MASTER_KEY": Fernet.generate_key().decode(),
        "API_SECRET_KEY": "fixture-acceptance-secret-key-public",
        "OPENAI_API_KEY": "fixture-openai-key-simulated",
        "JINA_API_KEY": "fixture-jina-key-simulated",
        "Jina_API_KEY": "fixture-jina-key-simulated",
        "N_PONTOS": "1",
        "PERSONAS_CONFIG": "planejador,historiador,visionario,cetico,futurista,auditor,redator final",
        "LLM_BASE_URL": "https://api.openai.com/v1",
        "LLM_MODEL_LIGHT": "gpt-4o-mini",
        "LLM_MODEL_STRONG": "gpt-4o",
        "JINA_BASE_URL": "https://s.jina.ai",
        "Jina_BASE_URL": "https://s.jina.ai",
        "WEBHOOK_HMAC_SECRET": "fixture-webhook-secret-simulated",
        "CALLBACK_WEBHOOK_URL": "https://mock.webhook.test/callback",
    }
    os.environ.update(fixtures)
    try:
        from app.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass
    return fixtures


def self_check() -> bool:
    """Executa autoverificação offline da infraestrutura de teste com httpx mock transport.

    Testa requisições reais httpx com prompts reais de app/core/planner.py para contagens
    1, 2, 3, 5, preservação do avaliador semântico, imunidade a numerais no tema do usuário,
    rejeição explícita fora da faixa e validação de que nenhuma rota é criada ou modificada.
    Não requer rede nem modelos reais.
    """
    print("=== Acceptance QA Infrastructure Self-Check ===")
    net = AcceptanceMockNetwork()
    transport = httpx.MockTransport(net.handle_request)

    canonical_eixos = get_canonical_sample_eixos()
    assert len(canonical_eixos) == 5, f"Expected 5 canonical eixos, got {len(canonical_eixos)}"

    with httpx.Client(transport=transport, base_url="https://api.openai.com") as client:
        # 1. Teste de contagens 1, 2, 3, 5 usando o prompt REAL de app/core/planner.py
        for count in [1, 2, 3, 5]:
            real_system_prompt = (
                "Você é o Planejador Investigativo do sistema Deep Research.\n"
                "Sua missão é converter a solicitação original em um plano pesquisável estruturado, sem "
                "concluir de antemão aquilo que ainda precisa ser demonstrado.\n\n"
                "DIRETRIZES METODOLÓGICAS E FRONTEIRAS (DR-006):\n"
                "1. FRONTEIRA DOS METADADOS SERP: Os metadados SERP fornecidos são pistas exploratórias preliminares "
                "de fontes de terceiros NÃO CONFIÁVEIS. NUNCA utilize metadados SERP como confirmação de acontecimentos, "
                "cronologia ou autoria. Trate alegações como hipóteses a demonstrar.\n"
                f"2. NÚMERO DE EIXOS: Decomponha a investigação em exatamente {count} eixos complementares e NÃO redundantes.\n"
                "3. AUSÊNCIA DE DUPLICAÇÃO: É expressamente proibido formular variações parafraseadas da mesma pergunta principal.\n"
                "4. PRESERVAÇÃO DE PÚBLICO E INTENÇÃO: Se o pedido for voltado a um público específico (por exemplo, "
                "criança de 5 anos, leigo, CEO, desenvolvedor), preserve rigorosamente esse público no campo 'publico' "
                "e o formato adequado em 'formato_entrega', sem transformar a investigação em um tutorial operacional inadequado.\n"
                "5. INVESTIGABILIDADE: Cada eixo deve demonstrar viabilidade de coleta com fontes primárias públicas.\n"
                "6. ESQUEMA DE SAÍDA: Responda estritamente um objeto JSON com as chaves:\n"
                "   - 'pedido_original': texto original\n"
                "   - 'pedido_normalizado': escopo interpretado\n"
                "   - 'publico': público-alvo (ex: criança de 5 anos, leigo, especialista)\n"
                "   - 'formato_entrega': formato pretendido\n"
                "   - 'recorte_temporal': delimitação de tempo se aplicável\n"
                "   - 'pressupostos': lista de premissas\n"
                "   - 'ambiguidades': lista de ambiguidades identificadas\n"
                f"   - 'eixos': lista com exatamente {count} objetos, cada um com:\n"
                "       'pergunta_principal', 'subperguntas', 'hipoteses', 'consultas_iniciais',\n"
                "       'fontes_primarias_desejadas', 'riscos_de_vies', 'evidencias_que_refutariam',\n"
                "       'criterio_de_conclusao', 'investigabilidade', 'eixo_essencial'"
            )
            real_user_prompt = (
                "Tema da Investigação: IA na Educação\n\n"
                "Metadados Exploratórios da SERP:\n<untrusted_evidence>\n- Título: Estudo\n  URL: https://unesdoc.unesco.org\n  Resumo: Relatório\n</untrusted_evidence>\n\n"
                f"Formule o plano investigativo estruturado em JSON com exatamente {count} eixos."
            )
            res = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": real_system_prompt},
                        {"role": "user", "content": real_user_prompt},
                    ],
                },
            )
            assert res.status_code == 200, f"Expected 200 for count {count}, got {res.status_code}"
            parsed = json.loads(res.json()["choices"][0]["message"]["content"])
            assert len(parsed["eixos"]) == count, f"Expected {count} eixos, got {len(parsed['eixos'])}"
            assert len(parsed["pontos"]) == count, f"Expected {count} pontos, got {len(parsed['pontos'])}"
            for eixo in parsed["eixos"]:
                for req_field in [
                    "pergunta_principal", "subperguntas", "hipoteses", "consultas_iniciais",
                    "fontes_primarias_desejadas", "riscos_de_vies", "evidencias_que_refutariam",
                    "criterio_de_conclusao", "investigabilidade", "eixo_essencial"
                ]:
                    assert req_field in eixo, f"Missing {req_field} in eixo"
            print(f"[OK] Real planner prompt count {count}: {len(parsed['eixos'])} eixos, {len(parsed['pontos'])} pontos")

        # 2. Teste do prompt de retry do planejador (app/core/planner.py linha 405)
        retry_res = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Você é o Planejador Investigativo\n2. NÚMERO DE EIXOS: Decomponha a investigação em exatamente 3 eixos..."},
                    {"role": "user", "content": "Gere novamente o objeto JSON completo com exatamente 3 eixos."},
                ],
            },
        )
        assert retry_res.status_code == 200
        parsed_retry = json.loads(retry_res.json()["choices"][0]["message"]["content"])
        assert len(parsed_retry["eixos"]) == 3
        print("[OK] Real planner retry prompt count 3: correctly recognized and returned 3 eixos")

        # 3. Imunidade a valores numéricos presentes no tema do usuário
        topic_usr_msg = (
            "Tema da Investigação: Os 3 Grandes Pilares e 10 Leis da Automação em 2026\n\n"
            "Metadados Exploratórios da SERP:\n[Pistas]\n\n"
            "Formule o plano investigativo estruturado em JSON com exatamente 2 eixos."
        )
        res_topic = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": real_system_prompt.replace("exatamente 5 eixos", "exatamente 2 eixos").replace("exatamente 1 eixos", "exatamente 2 eixos")},
                    {"role": "user", "content": topic_usr_msg},
                ],
            },
        )
        assert res_topic.status_code == 200
        parsed_topic = json.loads(res_topic.json()["choices"][0]["message"]["content"])
        assert len(parsed_topic["eixos"]) == 2, f"Expected 2 eixos despite topic numbers, got {len(parsed_topic['eixos'])}"
        print(f"[OK] Topic number immunity (3/10/2026 ignored, count=2 respected): {len(parsed_topic['eixos'])} eixos")

        # 4. Rejeição explícita para contagens fora da faixa suportada (1..5)
        res_unsupported = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Você é o Planejador Investigativo\n2. NÚMERO DE EIXOS: Decomponha a investigação em exatamente 7 eixos..."},
                    {"role": "user", "content": "Formule o plano investigativo estruturado em JSON com exatamente 7 eixos."},
                ],
            },
        )
        assert res_unsupported.status_code == 400
        err_data = res_unsupported.json()
        assert "unsupported_fixture_count" in str(err_data) or "only supports 1..5 points" in str(err_data)
        print("[OK] Unsupported count rejection (7 -> HTTP 400): correctly rejected")

        # 5. Opt-in do Plano Longo ("Energia solar: plano extenso para verificação visual")
        # 5.1. Requisição com contagem 2 (sucesso com volume real e contagens 6/7)
        long_user_prompt = (
            f"Tema da Investigação: {LONG_PLAN_TRIGGER_TOPIC}\n\n"
            "Metadados Exploratórios da SERP:\n<untrusted_evidence>\n- Título: Energia Solar\n</untrusted_evidence>\n\n"
            "Formule o plano investigativo estruturado em JSON com exatamente 2 eixos."
        )
        res_long = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": real_system_prompt.replace("exatamente 5 eixos", "exatamente 2 eixos").replace("exatamente 1 eixos", "exatamente 2 eixos")},
                    {"role": "user", "content": long_user_prompt},
                ],
            },
        )
        assert res_long.status_code == 200, f"Expected 200 for long plan, got {res_long.status_code}"
        parsed_long = json.loads(res_long.json()["choices"][0]["message"]["content"])
        assert len(parsed_long["eixos"]) == 2, f"Expected 2 eixos, got {len(parsed_long['eixos'])}"
        subq_e1 = len(parsed_long["eixos"][0]["subperguntas"])
        subq_e2 = len(parsed_long["eixos"][1]["subperguntas"])
        assert subq_e1 == 6, f"Expected 6 subperguntas in eixo 1, got {subq_e1}"
        assert subq_e2 == 7, f"Expected 7 subperguntas in eixo 2, got {subq_e2}"
        total_subq_chars = sum(len(q) for e in parsed_long["eixos"] for q in e["subperguntas"])
        total_hyp_chars = sum(len(h) for e in parsed_long["eixos"] for h in e["hipoteses"])
        assert total_subq_chars > 1000, f"Expected realistic subquestions volume (>1000 chars), got {total_subq_chars}"
        assert total_hyp_chars > 800, f"Expected realistic hypotheses volume (>800 chars), got {total_hyp_chars}"
        print(
            f"[OK] Long plan fixture: 2 axes (subquestions {subq_e1}/{subq_e2}), "
            f"realistic volume ({total_subq_chars} subq chars, {total_hyp_chars} hyp chars)"
        )

        # 5.2. Validador Pydantic no Plano Longo
        from app.core.plan_validator import validate_and_parse_plan
        parsed_long_plan, long_err = validate_and_parse_plan(
            parsed_long, expected_n=2, tema_original=LONG_PLAN_TRIGGER_TOPIC
        )
        assert long_err is None, f"Expected validation success for long plan, got error: {long_err}"
        assert parsed_long_plan is not None
        assert len(parsed_long_plan.eixos) == 2
        print("[OK] Long plan Pydantic schema validation: passes validate_and_parse_plan")

        # 5.3. Avaliação semântica preservada no Plano Longo
        res_eval_long = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "Você é o Avaliador Semântico de Planos Investigativos do Deep Research.\nCRITÉRIOS DE AUDITORIA:\n4. SOBREPOSIÇÃO DE EIXOS...",
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Pedido do Usuário: {LONG_PLAN_TRIGGER_TOPIC}\n"
                            f"Eixos:\n"
                            f"Eixo 1: {parsed_long['eixos'][0]['pergunta_principal']}\n"
                            f"Eixo 2: {parsed_long['eixos'][1]['pergunta_principal']}\n"
                            "Realize a avaliação semântica estrita."
                        ),
                    },
                ],
            },
        )
        assert res_eval_long.status_code == 200
        eval_long_data = json.loads(res_eval_long.json()["choices"][0]["message"]["content"])
        assert eval_long_data["aprovado"] is True
        assert len(eval_long_data["sobreposicao_eixos"]) == 1
        print("[OK] Long plan semantic evaluator: aprovado=True, 1 complement pair preserved")

        # 5.4. Rejeição explícita quando contagem diferente de 2 é solicitada para o tema marcador
        for bad_count in [1, 3, 5]:
            bad_prompt = (
                f"Tema da Investigação: {LONG_PLAN_TRIGGER_TOPIC}\n\n"
                f"Formule o plano investigativo estruturado em JSON com exatamente {bad_count} eixos."
            )
            res_bad_marker = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": real_system_prompt.replace("exatamente 5 eixos", f"exatamente {bad_count} eixos").replace("exatamente 1 eixos", f"exatamente {bad_count} eixos")},
                        {"role": "user", "content": bad_prompt},
                    ],
                },
            )
            assert res_bad_marker.status_code == 400
            err_bad = res_bad_marker.json()
            assert "invalid_marker_count" in str(err_bad)
        print("[OK] Long plan wrong count rejection: counts 1, 3, 5 explicitly rejected with HTTP 400")

        # 6. Preservação do Avaliador Semântico (N=1 e N=3)
        res_eval_1 = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "Você é o Avaliador Semântico de Planos Investigativos do Deep Research.\nCRITÉRIOS DE AUDITORIA:\n4. SOBREPOSIÇÃO DE EIXOS...",
                    },
                    {
                        "role": "user",
                        "content": "Pedido do Usuário: IA na Educação\nEixos:\nEixo 1: Adoção de tutores...\nRealize a avaliação semântica estrita.",
                    },
                ],
            },
        )
        assert res_eval_1.status_code == 200
        eval_1 = json.loads(res_eval_1.json()["choices"][0]["message"]["content"])
        assert eval_1["aprovado"] is True
        assert eval_1["sobreposicao_eixos"] == []
        print("[OK] Semantic evaluator preserved for N=1: aprovado=True, sobreposicao_eixos=[]")

        res_eval_3 = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "Você é o Avaliador Semântico de Planos Investigativos do Deep Research.\nCRITÉRIOS DE AUDITORIA:\n4. SOBREPOSIÇÃO DE EIXOS...",
                    },
                    {
                        "role": "user",
                        "content": (
                            "Pedido do Usuário: IA na Educação\n"
                            "Eixos:\n"
                            "Eixo 1: Adoção de tutores...\n"
                            "Eixo 2: Desafios de plágio...\n"
                            "Eixo 3: Desigualdade no acesso...\n"
                            "Realize a avaliação semântica estrita."
                        ),
                    },
                ],
            },
        )
        assert res_eval_3.status_code == 200
        eval_3 = json.loads(res_eval_3.json()["choices"][0]["message"]["content"])
        assert eval_3["aprovado"] is True
        assert len(eval_3["sobreposicao_eixos"]) == 3
        print(f"[OK] Semantic evaluator preserved for N=3: aprovado=True, pairs={len(eval_3['sobreposicao_eixos'])}")

        # 6. Preservação dos ramos de Searcher, Auditor e Writer
        res_searcher = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Você é a persona historiador... Protocolo de ações em JSON."},
                    {"role": "user", "content": "Realize a coleta inicial."},
                ],
            },
        )
        assert res_searcher.status_code == 200
        search_data = json.loads(res_searcher.json()["choices"][0]["message"]["content"])
        assert "acao" in search_data
        print("[OK] Searcher persona branch preserved: returns action JSON")

        res_writer = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Você é o redator final... Elabore o dossiê analítico final."},
                    {"role": "user", "content": "Escreva o relatório final com base nas fontes coletadas."},
                ],
            },
        )
        assert res_writer.status_code == 200
        writer_text = res_writer.json()["choices"][0]["message"]["content"]
        assert "Dossiê Analítico" in writer_text or "Dossie Analitico" in writer_text
        print("[OK] Writer dossier branch preserved: returns markdown dossier")

        # 7. Validador Pydantic do Plano da Aplicação Real (plan_validator)
        from app.core.plan_validator import validate_and_parse_plan

        for count in [1, 2, 3, 5]:
            plan_dict = {
                "pedido_original": "Tema Investigado",
                "pedido_normalizado": "Escopo investigativo delimitado",
                "publico": "Educadores e pesquisadores",
                "formato_entrega": "Dossiê analítico com citações",
                "recorte_temporal": "Últimos 3 anos",
                "pressupostos": ["Metadados SERP tratados como pistas preliminares"],
                "ambiguidades": [],
                "eixos": canonical_eixos[:count],
                "pontos": [e["pergunta_principal"] for e in canonical_eixos[:count]],
            }
            parsed_plan, err = validate_and_parse_plan(plan_dict, expected_n=count, tema_original="Tema Investigado")
            assert err is None, f"Expected validation success for count {count}, got error: {err}"
            assert parsed_plan is not None
            assert len(parsed_plan.eixos) == count
        print("[OK] Pydantic validate_and_parse_plan passes for counts 1, 2, 3, 5")

        # 8. Verificação de Inalterabilidade de Rotas em app.main
        from app.main import app as app_under_test
        from docs.frontend.remediation.capture_app import Recorder

        routes_initial = [getattr(r, "path", str(r)) for r in app_under_test.routes]
        assert "/{full_path:path}" in routes_initial, "Missing SPA route /{full_path:path} in app.main"
        assert "/app/session" in routes_initial, "Missing session route /app/session in app.main"

        dummy_path = Path(tempfile.mktemp())
        _ = Recorder(app_under_test, output=dummy_path, provider_mode="deterministic_external_provider_fixtures")
        routes_wrapped = [getattr(r, "path", str(r)) for r in app_under_test.routes]
        assert routes_initial == routes_wrapped, "Wrapping app with Recorder must not modify app.routes"
        print(f"[OK] Route preservation: {len(routes_initial)} routes identical before and after wrapping")

        # 9. Verificação de Privacidade e Sanitização do Recorder
        from docs.frontend.remediation.capture_app import public

        test_payload = {
            "tema": "IA na Educação",
            "api_secret_key": "raw-super-secret",
            "credentials_master_key": "master-fernet-secret",
            "reasoning": "internal llm thinking chain",
            "reasoning_planejamento": "planner private reasoning",
            "envelopes": [{"prompt": "secret prompt"}],
            "auditor_envelope": {"status": "ok"},
            "sub_envelope": {"data": 123},
            "public_field": "visible",
        }
        sanitized = public(test_payload)
        assert isinstance(sanitized, dict)
        assert sanitized["api_secret_key"] == "[OMITTED]"
        assert sanitized["credentials_master_key"] == "[OMITTED]"
        assert sanitized["reasoning"] == "[OMITTED]"
        assert sanitized["reasoning_planejamento"] == "[OMITTED]"
        assert sanitized["envelopes"] == "[OMITTED]"
        assert sanitized["auditor_envelope"] == "[OMITTED]"
        assert sanitized["sub_envelope"] == "[OMITTED]"
        assert sanitized["public_field"] == "visible"
        print("[OK] Recorder privacy sanitization: all private envelopes and keys recursively omitted")

    print("=== All self-check assertions passed successfully! ===")
    return True


def build_acceptance_app():
    """Constrói e valida a aplicação FastAPI sem criar ou substituir nenhuma rota ou dependência."""
    # 1. Patch de transporte ANTES de importar app.main
    patch_mock_transport()

    # 2. Importação do app principal e do Recorder
    from app.main import app
    from docs.frontend.remediation.capture_app import Recorder, SENSITIVE_VALUES

    # Adiciona credenciais de fixture para redação caso vazem em strings
    for k in ["API_SECRET_KEY", "OPENAI_API_KEY", "JINA_API_KEY", "CREDENTIALS_MASTER_KEY", "WEBHOOK_HMAC_SECRET"]:
        v = os.environ.get(k)
        if v and v not in SENSITIVE_VALUES:
            SENSITIVE_VALUES.append(v)

    # 3. Validação estrita: a aplicação real deve fornecer sua própria rota de SPA e sessão
    # O harness NÃO cria nem substitui rotas para fazer testes passarem
    routes_before = [getattr(r, "path", str(r)) for r in app.routes]
    missing_routes = []
    if not any(r in routes_before for r in ("/{full_path:path}", "/")):
        missing_routes.append("SPA route (/{full_path:path} or /)")
    if "/app/session" not in routes_before:
        missing_routes.append("session route (/app/session)")

    if missing_routes:
        raise RuntimeError(
            f"app.main não implementa a integração de UI/sessão esperada: ausente {', '.join(missing_routes)}. "
            "A infraestrutura de teste de aceitação não adiciona rotas substitutas sintéticas."
        )

    # 4. Envoltório transparente com Recorder para fixture payloads
    output_dir = ROOT / "docs/frontend/remediation/evidence"
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads_file = output_dir / "fixture-payloads.jsonl"

    recorded_app = Recorder(
        app,
        output=payloads_file,
        provider_mode="deterministic_external_provider_fixtures",
    )

    # 5. Verificação de integridade: a lista de rotas de app permanece 100% inalterada
    routes_after = [getattr(r, "path", str(r)) for r in app.routes]
    if routes_before != routes_after:
        raise RuntimeError("A lista de rotas de app.main foi alterada após o envelopamento com Recorder.")

    return recorded_app, app, output_dir


def main():
    parser = argparse.ArgumentParser(description="Deep Research Acceptance Server on localhost:8011")
    parser.add_argument("--port", type=int, default=8011, help="Port to bind (default: 8011)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--self-check", action="store_true", help="Run offline self-check assertions and exit")
    args = parser.parse_args()

    if args.self_check:
        success = self_check()
        sys.exit(0 if success else 1)

    # Cria diretório temporário para banco SQLite isolado
    temp_dir = tempfile.TemporaryDirectory(prefix="deep-research-acceptance-")
    temp_path = Path(temp_dir.name)

    try:
        fixtures = configure_acceptance_env(temp_path)
        recorded_app, raw_app, output_dir = build_acceptance_app()

        dist_index = ROOT / "frontend/dist/index.html"
        routes_list = [getattr(r, "path", str(r)) for r in raw_app.routes]
        proof = {
            "pid": os.getpid(),
            "host": args.host,
            "port": args.port,
            "provider_mode": "deterministic_external_provider_fixtures",
            "pytest_transport_enabled": True,
            "database": f"isolated SQLite ({temp_path / 'acceptance.db'}); lifespan cleanup on stop",
            "labelled_provider_mocks": {
                "llm": "AcceptanceMockNetwork (/v1/chat/completions) with dynamic 1..5 point count and long-plan regression opt-in",
                "search": "AcceptanceMockNetwork Jina SERP + Reader",
                "webhook": "AcceptanceMockNetwork HMAC-SHA256 callback dispatcher",
            },
            "supported_fixture_points_range": "1..5 (default), count 2 for marker topic 'Energia solar: plano extenso para verificação visual'",
            "long_plan_marker_topic": LONG_PLAN_TRIGGER_TOPIC,
            "semantic_evaluator_preserved": True,
            "dependency_overrides": len(raw_app.dependency_overrides),
            "app_routes": routes_list,
            "app_source_sha256": hashlib.sha256((ROOT / "app/main.py").read_bytes()).hexdigest(),
            "frontend_index_sha256": hashlib.sha256(dist_index.read_bytes()).hexdigest() if dist_index.exists() else None,
            "recorder": "transparent ASGI receive/send observation; headers/cookies/credentials/reasoning excluded",
            "evidence_output": str(output_dir / "fixture-payloads.jsonl"),
            "session_auth": "actual app.main mechanism (no test backdoor)",
            "synthetic_routes_added": False,
        }
        (output_dir / "fixture-runtime-proof.json").write_text(json.dumps(proof, indent=2) + "\n")

        print("=" * 60)
        print(f"Acceptance Server running on http://{args.host}:{args.port}")
        print(f"Isolated DB: {temp_path / 'acceptance.db'} (cleaned up on exit)")
        print("Provider mode: deterministic_external_provider_fixtures (1..5 points)")
        print(f"Native app routes: {len(routes_list)} (no synthetic route fallback)")
        print(f"Recorder output: {output_dir / 'fixture-payloads.jsonl'}")
        print("=" * 60)

        import uvicorn
        uvicorn.run(recorded_app, host=args.host, port=args.port, log_level="warning")
    finally:
        print("\nStopping acceptance server and cleaning up isolated SQLite directory...")
        temp_dir.cleanup()
        print("Cleanup completed.")


if __name__ == "__main__":
    main()
