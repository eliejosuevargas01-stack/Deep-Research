"""Política temporal canônica do Deep Research.

O pipeline não pode tratar o limite de conhecimento do modelo como limite dos
fatos. Este módulo centraliza:

- a data de referência da pesquisa (hoje, no fuso configurado);
- a decisão entre recorte histórico explícito e busca pelo estado mais recente;
- a geração de consultas ancoradas no ano corrente;
- a leitura e a ordenação de datas de publicação devolvidas pela SERP/corpo;
- o bloco de instruções temporais injetado em planner, search, auditor e writer.

A data é calculada em tempo de execução a partir do relógio do servidor no
fuso configurado. Para testes/reprodutibilidade pontual, ``RESEARCH_REFERENCE_DATE``
pode fixar uma data em formato ISO (YYYY-MM-DD); sem a variável, vale o ``now``.
O fuso default é ``America/Sao_Paulo`` (configurável por
``RESEARCH_REFERENCE_TIMEZONE``).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

DEFAULT_REFERENCE_TIMEZONE = "America/Sao_Paulo"
DEFAULT_RECENCY_MODE = "auto"
RECENCY_MODES = ("auto", "recente", "24h", "7d", "30d", "12m", "historico")

_WINDOW_DAYS = {
    "recente": 365,
    "24h": 1,
    "7d": 7,
    "30d": 30,
    "12m": 365,
}

_MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

_MONTHS_EN = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_RECENT_TERMS_RE = re.compile(
    r"\b(atuais?|hoje|agora|recentes?|ultim[oa]s?|últim[oa]s?|neste ano|este ano|"
    r"neste momento|atualidade|tempo real|breaking|latest)\b",
    re.IGNORECASE,
)

_HISTORICAL_TERMS_RE = re.compile(
    r"\b(hist[oó]ria|hist[oó]ric[oa]s?|linha do tempo|retrospectiva|s[eé]culo|"
    r"d[eé]cada|era uma vez|no passado|antigamente)\b",
    re.IGNORECASE,
)

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")

_FULL_DATE_PATTERNS = (
    re.compile(r"\b(19\d{2}|20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b"),
    re.compile(r"\b(0?[1-9]|[12]\d|3[01])[-/](0?[1-9]|1[0-2])[-/](19\d{2}|20\d{2})\b"),
)

_MONTH_NAMES_RE = "|".join(
    sorted(
        {re.escape(k) for k in list(_MONTHS_PT) + list(_MONTHS_EN)},
        key=len,
        reverse=True,
    )
)

_TEXTUAL_DATE_RE = re.compile(
    r"\b(0?[1-9]|[12]\d|3[01])\s+(?:de\s+)?(" + _MONTH_NAMES_RE + r")\.?\s+(?:de\s+)?(19\d{2}|20\d{2})\b",
    re.IGNORECASE,
)
_MONTH_YEAR_RE = re.compile(
    r"\b(" + _MONTH_NAMES_RE + r")\.?\s+(?:de\s+)?(19\d{2}|20\d{2})\b",
    re.IGNORECASE,
)
_TEXTUAL_DATE_EN_RE = re.compile(
    r"\b(" + _MONTH_NAMES_RE + r")\.?\s+(0?[1-9]|[12]\d|3[01])\s*,?\s+(19\d{2}|20\d{2})\b",
    re.IGNORECASE,
)

_URL_DATE_RE = re.compile(
    r"/(?:19\d{2}|20\d{2})[-/](?:0?[1-9]|1[0-2])(?:[-/](?:0?[1-9]|[12]\d|3[01]))?/?"
)


@dataclass(frozen=True)
class RecencyPolicy:
    """Decisão temporal efetiva para uma pesquisa.

    ``force_current_year`` é True quando o pedido não fixou um recorte
    histórico e o pipeline deve buscar explicitamente o estado mais recente.
    """

    mode: str
    reference: date
    window_days: Optional[int]
    force_current_year: bool
    reason: str

    @property
    def year(self) -> int:
        return self.reference.year

    @property
    def iso(self) -> str:
        return self.reference.isoformat()

    @property
    def br(self) -> str:
        return format_date_br(self.reference)

    @property
    def is_historical(self) -> bool:
        return not self.force_current_year

    @property
    def window_label(self) -> str:
        if self.window_days is None:
            return "sem janela de recência imposta"
        if self.window_days <= 1:
            return "últimas 24 horas"
        if self.window_days <= 7:
            return "últimos 7 dias"
        if self.window_days <= 30:
            return "últimos 30 dias"
        if self.window_days <= 365:
            return "últimos 12 meses"
        return f"últimos {self.window_days} dias"


def _reference_timezone() -> timezone | ZoneInfo:
    name = (os.environ.get("RESEARCH_REFERENCE_TIMEZONE") or DEFAULT_REFERENCE_TIMEZONE).strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return datetime.now().astimezone().tzinfo or timezone.utc


def reference_now() -> datetime:
    """Retorna o instante de referência com fuso, respeitando override de testes."""
    override = (os.environ.get("RESEARCH_REFERENCE_DATE") or "").strip()
    tz = _reference_timezone()
    if override:
        parsed = parse_any_date(override)
        if parsed is not None:
            return datetime(parsed.year, parsed.month, parsed.day, 12, 0, tzinfo=tz)
    return datetime.now(tz)


def current_reference_date() -> date:
    """Data canônica da pesquisa (hoje no fuso configurado ou override explícito)."""
    return reference_now().date()


def format_date_br(value: date) -> str:
    return f"{value.day:02d}/{value.month:02d}/{value.year:04d}"


def normalize_recency_mode(value: Optional[str]) -> str:
    mode = (value or DEFAULT_RECENCY_MODE).strip().lower()
    aliases = {
        "atual": "recente",
        "latest": "recente",
        "recent": "recente",
        "historico": "historico",
        "histórico": "historico",
        "history": "historico",
        "1d": "24h",
        "dia": "24h",
        "7dias": "7d",
        "30dias": "30d",
        "1ano": "12m",
        "12meses": "12m",
    }
    mode = aliases.get(mode, mode)
    return mode if mode in RECENCY_MODES else DEFAULT_RECENCY_MODE


def has_explicit_past_scope(text: str, reference: Optional[date] = None) -> bool:
    """Detecta um recorte histórico explícito que não deve ser sobrescrito.

    Um ano isolado anterior ao ano corrente caracteriza recorte histórico.
    Anos do ano corrente, janelas relativas ("últimos 5 anos") e pedidos com
    termos de atualidade NÃO caracterizam recorte passado.
    """
    ref = reference or current_reference_date()
    raw = (text or "").strip()
    if not raw:
        return False

    years = [int(y) for y in _YEAR_RE.findall(raw)]
    if years:
        if max(years) >= ref.year:
            return False
        if _RECENT_TERMS_RE.search(raw):
            return False
        return True

    if _RECENT_TERMS_RE.search(raw):
        return False

    if _HISTORICAL_TERMS_RE.search(raw):
        return True

    return False


def resolve_recency_policy(
    user_request: str,
    requested_mode: Optional[str] = None,
    reference: Optional[date] = None,
) -> RecencyPolicy:
    """Resolve a política efetiva de recência a partir do pedido e de um override."""
    ref = reference or current_reference_date()
    requested = normalize_recency_mode(requested_mode)

    if requested == "historico":
        return RecencyPolicy(
            mode="historico",
            reference=ref,
            window_days=None,
            force_current_year=False,
            reason="recorte histórico solicitado explicitamente",
        )

    if requested in _WINDOW_DAYS:
        return RecencyPolicy(
            mode=requested,
            reference=ref,
            window_days=_WINDOW_DAYS[requested],
            force_current_year=True,
            reason=f"modo de recência explícito: {requested}",
        )

    # auto: respeita recorte histórico explícito; caso contrário busca o estado atual.
    if has_explicit_past_scope(user_request, ref):
        return RecencyPolicy(
            mode="historico",
            reference=ref,
            window_days=None,
            force_current_year=False,
            reason="pedido contém recorte histórico explícito; nenhum ano atual será imposto",
        )

    return RecencyPolicy(
        mode="recente",
        reference=ref,
        window_days=365,
        force_current_year=True,
        reason="pedido sem recorte histórico explícito; cobertura deve alcançar a data de referência",
    )


def query_has_time_anchor(query: str) -> bool:
    """Indica se a consulta já contém âncora temporal suficiente."""
    q = (query or "").strip()
    if not q:
        return False
    if _YEAR_RE.search(q):
        return True
    if _TEXTUAL_DATE_RE.search(q) or _MONTH_YEAR_RE.search(q):
        return True
    if _RECENT_TERMS_RE.search(q):
        return True
    if re.search(r"\b(hoje|ontem|amanh[ãa]|esta semana|neste m[eê]s|agora)\b", q, re.IGNORECASE):
        return True
    return False


def build_recency_aware_query(query: str, policy: RecencyPolicy) -> str:
    """Acrescenta o ano corrente a consultas sem âncora temporal.

    A consulta original é preservada quando já contém ano, data, operador de
    site ou termo de atualidade. A transformação é deliberadamente simples:
    o objetivo é garantir que ao menos uma linha de busca alcance o presente,
    sem reescrever a intenção semântica da persona.
    """
    q = (query or "").strip()
    if not q or not policy.force_current_year or query_has_time_anchor(q):
        return q
    if "site:" in q.lower() or q.startswith("http://") or q.startswith("https://"):
        return q
    return f"{q} {policy.year}"[:500].strip()


def build_discovery_queries(user_request: str, policy: RecencyPolicy) -> List[str]:
    """Queries de descoberta do planejador: intenção original + recorte atual.

    Em recorte histórico, apenas a consulta original é executada. Em modo
    recente, a segunda consulta ancora o ano corrente para que a SERP não
    devolva somente material antigo por inércia do índice.
    """
    original = (user_request or "").strip()
    if not original:
        return []
    if not policy.force_current_year:
        return [original]
    anchored = build_recency_aware_query(original, policy)
    if anchored and anchored != original:
        return [original, anchored]
    return [original]


def parse_any_date(value: Any, reference: Optional[date] = None) -> Optional[date]:
    """Interpreta datas comuns em metadados web, URLs, SERP e corpo Markdown."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).date()
        except (ValueError, OSError, OverflowError):
            return None

    raw = str(value).strip()
    if not raw:
        return None
    # Remove horas e timezone de ISO/RFC quando presentes.
    iso_candidate = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate).date()
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(raw)
        if parsed:
            return parsed.date()
    except (TypeError, ValueError, IndexError, OverflowError):
        pass

    for pattern in _FULL_DATE_PATTERNS:
        m = pattern.search(raw)
        if m:
            a, b, c = m.groups()
            if len(a) == 4:
                y, mo, d = int(a), int(b), int(c)
            else:
                d, mo, y = int(a), int(b), int(c)
            try:
                return date(y, mo, d)
            except ValueError:
                return None

    m = _TEXTUAL_DATE_RE.search(raw)
    if m:
        d, month_name, y = m.groups()
        month = _MONTHS_PT.get(month_name.lower()) or _MONTHS_EN.get(month_name.lower())
        if month:
            try:
                return date(int(y), month, int(d))
            except ValueError:
                return None

    m = _TEXTUAL_DATE_EN_RE.search(raw)
    if m:
        month_name, d, y = m.groups()
        month = _MONTHS_PT.get(month_name.lower()) or _MONTHS_EN.get(month_name.lower())
        if month:
            try:
                return date(int(y), month, int(d))
            except ValueError:
                return None

    m = _MONTH_YEAR_RE.search(raw)
    if m:
        month_name, y = m.groups()
        month = _MONTHS_PT.get(month_name.lower()) or _MONTHS_EN.get(month_name.lower())
        if month:
            try:
                return date(int(y), month, 1)
            except ValueError:
                return None

    m = _YEAR_RE.search(raw)
    if m:
        try:
            return date(int(m.group(1)), 1, 1)
        except ValueError:
            return None
    return None


