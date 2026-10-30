"""Validador e detector de conformidade para o Plano de Investigação (DR-006).

Implementa validação estrita, determinística e direta:
- Tipos de dados estritos e campos investigativos obrigatórios (sem conversão arbitrária).
- Quantidade exata de eixos (N_PONTOS).
- Deduplicação literal local baseada em comparação canônica curta (sem vetar eixos complementares).
- Metadados contextuais úteis: público, formato de entrega e pedido normalizado.
- Fixação inviolável de pedido_original pelo input real do usuário.
- Identificação de ambiguidade bloqueante sem gastar chamadas desnecessárias.
- A avaliação semântica de intenção, público, tempo e sobreposição entre eixos
  é delegada ao avaliador semântico do modelo via Planner.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
import unicodedata

from pydantic import ValidationError
from app.schemas.plan import PlanoEixo, PlanoInvestigacao


def remove_accents(text: str) -> str:
    """Remove diacríticos e acentos para comparação canônica."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canonical_question(text: str) -> str:
    """Normaliza texto para comparação canônica curta de duplicatas literais."""
    clean = remove_accents(text.lower())
    clean = re.sub(r"[^a-z0-9\s]", " ", clean)
    return " ".join(clean.split())


def detect_literal_question_duplicates(questions: List[str]) -> Optional[Tuple[str, str, str]]:
    """Detecta repetições textuais literais entre perguntas via normalização canônica simples."""
    seen: Dict[str, str] = {}
    for q in questions:
        norm = canonical_question(q)
        if not norm:
            continue
        if norm in seen:
            return (seen[norm], q, "Perguntas com formulação textual idêntica")
        seen[norm] = q
    return None


# Compatibilidade retroativa de interface
lexical_filter_overlap = detect_literal_question_duplicates
detect_question_overlap = detect_literal_question_duplicates


def validate_and_parse_plan(
    parsed_json: Any,
    expected_n: int,
    tema_original: str,
) -> Tuple[Optional[PlanoInvestigacao], Optional[str]]:
    """Valida estritamente a resposta do LLM contra o contrato DR-006.

    Exige campos obrigatórios com tipos estritos, sem conversão com str(),
    sem fallbacks fictícios para o tema e sem aceitação de esquemas legados parciais.
    Retorna (PlanoInvestigacao, None) em conformidade, ou (None, motivo_erro).
    """
    if not isinstance(parsed_json, dict):
        return (
            None,
            f"Formato de resposta inválido do LLM: esperava um objeto JSON dict, "
            f"mas recebeu {type(parsed_json).__name__}.",
        )

    # 1. Verificação de ambiguidade bloqueante (DR-006)
    pergunta_esclarecimento = parsed_json.get("pergunta_de_esclarecimento")
    if pergunta_esclarecimento and isinstance(pergunta_esclarecimento, str) and pergunta_esclarecimento.strip():
        return (
            None,
            f"Ambiguidade bloqueante identificada: o tema requer esclarecimento prévio "
            f"('{pergunta_esclarecimento.strip()}') antes de gerar o plano investigativo.",
        )

    # 2. Exigência estrita de esquema rico completo ('eixos')
    if "eixos" not in parsed_json:
        if "pontos" in parsed_json:
            return (
                None,
                "Contrato inválido: o modelo deve fornecer o esquema rico completo com 'eixos' "
                "e seus campos investigativos, não apenas uma lista legada 'pontos'.",
            )
        return (
            None,
            "Formato de resposta inválido do LLM: o JSON deve conter a chave 'eixos' "
            "com a lista estruturada de eixos investigativos.",
        )

    eixos_raw = parsed_json.get("eixos")
    if not isinstance(eixos_raw, list):
        return None, "O campo 'eixos' deve ser uma lista de objetos investigativos."

    if len(eixos_raw) != expected_n:
        return (
            None,
            f"O modelo gerou {len(eixos_raw)} eixos, mas eram esperados exatamente {expected_n}.",
        )

    eixos_objs: List[PlanoEixo] = []
    questions: List[str] = []

    for idx, item in enumerate(eixos_raw, start=1):
        if not isinstance(item, dict):
            return (
                None,
                f"Eixo {idx} possui tipo inválido ({type(item).__name__}). Deve ser um objeto com contrato estrito.",
            )

        try:
            eixo_obj = PlanoEixo.model_validate(item)
        except ValidationError as ve:
            errs = [f"{e['loc'][-1] if e['loc'] else 'campo'}: {e['msg']}" for e in ve.errors()]
            return None, f"Eixo {idx} possui violação de contrato: {'; '.join(errs)}"

        questions.append(eixo_obj.pergunta_principal)
        eixos_objs.append(eixo_obj)

    # 3. Deduplicação literal local (para N > 1)
    if expected_n > 1:
        dup_info = detect_literal_question_duplicates(questions)
        if dup_info:
            q1, q2, motivo = dup_info
            return (
                None,
                f"Detecção de duplicidade literal no plano gerado: '{q1}' vs '{q2}'. Motivo: {motivo}.",
            )

    # 4. Tipagem estrita dos metadados contextuais do plano
    raw_publico = parsed_json.get("publico")
    if not isinstance(raw_publico, str):
        return None, f"O campo 'publico' deve ser do tipo string, recebeu {type(raw_publico).__name__}."
    publico = raw_publico.strip()
    if len(publico) < 2:
        return None, "O campo 'publico' deve conter ao menos 2 caracteres."

    raw_formato = parsed_json.get("formato_entrega")
    if not isinstance(raw_formato, str):
        return None, f"O campo 'formato_entrega' deve ser do tipo string, recebeu {type(raw_formato).__name__}."
    formato = raw_formato.strip()
    if len(formato) < 3:
        return None, "O campo 'formato_entrega' deve conter ao menos 3 caracteres."

    raw_pedido_norm = parsed_json.get("pedido_normalizado")
    if raw_pedido_norm is None:
        return None, "O campo 'pedido_normalizado' é obrigatório e deve ser gerado pelo modelo sem fallback."
    if not isinstance(raw_pedido_norm, str):
        return None, f"O campo 'pedido_normalizado' deve ser do tipo string, recebeu {type(raw_pedido_norm).__name__}."
    pedido_norm = raw_pedido_norm.strip()
    if len(pedido_norm) < 3:
        return None, "O campo 'pedido_normalizado' deve ter pelo menos 3 caracteres."

    recorte_temp = parsed_json.get("recorte_temporal")
    if recorte_temp is not None and not isinstance(recorte_temp, str):
        return None, f"O campo 'recorte_temporal' deve ser string ou null, recebeu {type(recorte_temp).__name__}."

    # 5. Construção do plano com pedido_original fixado inviolavelmente pelo input real
    try:
        plano = PlanoInvestigacao(
            pedido_original=tema_original.strip(),  # Inviolável: fixado pela aplicação
            pedido_normalizado=pedido_norm,
            publico=publico,
            formato_entrega=formato,
            recorte_temporal=recorte_temp,
            pressupostos=parsed_json.get("pressupostos") if "pressupostos" in parsed_json else [],
            ambiguidades=parsed_json.get("ambiguidades") if "ambiguidades" in parsed_json else [],
            pergunta_de_esclarecimento=pergunta_esclarecimento,
            eixos=eixos_objs,
        )
    except ValidationError as ve:
        errs = [f"{e['loc'][-1] if e['loc'] else 'campo'}: {e['msg']}" for e in ve.errors()]
        return None, f"Violação de contrato nos metadados do plano: {'; '.join(errs)}"

    return plano, None
