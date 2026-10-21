"""Isolated proposal: conservative citation screening and deterministic gap rendering."""
import re

URL = re.compile(r"\]\((https?://[^\s)]+)\)")
CLASSROOM = re.compile(r"^\*\*Proposta didática:\*\*\s+desenhe dois cartões, 0 e 1; use moeda parada para representar escolha entre ambos; depois pergunte: “Onde comparação deixa de funcionar\?”\s*$")
GAP_NOTICE = "Lacuna: nenhuma evidência aproveitável após quatro tentativas. Conteúdo não disponível; sem fontes para citar."


def requires_citation(line: str) -> bool:
    """Recognize syntax, not truth: all substantive prose/list/table candidates are guarded."""
    s = line.strip()
    if not s or s.startswith(("#", ">")) or s.lower().startswith(("references", "fontes", "referências")):
        return False
    if CLASSROOM.fullmatch(s):
        return False
    s = re.sub(r"^(?:\*\*|__)(.+?)(?:\*\*|__)", r"\1", s)
    stripped = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+|\|\s*)", "", s)
    substantive = bool(re.search(r"[A-Za-zÀ-ÿ]{3,}", stripped)) and len(stripped.split()) >= 4
    return substantive and (bool(re.match(r"^(?:[-*+]\s+|\d+[.)]\s+|\|)", s)) or bool(re.search(r"[.!?]\s*$", s)))


def validate_lines(text: str, known_urls: set[str]) -> None:
    for line in text.splitlines():
        links = set(URL.findall(line))
        if not links.issubset(known_urls):
            raise ValueError("uncollected citation URL")
        if line.strip().startswith("Lacuna: nenhuma evidência aproveitável após quatro tentativas."):
            continue
        if requires_citation(line) and not links:
            raise ValueError("uncited factual candidate")


def render_gap_report(points: list[tuple[str, bool]]) -> str:
    """Each pair: title and has_evidence. No generated factual prose for missing evidence."""
    return "\n\n".join(
        f"## {title}\n" + ("Evidência disponível; consulte síntese sustentada por fontes." if has_evidence
                               else "Lacuna: nenhuma evidência aproveitável após quatro tentativas. Conteúdo não disponível; sem fontes para citar.")
        for title, has_evidence in points
    )


def validate_lines(text: str, known_urls: set[str]) -> None:
    for line in text.splitlines():
        links = set(URL.findall(line))
        if not links.issubset(known_urls):
            raise ValueError("uncollected citation URL")
        if line.strip() == GAP_NOTICE:
            continue
        if requires_citation(line) and not links:
            raise ValueError("uncited factual candidate")


def render_gap_report(points: list[tuple[str, bool]]) -> str:
    """Each pair: title and has_evidence. No generated factual prose for missing evidence."""
    return "\n\n".join(
        f"## {title}\n" + ("Evidência disponível; consulte síntese sustentada por fontes." if has_evidence
                               else "Lacuna: nenhuma evidência aproveitável após quatro tentativas. Conteúdo não disponível; sem fontes para citar.")
        for title, has_evidence in points
    )