def extract_dates(text: str, max_chars: Optional[int] = None) -> List[date]:
    """Extrai datas de um texto com prioridade para datas completas."""
    if not text:
        return []
    raw = text[:max_chars] if max_chars else text
    found: List[date] = []
    covered: List[Tuple[int, int]] = []

    for pattern in _FULL_DATE_PATTERNS:
        for m in pattern.finditer(raw):
            if any(start <= m.start() < end or start < m.end() <= end for start, end in covered):
                continue
            a, b, c = m.groups()
            if len(a) == 4:
                y, mo, d = int(a), int(b), int(c)
            else:
                d, mo, y = int(a), int(b), int(c)
            try:
                found.append(date(y, mo, d))
                covered.append((m.start(), m.end()))
            except ValueError:
                continue

    for m in _TEXTUAL_DATE_RE.finditer(raw):
        if any(start <= m.start() < end or start < m.end() <= end for start, end in covered):
            continue
        d, month_name, y = m.groups()
        month = _MONTHS_PT.get(month_name.lower()) or _MONTHS_EN.get(month_name.lower())
        if month:
            try:
                found.append(date(int(y), month, int(d)))
                covered.append((m.start(), m.end()))
            except ValueError:
                continue

    for m in _TEXTUAL_DATE_EN_RE.finditer(raw):
        if any(start <= m.start() < end or start < m.end() <= end for start, end in covered):
            continue
        month_name, d, y = m.groups()
        month = _MONTHS_PT.get(month_name.lower()) or _MONTHS_EN.get(month_name.lower())
        if month:
            try:
                found.append(date(int(y), month, int(d)))
                covered.append((m.start(), m.end()))
            except ValueError:
                continue

    for m in _MONTH_YEAR_RE.finditer(raw):
        if any(start <= m.start() < end or start < m.end() <= end for start, end in covered):
            continue
        month_name, y = m.groups()
        month = _MONTHS_PT.get(month_name.lower()) or _MONTHS_EN.get(month_name.lower())
        if month:
            try:
                found.append(date(int(y), month, 1))
                covered.append((m.start(), m.end()))
            except ValueError:
                continue

    for m in _YEAR_RE.finditer(raw):
        if any(start <= m.start() < end or start < m.end() <= end for start, end in covered):
            continue
        try:
            found.append(date(int(m.group(1)), 1, 1))
            covered.append((m.start(), m.end()))
        except ValueError:
            continue

    # Datas repetidas não acrescentam informação; ordem cronológica facilita inspeção.
    return sorted(set(found))


