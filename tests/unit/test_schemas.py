"""Testes unitários para validação de esquemas Pydantic v2 (contratos de entrada e saída).

Cobre regras de validação para os endpoints /api/v1/plan, /api/v1/search,
/api/v1/audit, /api/v1/writer e /api/v1/admin/credentials.
Atende a RF-01 até RF-12.
"""

import uuid
import pytest
from pydantic import ValidationError


def test_plan_request_valid() -> None:
    """Verifica que PlanRequest aceita tema válido e id_pesquisa opcional."""
    from app.schemas.plan import PlanRequest

    req = PlanRequest(tema="Impacto da Inteligência Artificial na Educação")
    assert req.tema == "Impacto da Inteligência Artificial na Educação"
    assert req.id_pesquisa is None

    uid = str(uuid.uuid4())
    req_with_id = PlanRequest(tema="Impacto da IA", id_pesquisa=uid)
    assert req_with_id.id_pesquisa == uid


def test_plan_request_tema_length_validation() -> None:
    """Tema exige mínimo de 5 caracteres e NÃO possui limite máximo (PRD v2, I-2)."""
    from app.schemas.plan import PlanRequest

    # Tema curto (< 5 caracteres) deve falhar
    with pytest.raises(ValidationError):
        PlanRequest(tema="IA")

    # Briefing longo deve ser aceito integralmente, sem truncamento nem rejeição
    briefing = "A" * 501
    req = PlanRequest(tema=briefing)
    assert req.tema == briefing
    assert len(req.tema) == 501

    briefing_longo = "B" * 8000
    assert PlanRequest(tema=briefing_longo).tema == briefing_longo


def test_plan_request_execution_mode_contract() -> None:
    """`execution_mode` aceita apenas parallel/sequential, com default parallel (I-3)."""
    from app.schemas.plan import PlanRequest

    assert PlanRequest(tema="Tema de teste").execution_mode == "parallel"
    assert PlanRequest(tema="Tema de teste", execution_mode="sequential").execution_mode == "sequential"
    with pytest.raises(ValidationError):
        PlanRequest(tema="Tema de teste", execution_mode="turbo")


def test_plan_response_serialization() -> None:
    """Verifica estrutura de saída de PlanResponse."""
    from app.schemas.plan import PlanResponse

    uid = str(uuid.uuid4())
    data = {
        "id_pesquisa": uid,
        "tema": "Impacto da IA na Educação",
        "n_pontos": 5,
        "criado_em": "2026-10-21T18:30:00Z",
        "pontos": [
            {
                "ponto_id": str(uuid.uuid4()),
                "ponto_n": 1,
                "ponto": "Adoção de tutores inteligentes",
                "status": "pendente",
            }
        ],
    }
    resp = PlanResponse(**data)
    assert resp.id_pesquisa == uid
    assert resp.n_pontos == 5
    assert len(resp.pontos) == 1
    assert resp.pontos[0].ponto_n == 1


def test_search_request_validation() -> None:
    """Verifica validação de id_pesquisa e ponto_id em SearchRequest."""
    from app.schemas.search import SearchRequest

    uid_pesquisa = str(uuid.uuid4())
    uid_ponto = str(uuid.uuid4())

    req = SearchRequest(id_pesquisa=uid_pesquisa, ponto_id=uid_ponto)
    assert req.id_pesquisa == uid_pesquisa
    assert req.ponto_id == uid_ponto

    # Ausência de id_pesquisa deve falhar
    with pytest.raises(ValidationError):
        SearchRequest()  # type: ignore[call-arg]


