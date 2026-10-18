"""Domínio puro do Módulo de Auditoria Factual (T041, T044, T048; RN-302/RN-303/RN-305).

Sem I/O e sem dependência de banco: cálculo de score sobre os 12 critérios
canônicos (`q1`..`q12`), regra de aprovação (score >= 10 e nenhuma
contradição não reconciliada), checagem determinística de citações e
máquina de estados do ponto:

- Aprovado                   -> ``AUDIT_APPROVED``
- Reprovado (attempt < 4)    -> ``SCRAPER_RETRY`` (exige missing_research concreto)
- Reprovado na 4ª tentativa  -> ``AUDIT_CAVEAT`` (limitações registradas; a
  pesquisa nunca fica travada em estado BLOCKED, RN-305)

Sanitização de segredos em dicionários de auditoria via
``apply_output_guardrail`` (app.services.llm).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.services.llm import apply_output_guardrail

# ---------------------------------------------------------------- estados ---

STATE_APPROVED = "AUDIT_APPROVED"
STATE_RETRY = "SCRAPER_RETRY"
STATE_CAVEAT = "AUDIT_CAVEAT"
STATE_INCONCLUSIVE = "AUDIT_INCONCLUSIVE"

#: Estados conclusivos do ciclo de auditoria (RN-305/RN-306).
CONCLUSIVE_STATES: frozenset[str] = frozenset({STATE_APPROVED, STATE_CAVEAT})

#: Teto rígido de execuções pesquisa/auditoria por ponto (1 inicial + 3 retries).
MAX_AUDIT_ATTEMPTS = 4

#: Score mínimo de aprovação: >= 10 das 12 perguntas (RN-302).
MIN_APPROVAL_SCORE = 10

# ---------------------------------------------- aliases públicos (T041) ------
# Nomes estáveis consumidos por app.audit.__init__, schemas e testes.
AUDIT_APPROVED = STATE_APPROVED
SCRAPER_RETRY = STATE_RETRY
AUDIT_CAVEAT = STATE_CAVEAT
APPROVAL_MIN_SCORE = MIN_APPROVAL_SCORE
MAX_ATTEMPTS = MAX_AUDIT_ATTEMPTS
REDACTED = "[REDACTED]"

# ---------------------------------------------------- 12 critérios canônicos -

#: 12 critérios canônicos, redigidos no sentido positivo: ``true`` significa
#: critério ATENDIDO (seção 3 de requirements.md da Feature 003).
AUDIT_CRITERIA: dict[str, str] = {
    "q1": "A pergunta central e os objetivos do ponto foram respondidos satisfatoriamente?",
    "q2": "Os aspectos críticos e variáveis chave do problema foram cobertos?",
    "q3": "As principais alegações estão ancoradas em fontes rastreáveis e verificáveis?",
    "q4": "As fontes consultadas possuem autoridade técnica, institucional ou acadêmica?",
    "q5": "As citações e excertos realmente sustentam as conclusões tiradas pelas personas?",
    "q6": "Não há dependência excessiva ou viés em uma única fonte ou domínio?",
    "q7": "Os dados e referências são cronologicamente adequados ao tema investigado?",
    "q8": "Contradições entre diferentes fontes ou personas foram identificadas e esclarecidas?",
    "q9": "Fatos empíricos estão claramente distinguidos de hipóteses, projeções e opiniões?",
    "q10": "Não há saltos argumentativos, generalizações indevidas ou alucinações?",
    "q11": "Não restam lacunas críticas de informação que invalidem o ponto?",
    "q12": "O material acumulado fornece base sólida e suficiente para o Agente Redator?",
}

CRITERIA_KEYS: tuple[str, ...] = tuple(AUDIT_CRITERIA)

#: Alias estável (ordem q1..q12) exportado por ``app.audit``/consumido por testes.
CRITERION_IDS: tuple[str, ...] = CRITERIA_KEYS


def evaluate_checklist(checklist: Mapping[str, Any]) -> int:
    """Score S em [0, 12]: nº de critérios canônicos marcados como verdadeiros.

    Chaves fora de ``q1``..``q12`` são ignoradas; critérios ausentes contam
    como falsos. O resultado é fixado (clamp) no intervalo [0, 12].
    """
    score = sum(1 for key in CRITERIA_KEYS if bool(checklist.get(key)))
    return max(0, min(len(CRITERIA_KEYS), score))


def verdict_approves(
    score: int,
    contradictions: Iterable[str] | None,
    citation_issues: Iterable[str] | None = None,
) -> bool:
    """RN-302: aprovado se e somente se score >= 10 e contradições vazias.

    ``citation_issues`` carrega falsificações/citações não suportadas
    detectadas na checagem determinística; qualquer item nega aprovação.
    """
    if score < MIN_APPROVAL_SCORE:
        return False
    if [c for c in (contradictions or []) if str(c or "").strip()]:
        return False
    if [c for c in (citation_issues or []) if str(c or "").strip()]:
        return False
    return True


def next_audit_state(
    approved: bool, attempt: int, max_attempts: int = MAX_AUDIT_ATTEMPTS
) -> str:
    """Máquina de estados do ponto (RN-302/RN-303/RN-305).

    ``attempt`` é o número ordinal (1-based) do ciclo de auditoria que
    acaba de rodar (1 = execução inicial). Nunca devolve um estado
    BLOCKED fatal: o teto de tentativas converge para ``AUDIT_CAVEAT``.
    """
    if approved:
        return STATE_APPROVED
    if attempt >= max_attempts:
        return STATE_CAVEAT
    return STATE_RETRY


def ensure_concrete_missing_research(
    missing_research: Iterable[str] | None,
    findings: Iterable[str] | None,
    point_title: str,
) -> list[str]:
    """RN-303: instrução de re-pesquisa concreta e direcionada.

    Descarta itens vazios/curtos (proibidas diretrizes vagas tipo
    "pesquise mais"); se o auditor não tiver formulado nada útil,
    sintetiza instruções a partir dos findings.
    """
    concrete: list[str] = []
    for item in missing_research or []:
        text = str(item or "").strip()
        if len(text) >= 12:
            concrete.append(text)
    if concrete:
        return concrete

    synthesized: list[str] = []
    for finding in findings or []:
        text = str(finding or "").strip()
        if len(text) >= 12:
            synthesized.append(f'Investigar e corroborar com fonte específica: "{text}"')
    if not synthesized:
        synthesized.append(
            f'Reinvestigar o ponto "{point_title}" buscando fontes inéditas '
            "que cubram a lacuna detectada nos 12 critérios canônicos."
        )
    return synthesized


def sanitize_audit_dict(data: Any, sensitive_values: list[str] | None = None) -> Any:
    """Sanitização estrita de segredos em dicionários de auditoria (T044).

    Recursivamente aplica ``apply_output_guardrail`` a strings; blocos que
    carregariam segredo/config interna viram ``[REDACTED]`` em vez de
    propagar exceção. Bools/ints/None atravessam intactos.
    """
    if isinstance(data, str):
        try:
            return apply_output_guardrail(data, sensitive_values)
        except Exception:
            return "[REDACTED]"
    if isinstance(data, list):
        return [sanitize_audit_dict(item, sensitive_values) for item in data]
    if isinstance(data, dict):
        return {str(k): sanitize_audit_dict(v, sensitive_values) for k, v in data.items()}
    return data


def deterministic_citation_check(step_results: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Checagem determinística de citações sobre os resultados das personas.

    Com a granularidade disponível neste estágio (texto analítico por
    persona + ``used_urls``/``read_urls``), verifica:
    - presença das 4 personas (completeza do consenso investigativo);
    - rastreabilidade: cada resultado bem-sucedido aponta ao menos uma URL
      efetivamente lida/utilizada (``used_urls`` ∪ ``read_urls``).

    Resultados `FAILED` (ou sem URL alguma) não são suportados e tornam a
    checagem reprovatória para aprovação até que a lacuna seja sanada.
    """
    rows = list(step_results)
    supported: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    personas: Counter[str] = Counter()
    for row in rows:
        worker = row.get("worker")
        status = str(row.get("status") or "")
        used = [u for u in (row.get("used_urls") or []) if isinstance(u, str) and u]
        read = [u for u in (row.get("read_urls") or []) if isinstance(u, str) and u]
        urls = set(used) | set(read)
        if status == "FAILED" or not urls:
            unsupported.append({"worker": worker, "status": status, "traceable": False})
            continue
        if worker:
            personas[str(worker)] += 1
        supported.append({"worker": worker, "traceable": True, "urls": sorted(urls)[:8]})
    complete = all(p in personas for p in ("historian", "skeptic", "pragmatist", "futurist"))
    citation_issues = [
        f'Persona "{item.get("worker")}" sem evidência rastreável (URL) do resultado'
        for item in unsupported
        if item.get("worker")
    ]
    return {
        "supported": len(supported),
        "unsupported": unsupported,
        "personas_present": sorted(personas),
        "complete_personas": complete,
        "citation_issues": citation_issues,
    }