def latest_documented_date(
    texts: Iterable[str],
    reference: Optional[date] = None,
    max_chars_per_text: int = 6000,
) -> Optional[date]:
    """Maior data documentada no corpus, ignorando datas futuras além da referência."""
    ref = reference or current_reference_date()
    limit = ref + timedelta(days=1)
    latest: Optional[date] = None
    for text in texts:
        for d in extract_dates(str(text or "")[:max_chars_per_text]):
            if d <= limit and (latest is None or d > latest):
                latest = d
    return latest


def source_date_from_item(item: dict, body: Optional[str] = None, reference: Optional[date] = None) -> Tuple[Optional[date], Optional[str]]:
    """Descobre a data de publicação de um resultado SERP/leitura.

    Prioridade: timestamp/metadados da SERP → data na URL → data no corpo.
    A origem é devolvida para que a auditoria saiba distinguir metadado de
    data inferida por texto.
    """
    ref = reference or current_reference_date()
    if isinstance(item, dict):
        for key in ("timestamp", "published_time", "published", "date", "last_updated", "updated"):
            parsed = parse_any_date(item.get(key), ref)
            if parsed is not None:
                return parsed, f"serp:{key}"
        url = str(item.get("url") or "")
        parsed = parse_any_date(url, ref) if _URL_DATE_RE.search(url) else None
        if parsed is not None:
            return parsed, "url"
    if body:
        parsed = latest_documented_date([body], ref, max_chars_per_text=6000)
        if parsed is not None:
            return parsed, "body"
    return None, None