def test_search_response_serialization() -> None:
    """Verifica integridade do contrato de saída de SearchResponse."""
    from app.schemas.search import SearchResponse

    uid = str(uuid.uuid4())
    data = {
        "id_pesquisa": uid,
        "total_pontos_processados": 5,
        "status_pesquisa": "coletado",
        "resumo_coletas": [
            {
                "ponto_id": str(uuid.uuid4()),
                "ponto_n": 1,
                "status": "coletado",
                "total_urls_lidas": 8,
                "total_urls_fonte": 4,
                "tamanho_conteudo_caracteres": 34820,
            }
        ],
    }
    resp = SearchResponse(**data)
    assert resp.total_pontos_processados == 5
    assert resp.resumo_coletas[0].total_urls_lidas == 8
    # CA-04.1: contrato falha de coleta é opcional e não quebra respostas legadas
    assert resp.total_falhas_coleta == 0
    assert resp.resumo_coletas[0].falha_coleta is False
    assert resp.resumo_coletas[0].diagnostico is None


def test_search_response_serializacao_falha_coleta() -> None:
    """CA-04.1/CA-04.4: status falha_coleta e diagnóstico expostos por ponto e persona."""
    from app.schemas.search import SearchResponse

    uid = str(uuid.uuid4())
    data = {
        "id_pesquisa": uid,
        "total_pontos_processados": 1,
        "status_pesquisa": "coletado",
        "total_falhas_coleta": 1,
        "resumo_coletas": [
            {
                "ponto_id": str(uuid.uuid4()),
                "ponto_n": 2,
                "status": "falha_coleta",
                "falha_coleta": True,
                "diagnostico": "JinaError 402 billing: saldo insuficiente",
                "total_urls_lidas": 0,
                "total_urls_fonte": 0,
                "tamanho_conteudo_caracteres": 180,
                "personas": [
                    {
                        "persona": "historiador",
                        "analise": "COLETA FALHOU",
                        "urls_fonte": [],
                        "falha_coleta": True,
                        "diagnostico": "JinaError 402 billing: saldo insuficiente",
                    }
                ],
                "conteudo_relevante": "### Perspectiva Historiador\n\nCOLETA FALHOU",
            }
        ],
    }
    resp = SearchResponse(**data)
    assert resp.total_falhas_coleta == 1
    resumo = resp.resumo_coletas[0]
    assert resumo.status == "falha_coleta"
    assert resumo.falha_coleta is True
    assert "402" in (resumo.diagnostico or "")
    assert resumo.personas[0].falha_coleta is True
    assert resumo.personas[0].diagnostico is not None


def test_audit_request_and_response_validation() -> None:
    """Verifica contratos de entrada e saída para etapa de auditoria."""
    from app.schemas.audit import AuditRequest, AuditResponse

    uid = str(uuid.uuid4())
    req = AuditRequest(id_pesquisa=uid)
    assert req.id_pesquisa == uid

    resp_data = {
        "id_pesquisa": uid,
        "total_pontos": 5,
        "aprovados": 4,
        "reprovados": 1,
        "status_geral": "auditado",
        "auditorias": [
            {
                "ponto_id": str(uuid.uuid4()),
                "ponto_n": 1,
                "status": "aprovado",
                "pontos_fracos": None,
                "resumo_auditoria": "Aprovado com evidências canônicas.",
            }
        ],
    }
    resp = AuditResponse(**resp_data)
    assert resp.aprovados == 4
    assert resp.reprovados == 1
    assert resp.auditorias[0].status == "aprovado"


def test_writer_request_and_response_validation() -> None:
    """Verifica contratos de entrada e saída para etapa de redação."""
    from app.schemas.writer import WriterRequest, WriterResponse

    uid = str(uuid.uuid4())
    req = WriterRequest(id_pesquisa=uid)
    assert req.id_pesquisa == uid

    resp_data = {
        "id_pesquisa": uid,
        "tema": "Impacto da IA",
        "status": "concluido",
        "total_caracteres_dossier": 18450,
        "concluido_em": "2026-10-21T18:40:00Z",
        "webhook_entrega": {
            "url": "https://callback.test/hook",
            "status": "entregue",
            "http_status_code": 200,
            "tentativas": 1,
        },
        "dossier_resumo": "# Dossiê Analítico\n...",
    }
    resp = WriterResponse(**resp_data)
    assert resp.total_caracteres_dossier == 18450
    assert resp.webhook_entrega.status == "entregue"


