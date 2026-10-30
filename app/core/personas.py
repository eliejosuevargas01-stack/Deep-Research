"""Módulo de contratos e resolução de personas de busca e papéis internos do pipeline.

Centraliza as regras contratuais:
1. As 4 personas analíticas de busca permitidas: historiador, visionario, cetico, futurista.
2. Papéis internos do pipeline (planejador, avaliador_semantico, auditor, redator final, auditor_redacao).
3. Resolução determinística do snapshot de personas obrigatórias por pesquisa persistido em metadados_planejamento.
4. Compatibilidade conservadora com planos legados (default de todas as 4 personas quando sem snapshot).
5. NUNCA deriva o contrato a partir de quais resultados calham de estar presentes na coleta!
"""

import json
from typing import Any, Collection, Dict, List, Optional, Set

CANONICAL_SEARCH_PERSONAS: List[str] = ["historiador", "visionario", "cetico", "futurista"]
CANONICAL_SEARCH_PERSONAS_SET: Set[str] = set(CANONICAL_SEARCH_PERSONAS)

INTERNAL_PIPELINE_ROLES: Set[str] = {
    "planejador",
    "avaliador_semantico",
    "auditor",
    "redator",
    "redator final",
    "auditor_redacao",
}


def resolve_required_search_personas(
    pesquisa: Any = None,
    metadados_planejamento: Any = None,
    fallback_personas: Optional[Collection[str]] = None,
) -> List[str]:
    """Resolve o conjunto canônico e ordenado de personas de busca obrigatórias para uma pesquisa.

    Regra contratual:
    - Se a pesquisa possui snapshot válido persistido em metadados_planejamento['preferencias']['personas'],
      retorna esse subconjunto validado (ex: ['historiador', 'cetico']).
    - Em caso de pesquisa legada (sem snapshot, metadados nulos ou malformados, ou lista vazia/inválida):
      utiliza fallback_personas caso informado e válido, ou aplica o padrão conservador legado
      com todas as 4 personas canônicas: ['historiador', 'visionario', 'cetico', 'futurista'].
    - NUNCA deriva o contrato a partir de quais resultados calham de estar presentes na coleta!
    """
    raw_meta = metadados_planejamento
    if raw_meta is None and pesquisa is not None:
        raw_meta = getattr(pesquisa, "metadados_planejamento", None)
        if raw_meta is None:
            raw_meta = getattr(pesquisa, "_metadados_modelo", None)

    meta_obj: Optional[Dict[str, Any]] = None
    if isinstance(raw_meta, str) and raw_meta.strip():
        try:
            parsed = json.loads(raw_meta)
            if isinstance(parsed, dict):
                meta_obj = parsed
        except Exception:
            meta_obj = None
    elif isinstance(raw_meta, dict):
        meta_obj = raw_meta

    if meta_obj and isinstance(meta_obj.get("preferencias"), dict):
        prefs = meta_obj["preferencias"]
        personas = prefs.get("personas")
        if isinstance(personas, list) and personas:
            valid_personas = []
            for p in personas:
                if isinstance(p, str):
                    p_clean = p.strip().lower()
                    if p_clean in CANONICAL_SEARCH_PERSONAS_SET and p_clean not in valid_personas:
                        valid_personas.append(p_clean)
            if valid_personas:
                return valid_personas

    # Fallback para pesquisas legadas sem snapshot quando fornecido explicitamente
    if fallback_personas:
        valid_fallback = []
        for p in fallback_personas:
            if isinstance(p, str):
                p_clean = p.strip().lower()
                if p_clean in CANONICAL_SEARCH_PERSONAS_SET and p_clean not in valid_fallback:
                    valid_fallback.append(p_clean)
        if valid_fallback:
            return valid_fallback

    # Fallback conservador legado: todas as 4 personas canônicas
    return list(CANONICAL_SEARCH_PERSONAS)


def filter_target_personas_for_research(
    requested_personas: Optional[Collection[str]],
    allowed_personas: Collection[str],
) -> List[str]:
    """Filtra um subconjunto de personas solicitadas para garantir que não ultrapasse as personas permitidas da pesquisa."""
    if not requested_personas:
        return list(allowed_personas)
    allowed_set = set(allowed_personas)
    filtered = []
    for p in requested_personas:
        if isinstance(p, str):
            p_clean = p.strip().lower()
            if p_clean in allowed_set and p_clean not in filtered:
                filtered.append(p_clean)
    return filtered or list(allowed_personas)