# ------------------------------------------------ -------- T041/T044 helpers --


def _as_bool(value: Any) -> bool:
    """Coerção tolerante de booleanos emitidos pelo LLM."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "sim", "s"}
    return bool(value)


def normalize_checklist(checklist: Mapping[str, Any] | None) -> dict[str, bool]:
    """Checklist canônico ``q1``..``q12`` (chaves ausentes contam como falsas)."""
    source = checklist or {}
    return {key: _as_bool(source.get(key)) for key in CRITERIA_KEYS}


def calculate_score(checklist: Mapping[str, Any] | None) -> int:
    """Score S em [0, 12] sobre o checklist canônico normalizado."""
    normalized = normalize_checklist(checklist)
    score = sum(1 for value in normalized.values() if value)
    return max(0, min(len(CRITERIA_KEYS), score))


def default_missing_research(
    point_title: str,
    checklist: Mapping[str, Any] | None,
    findings: Iterable[str] | None = None,
) -> list[str]:
    """Instruções concretas de re-pesquisa quando o auditor não as formulou (RN-303).

    Cita cada critério reprovado e exige citação verbatim + URL; nunca
    devolve diretrizes vagas.
    """
    normalized = normalize_checklist(checklist)
    instructions: list[str] = []
    for key, satisfied in normalized.items():
        if satisfied:
            continue
        criterion = AUDIT_CRITERIA.get(key, "critério canônico")
        instructions.append(
            f"[{key}] Repesquisar o ponto \"{point_title}\" até atender o critério "
            f"\"{criterion}\" registrando citação verbatim e URL de origem."
        )
    for finding in findings or []:
        text = str(finding or "").strip()
        if len(text) >= 12:
            instructions.append(
                f'Investigar e corroborar com citação verbatim e URL: "{text}"'
            )
    if not instructions:
        instructions.append(
            f'Reinvestigar o ponto "{point_title}" buscando fontes inéditas '
            "que cubram as lacunas dos 12 critérios canônicos, com citação "
            "verbatim e URL de origem."
        )
    return instructions


@dataclass
class AuditVerdict:
    """Veredito estruturado do Agente Auditor para um ponto (T041/T044).

    ``status`` é o estado DB do ponto: ``AUDIT_APPROVED``, ``SCRAPER_RETRY``,
    ``AUDIT_CAVEAT`` ou ``AUDIT_INCONCLUSIVE`` (falha de infraestrutura).
    """

    approved: bool
    score: int
    checklist: dict[str, bool] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    missing_research: list[str] = field(default_factory=list)
    outline: list[str] = field(default_factory=list)
    status: str = STATE_RETRY
    is_caveat: bool = False
    #: Ciclo de auditoria 1-based executado (None quando inconclusivo, RN-304).
    attempt: int | None = None


def evaluate_audit_verdict(
    checklist: Mapping[str, Any] | None,
    findings: Iterable[str] | None = None,
    contradictions: Iterable[str] | None = None,
    uncertainties: Iterable[str] | None = None,
    missing_research: Iterable[str] | None = None,
    outline: Iterable[str] | None = None,
    attempt_count: int = 1,
) -> AuditVerdict:
    """Máquina de estados RN-302/RN-303/RN-305 sobre a saída do auditor LLM.

    ``attempt_count`` é o ciclo 1-based executado. Aprovado se e somente se
    score >= APPROVAL_MIN_SCORE e nenhuma contradição concreta; reprovado
    antes do teto -> ``SCRAPER_RETRY`` (missing_research concreto garantido);
    reprovado no teto -> ``AUDIT_CAVEAT`` (is_caveat=True).
    """
    normalized = normalize_checklist(checklist)
    score = calculate_score(normalized)
    findings_list = [str(f or "").strip() for f in (findings or []) if str(f or "").strip()]
    contradictions_list = [
        str(c or "").strip() for c in (contradictions or []) if str(c or "").strip()
    ]
    uncertainties_list = [
        str(u or "").strip() for u in (uncertainties or []) if str(u or "").strip()
    ]
    outline_list = [str(o or "").strip() for o in (outline or []) if str(o or "").strip()]
    missing_list = [
        str(m or "").strip() for m in (missing_research or []) if str(m or "").strip()
    ]

    approved = verdict_approves(score, contradictions_list)
    try:
        ordinal = int(attempt_count)
    except (TypeError, ValueError):
        ordinal = 1
    ordinal = max(1, ordinal)
    state = next_audit_state(approved, ordinal, MAX_AUDIT_ATTEMPTS)

    if not approved:
        missing_list = ensure_concrete_missing_research(
            missing_list, findings_list, "ponto sob auditoria"
        )

    return AuditVerdict(
        approved=approved,
        score=score,
        checklist=normalized,
        findings=findings_list,
        contradictions=contradictions_list,
        uncertainties=uncertainties_list,
        missing_research=missing_list,
        outline=outline_list,
        status=state,
        is_caveat=state == STATE_CAVEAT,
    )