def rank_serp_items_by_freshness(items: List[dict], policy: RecencyPolicy) -> List[dict]:
    """Estabiliza os resultados recentes no topo quando a política exige atualidade.

    Resultados sem data não são descartados: permanecem na ordem original e
    entram depois dos resultados datados recentes. Em recorte histórico a
    ordem original da SERP é preservada integralmente.
    """
    if not policy.force_current_year or not items:
        return list(items)

    ref_limit = policy.reference + timedelta(days=1)
    window = policy.window_days or 365

    def _key(pair: Tuple[int, dict]) -> Tuple[int, int, int]:
        idx, item = pair
        dt, _origin = source_date_from_item(item, reference=policy.reference)
        if dt is not None and dt <= ref_limit and (policy.reference - dt).days <= window:
            return (0, -dt.toordinal(), idx)
        if dt is not None and dt <= ref_limit:
            return (1, -dt.toordinal(), idx)
        return (2, 0, idx)

    indexed = list(enumerate(items))
    return [item for _idx, item in sorted(indexed, key=_key)]


def build_recency_block(policy: RecencyPolicy, task: str = "search") -> str:
    """Bloco de instruções temporais compartilhado pelos estágios do pipeline."""
    lines = [
        f"DATA DE REFERÊNCIA: {policy.br} (ano corrente: {policy.year}).",
        "A base de conhecimento do modelo pode ter sido treinada antes dessa data; NUNCA trate o corte do treinamento como limite dos fatos.",
        "Toda afirmação sobre o presente deve ser verificada contra fontes web e datada.",
        "Distinga a data do evento da data de publicação/atualização da fonte.",
        "Datas iguais ou anteriores à DATA DE REFERÊNCIA são presente/passado verificável, NÃO são 'futuro'. "
        "Só classifique um evento como futuro se a data exceder a referência; se a data for duvidosa, diga "
        "'data não confirmada', sem converter isso em 'evento futuro'.",
        "Ausência de menção no corpus consultado NÃO prova que o fato não ocorreu; registre como lacuna de cobertura.",
    ]

    if policy.force_current_year:
        lines.extend(
            [
                "RECORTE PADRÃO: como o pedido não fixou um recorte histórico, a cobertura deve alcançar a data de referência e incluir os desdobramentos mais recentes.",
                f"PRIORIDADE DE FONTES: {policy.window_label}, com pelo menos uma busca ancorada no ano corrente ou em termos de atualidade (ex.: 'atualizado', 'últimas notícias').",
                "NÃO declare cobertura 'até 2024' (ou qualquer ano anterior) apenas porque o modelo conhece menos; verifique explicitamente o período posterior.",
            ]
        )
    else:
        lines.append(
            "RECORTE HISTÓRICO EXPLÍCITO: preserve o período pedido, sem substituí-lo pelo ano corrente; ainda assim, se houver desdobramentos recentes relevantes, registre-os como complemento claramente separado."
        )

    if task == "plan":
        lines.extend(
            [
                "No campo 'recorte_temporal', descreva o intervalo efetivo do plano. Se não houver recorte histórico do usuário, use a data de referência como limite superior.",
                "Inclua consultas iniciais que permitam verificar o fato mais recente do tema, não apenas o histórico.",
                "Nos campos 'pressupostos' e 'ambiguidades', registre apenas premissas e lacunas do pedido/tema. "
                "Não copie para esses campos avisos metodológicos sobre a SERP, datas suspeitas ou falta de "
                "confirmação: a fronteira da SERP já está definida nas diretrizes e não é um pressuposto do usuário.",
            ]
        )
    elif task == "search":
        lines.extend(
            [
                "Antes de concluir, verifique o estado mais recente do tema. Se as fontes encontradas só cobrirem período antigo, faça nova busca com âncora temporal antes de declarar a lacuna.",
                "Priorize, na leitura, fontes com data de publicação verificável e recente; registre a data no raciocínio e nas conclusões quando ela for material.",
                "Uma fonte sem data explícita não deve ser tratada automaticamente como atual nem como antiga.",
            ]
        )
    elif task == "writer":
        lines.extend(
            [
                "Na seção de Ressalvas e Limitações Metodológicas, declare a data de referência, a data da evidência mais recente encontrada e qualquer lacuna de cobertura.",
                "Não escreva que a cobertura termina em ano anterior se o corpus contém fontes posteriores; se não houver fontes posteriores, diga que não foram encontradas, não que os fatos não existem.",
            ]
        )
    elif task == "audit":
        lines.extend(
            [
                "No critério de atualidade, compare o conteúdo com a data de referência e com o recorte do plano. Reprove omissão de desdobramentos documentados no corpus ou tratamento de marco antigo como se fosse o estado atual.",
            ]
        )

    return "\n".join(f"- {line}" if not line.startswith("-") else line for line in lines)