def test_admin_credential_create_request_validation() -> None:
    """Verifica contrato de cadastro de credenciais administrativas."""
    from app.schemas.admin import CredentialCreateRequest

    req = CredentialCreateRequest(
        chave="OPENAI_API_KEY",
        valor="sk-test-123456",
        tipo="llm",
        base_url="https://api.openai.com/v1",
        descricao="Chave principal",
    )
    assert req.chave == "OPENAI_API_KEY"
    assert req.tipo == "llm"

    # Chave ou valor ausentes devem falhar
    with pytest.raises(ValidationError):
        CredentialCreateRequest(chave="", valor="val", tipo="llm")


def test_credential_sanitized_mask_secret() -> None:
    """Verifica mascaramento em CredentialSanitizedListItem sem vazamento de segredos de webhook (REV-SEC-001)."""
    from app.schemas.admin import CredentialSanitizedListItem

    # URL legítima deve permanecer sem máscara
    url = "https://example.com/webhook"
    assert CredentialSanitizedListItem.mask_secret(url, "webhook") == url

    # Segredo de webhook NÃO deve vazar em texto claro
    secret = "super-secret-hmac-token-xyz-123456"
    masked = CredentialSanitizedListItem.mask_secret(secret, "webhook")
    assert masked != secret
    assert masked == "supe****3456"

    # Segredo curto <= 8 caracteres
    assert CredentialSanitizedListItem.mask_secret("12345678", "webhook") == "[REDACTED]"
    assert CredentialSanitizedListItem.mask_secret("", "webhook") == "[REDACTED]"


def test_plano_eixo_required_fields_omission_validation() -> None:
    """Verifica que a omissão de qualquer campo investigativo essencial falha a validação (R2-F01)."""
    from app.schemas.plan import PlanoEixo
    from app.core.plan_validator import validate_and_parse_plan

    valid_eixo_dict = {
        "pergunta_principal": "Qual o impacto da computação quântica?",
        "subperguntas": ["Como afeta criptografia?"],
        "hipoteses": ["Criptografia RSA será quebrada."],
        "consultas_iniciais": ["computacao quantica rsa"],
        "fontes_primarias_desejadas": ["Artigos NIST"],
        "riscos_de_vies": ["Hype tecnológico"],
        "evidencias_que_refutariam": ["Novos algoritmos pós-quânticos"],
        "criterio_de_conclusao": "Análise completa",
        "investigabilidade": "Fontes públicas disponíveis",
        "eixo_essencial": True,
    }

    # Deve validar com sucesso quando todos os campos estão presentes
    eixo_valido = PlanoEixo.model_validate(valid_eixo_dict)
    assert eixo_valido.pergunta_principal.startswith("Qual o impacto")

    # Lista dos campos investigativos essenciais que NUNCA podem ser omitidos ou virar [] por default silencioso
    essential_fields = [
        "hipoteses",
        "consultas_iniciais",
        "fontes_primarias_desejadas",
        "evidencias_que_refutariam",
        "subperguntas",
        "riscos_de_vies",
    ]

    for field in essential_fields:
        eixo_sem_campo = dict(valid_eixo_dict)
        del eixo_sem_campo[field]

        # 1. Pydantic direto deve levantar ValidationError
        with pytest.raises(ValidationError):
            PlanoEixo.model_validate(eixo_sem_campo)

        # 2. validate_and_parse_plan deve rejeitar e indicar motivo citando o campo
        full_plan = {
            "pedido_original": "Computação quântica",
            "pedido_normalizado": "Computação quântica",
            "publico": "Especialista",
            "formato_entrega": "Artigo técnico",
            "eixos": [eixo_sem_campo],
        }
        plano, motivo = validate_and_parse_plan(full_plan, 1, "Computação quântica")
        assert plano is None, f"Plano com eixo sem campo '{field}' não deve ser aceito"
        assert field in motivo or "inválido" in motivo or "obrigatór" in motivo