def build_recency_metadata(policy: RecencyPolicy, source_records: Iterable[dict]) -> dict:
    """Resume a cobertura temporal observada para persistência/auditoria."""
    sources = [s for s in source_records if isinstance(s, dict)]
    dated: List[Tuple[date, str]] = []
    for s in sources:
        raw = s.get("data_fonte") or s.get("published_at") or s.get("timestamp")
        parsed = parse_any_date(raw, policy.reference) if raw else None
        if parsed is None:
            body = s.get("body")
            if body:
                parsed = latest_documented_date([body], policy.reference, max_chars_per_text=6000)
        if parsed is not None and parsed <= policy.reference + timedelta(days=1):
            dated.append((parsed, str(s.get("url") or "")))

    latest = max((d for d, _u in dated), default=None)
    window = policy.window_days or 365
    coverage_recent = bool(latest and (policy.reference - latest).days <= window)
    return {
        "data_referencia": policy.iso,
        "politica": policy.mode,
        "janela_dias": policy.window_days,
        "force_current_year": policy.force_current_year,
        "motivo": policy.reason,
        "data_mais_recente_fonte": latest.isoformat() if latest else None,
        "fontes_com_data": len(dated),
        "fontes_totais": len(sources),
        "cobertura_recente": coverage_recent,
    }
