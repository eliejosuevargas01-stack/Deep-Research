"""Serviço contábil e público de separação de fontes de pesquisa.

Atende ao contrato de separação de fontes:
- consultadas: URLs HTTP(S) únicas efetivamente lidas com sucesso (read_ok com corpus material comprovado).
- utilizadas: Fontes citadas no dossiê final e rastreáveis às evidências lidas.
- nao_utilizadas: Fontes consultadas com sucesso, mas não citadas no artigo final.

Deduplicação canônica estrita, exclusão de candidatas/snippets/falhas, proteção contra
vazamento de IDs internos e suporte a relatórios legados e parciais sem fabricação de zeros.
"""

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.db.models import ConteudoColetado, Pesquisa
from app.db.research_repository import ResearchRepository
from app.schemas.sources import FonteItem, FontesResumo

logger = logging.getLogger(__name__)

# Parâmetros sensíveis de autenticação/tokens em query strings que devem ser excluídos
SENSITIVE_PARAM_NAMES = {
    "token",
    "access_token",
    "auth_token",
    "api_key",
    "apikey",
    "secret",
    "password",
    "pwd",
    "auth",
    "bearer",
    "signature",
    "sig",
    "session",
    "session_id",
    "jwt",
    "private_key",
    "client_secret",
    "key",
}


def normalize_and_validate_url(raw_url: Optional[str]) -> Optional[Tuple[str, str, str]]:
    """Valida e normaliza URL para contabilidade pública.

    Retorna tupla (canonical_key, clean_public_url, dominio) ou None se inválida/insegura.
    - Exige estritamente esquema http ou https.
    - Remove credenciais de usuário (userinfo) e parâmetros sensíveis em query strings.
    - Normaliza porta padrão (80/443), caixa do hostname e IPv6.
    - Preserva rigorosamente semântica de path (sem remoção arbitrária de barra final).
    - Preserva parâmetros de consulta legítimos.
    """
    if not raw_url or not isinstance(raw_url, str):
        return None

    cleaned = raw_url.strip()
    if not cleaned:
        return None

    # Rejeita URLs contendo caracteres de controle
    if any(ord(c) < 32 or ord(c) == 127 for c in cleaned):
        return None

    try:
        parts = urlsplit(cleaned)
    except Exception:
        return None

    scheme = (parts.scheme or "").lower()
    if scheme not in ("http", "https"):
        return None

    try:
        hostname = parts.hostname
    except (ValueError, TypeError):
        return None

    if not hostname:
        return None

    hostname = hostname.lower().rstrip(".")
    if not hostname:
        return None

    # Tratamento seguro de porta (evita falha se porta for malformada, ex: ':bad')
    try:
        port = parts.port
    except (ValueError, TypeError):
        return None

    # Normaliza supressão de portas padrão
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    is_ipv6 = ":" in hostname
    host_fmt = f"[{hostname}]" if is_ipv6 else hostname
    netloc_clean = f"{host_fmt}:{port}" if port else host_fmt

    # Preserva o path original exato (não remove barras finais arbitrariamente)
    path = parts.path or "/"

    # Filtra parâmetros sensíveis de consulta, preservando parâmetros legítimos
    query_clean = ""
    if parts.query:
        try:
            raw_q = parse_qsl(parts.query, keep_blank_values=True)
            safe_q = [(k, v) for k, v in raw_q if k.lower() not in SENSITIVE_PARAM_NAMES]
            if safe_q:
                query_clean = urlencode(safe_q)
        except Exception:
            query_clean = ""

    query_part = f"?{query_clean}" if query_clean else ""
    canonical_key = f"{scheme}://{netloc_clean}{path}{query_part}"
    clean_public_url = urlunsplit((scheme, netloc_clean, path, query_clean, ""))

    return canonical_key, clean_public_url, hostname


def _clean_raw_url_candidate(cand: str) -> str:
    """Limpa pontuações periféricas de URL crua mantendo parênteses balanceados (ex.: Wikipédia)."""
    punct = '.,;:!?"\'[]<>'
    while cand and cand[-1] in punct:
        cand = cand[:-1]
    # Remove parêntese final apenas se desbalanceado (ex.: frase externa `(veja https://...)`)
    while cand and cand.endswith(")"):
        if cand.count(")") > cand.count("("):
            cand = cand[:-1]
        else:
            break
    while cand and cand[-1] in punct:
        cand = cand[:-1]
    return cand


def extract_markdown_citations(text: Optional[str]) -> List[Tuple[str, Optional[str]]]:
    """Extrai URLs e textos-âncora de links e referências em texto Markdown.

    Suporta:
    - Links inline com parênteses balanceados: [texto](https://url_(com_parenteses) "Título")
    - Autolinks: <https://...>
    - Definições de referência usadas: [id]: https://... (apenas quando referenciadas no corpo)
    - URLs diretas no corpo do texto preservando Wikipédia e delimitadores balanceados.
    Ignora blocos de código cercados e links relativos/não-HTTP.
    """
    if not text or not isinstance(text, str):
        return []

    # 1. Remove blocos de código cercados e inline
    sem_codigo = re.sub(r"```[\s\S]*?```", "", text)
    sem_codigo = re.sub(r"~~~[\s\S]*?~~~", "", sem_codigo)
    sem_codigo = re.sub(r"`[^`\n]+`", "", sem_codigo)

    # 2. Extrai definições de referência: [ref_id]: url "título opcional"
    ref_defs: Dict[str, Tuple[str, Optional[str]]] = {}
    ref_def_pattern = re.compile(
        r'^\s*\[([^\]]+)\]:\s*<?([^\s>]+)>?(?:\s+["\'](.*?)["\'])?',
        re.MULTILINE,
    )
    for m in ref_def_pattern.finditer(sem_codigo):
        ref_id = m.group(1).strip().lower()
        u = m.group(2).strip()
        tit = m.group(3).strip() if m.group(3) else None
        ref_defs[ref_id] = (u, tit)

    # Substitui as linhas de definição por espaços para não serem lidas como URLs soltas
    texto_sem_defs = ref_def_pattern.sub("", sem_codigo)

    results: List[Tuple[str, Optional[str]]] = []
    seen_raw_urls: Set[str] = set()

    # 3. Extrai links inline com parênteses balanceados: [anchor](url "title")
    pos = 0
    n = len(texto_sem_defs)
    while pos < n:
        start_bracket = texto_sem_defs.find("[", pos)
        if start_bracket == -1:
            break
        end_bracket = texto_sem_defs.find("]", start_bracket)
        if end_bracket == -1:
            break

        anchor = texto_sem_defs[start_bracket + 1 : end_bracket].strip()

        # Verifica se é link inline: ](
        if end_bracket + 1 < n and texto_sem_defs[end_bracket + 1] == "(":
            paren_start = end_bracket + 1
            depth = 1
            idx = paren_start + 1
            while idx < n and depth > 0:
                if texto_sem_defs[idx] == "(":
                    depth += 1
                elif texto_sem_defs[idx] == ")":
                    depth -= 1
                idx += 1

            if depth == 0:
                content = texto_sem_defs[paren_start + 1 : idx - 1].strip()
                # Separa URL de título opcional
                m_inline = re.match(r'^(<[^>]+>|[^\s]+)(?:\s+["\'](.*?)["\'])?$', content)
                if m_inline:
                    u = m_inline.group(1).strip()
                    if u.startswith("<") and u.endswith(">"):
                        u = u[1:-1].strip()
                    tit = m_inline.group(2).strip() if m_inline.group(2) else None
                    results.append((u, tit or (anchor if anchor else None)))
                    seen_raw_urls.add(u)
                pos = idx
                continue

        # Verifica se é uso de referência: [anchor][ref_id] ou [ref_id][] ou [ref_id]
        if end_bracket + 1 < n and texto_sem_defs[end_bracket + 1] == "[":
            ref_end = texto_sem_defs.find("]", end_bracket + 2)
            if ref_end != -1:
                ref_key = texto_sem_defs[end_bracket + 2 : ref_end].strip().lower()
                if not ref_key:
                    ref_key = anchor.lower()
                if ref_key in ref_defs:
                    u, tit = ref_defs[ref_key]
                    results.append((u, tit or (anchor if anchor else None)))
                    seen_raw_urls.add(u)
                pos = ref_end + 1
                continue
        else:
            # Atalho de referência [ref_id]
            ref_key = anchor.lower()
            if ref_key in ref_defs:
                u, tit = ref_defs[ref_key]
                results.append((u, tit or (anchor if anchor else None)))
                seen_raw_urls.add(u)

        pos = end_bracket + 1

    # 4. Autolinks: <https://...>
    autolink_pattern = re.compile(r"<((?:https?://)[^\s>]+)>")
    for match in autolink_pattern.finditer(texto_sem_defs):
        u = match.group(1).strip()
        results.append((u, None))
        seen_raw_urls.add(u)

    # 5. URLs diretas no texto que não tenham sido capturadas acima
    raw_pattern = re.compile(r"(https?://[^\s<>\"'`]+)")
    for match in raw_pattern.finditer(texto_sem_defs):
        cand = match.group(1).strip()
        cleaned_cand = _clean_raw_url_candidate(cand)
        if cleaned_cand and cleaned_cand not in seen_raw_urls:
            results.append((cleaned_cand, None))
            seen_raw_urls.add(cleaned_cand)

    return results


class SourceAccountingService:
    """Serviço assíncrono para contabilidade, deduplicação e auditoria de fontes."""

    def __init__(self, research_repo: ResearchRepository) -> None:
        self.repo = research_repo

    async def get_source_summary(
        self,
        id_pesquisa: str,
        dossier_override: Optional[str] = None,
    ) -> Optional[FontesResumo]:
        """Calcula o resumo tipado de fontes consultadas, utilizadas e não utilizadas.

        Retorna None se a pesquisa não for localizada (gerando 404 no endpoint).
        Não invoca LLMs, leituras de rede ou mutações de banco de dados.
        """
        pesquisa = await self.repo.get_research(id_pesquisa)
        if not pesquisa:
            return None

        coletas = await self.repo.get_collected_content(id_pesquisa)
        return self.compute_sources(
            id_pesquisa=id_pesquisa,
            pesquisa=pesquisa,
            coletas=coletas,
            dossier_override=dossier_override,
        )

    def compute_sources(
        self,
        id_pesquisa: str,
        pesquisa: Pesquisa,
        coletas: List[ConteudoColetado],
        dossier_override: Optional[str] = None,
    ) -> FontesResumo:
        """Processa de forma determinística as evidências materiais e o dossiê final."""
        # 1. Mapeamento de fontes consultadas a partir das evidências reais de leitura
        consultadas_map: Dict[str, FonteItem] = {}
        disqualified_canon_keys: Set[str] = set()
        # URLs eleitas como fonte pelas personas: permitem classificar uso já na busca
        urls_fonte_keys: Set[str] = set()

        for col in coletas:
            meta_col: Dict[str, Any] = {}
            if col.metadados_coleta:
                try:
                    meta_col = (
                        json.loads(col.metadados_coleta)
                        if isinstance(col.metadados_coleta, str)
                        else col.metadados_coleta
                    )
                except Exception:
                    meta_col = {}

            fontes_dict = meta_col.get("fontes", {}) if isinstance(meta_col, dict) else {}
            if isinstance(fontes_dict, dict) and fontes_dict:
                for _sid, finfo in fontes_dict.items():
                    if not isinstance(finfo, dict):
                        continue
                    raw_u = finfo.get("url")
                    normalized = normalize_and_validate_url(raw_u)
                    if not normalized:
                        continue
                    canon_key, clean_url, domain = normalized

                    status = str(finfo.get("status") or "").lower().strip()
                    raw_body = finfo.get("body")
                    if not isinstance(raw_body, str):
                        raw_body = ""
                    body = raw_body.strip()

                    raw_length = finfo.get("length")
                    parsed_length: Optional[int] = None
                    if isinstance(raw_length, int):
                        parsed_length = raw_length
                    elif isinstance(raw_length, str) and raw_length.strip().isdigit():
                        try:
                            parsed_length = int(raw_length.strip())
                        except (ValueError, TypeError):
                            parsed_length = None

                    if parsed_length is None and body:
                        parsed_length = len(body)

                    # Exige materialidade comprovada (read_ok com texto real não-vazio)
                    has_material_corpus = bool(body) and (parsed_length is not None and parsed_length > 0)

                    if status == "read_ok" and has_material_corpus:
                        titulo = finfo.get("title") or finfo.get("titulo")
                        if not titulo and body:
                            m_tit = re.match(r"^Title:\s*(.+)$", body, re.MULTILINE)
                            if m_tit:
                                titulo = m_tit.group(1).strip()

                        if canon_key not in consultadas_map:
                            consultadas_map[canon_key] = FonteItem(
                                url=clean_url,
                                titulo=str(titulo).strip() if titulo else None,
                                dominio=domain,
                            )
                        elif not consultadas_map[canon_key].titulo and titulo:
                            consultadas_map[canon_key].titulo = str(titulo).strip()
                    else:
                        # Falha explícita, snippet_only ou read_ok vazio: desqualificado
                        disqualified_canon_keys.add(canon_key)

            # URLs eleitas pelas personas em QUALQUER rodada (uso sem depender de dossiê)
            personas_meta = meta_col.get("resultados_personas") if isinstance(meta_col, dict) else None
            if isinstance(personas_meta, dict):
                for p_data in personas_meta.values():
                    if not isinstance(p_data, dict):
                        continue
                    for raw_u in p_data.get("urls_fonte") or []:
                        normalized_f = normalize_and_validate_url(raw_u)
                        if normalized_f:
                            urls_fonte_keys.add(normalized_f[0])
            if col.urls_fonte:
                try:
                    fonte_col = (
                        json.loads(col.urls_fonte)
                        if isinstance(col.urls_fonte, str)
                        else col.urls_fonte
                    )
                except Exception:
                    fonte_col = []
                if isinstance(fonte_col, list):
                    for raw_u in fonte_col:
                        normalized_f = normalize_and_validate_url(raw_u)
                        if normalized_f:
                            urls_fonte_keys.add(normalized_f[0])

            # Processa urls_lidas: fallback para coletas históricas sem metadados estruturados
            if col.urls_lidas:
                try:
                    lidas_list = (
                        json.loads(col.urls_lidas)
                        if isinstance(col.urls_lidas, str)
                        else col.urls_lidas
                    )
                except Exception:
                    lidas_list = []

                if isinstance(lidas_list, list):
                    # Coleta sem fontes_dict detalhado mas com texto material substantivo
                    has_col_body = bool(col.conteudo_coletado and col.conteudo_coletado.strip())
                    for raw_u in lidas_list:
                        normalized = normalize_and_validate_url(raw_u)
                        if not normalized:
                            continue
                        canon_key, clean_url, domain = normalized

                        # Metadados explícitos de falha/snippet dominam: urls_lidas não sobrepõe
                        if canon_key in disqualified_canon_keys:
                            continue

                        # Se não havia fontes_dict mas há corpus material na coleta legada
                        if not fontes_dict and has_col_body:
                            if canon_key not in consultadas_map:
                                consultadas_map[canon_key] = FonteItem(
                                    url=clean_url,
                                    titulo=None,
                                    dominio=domain,
                                )

        # 2. Extração de citações no dossiê final publicado
        dossier_text = dossier_override if dossier_override is not None else pesquisa.dossier_final
        has_dossier = False
        artifact_hash: Optional[str] = None

        if dossier_text and dossier_text.strip():
            has_dossier = True
            artifact_hash = hashlib.sha256(dossier_text.encode("utf-8")).hexdigest()

        used_traced_map: Dict[str, FonteItem] = {}
        used_untraced_map: Dict[str, FonteItem] = {}

        if has_dossier and dossier_text:
            raw_citations = extract_markdown_citations(dossier_text)
            for raw_u, anchor_text in raw_citations:
                normalized = normalize_and_validate_url(raw_u)
                if not normalized:
                    continue
                canon_key, clean_url, domain = normalized

                # Correspondência por identidade canônica normalizada exata
                matched_key: Optional[str] = canon_key if canon_key in consultadas_map else None

                if matched_key:
                    # Fonte consultada e citada: herda metadados lidos
                    item = consultadas_map[matched_key]
                    if not item.titulo and anchor_text and not anchor_text.startswith("http"):
                        item = FonteItem(url=item.url, titulo=anchor_text, dominio=item.dominio)
                    used_traced_map[matched_key] = item
                else:
                    # Fonte citada sem evidência de leitura registrada
                    if canon_key not in used_untraced_map:
                        cand_title = anchor_text if anchor_text and not anchor_text.startswith("http") else None
                        used_untraced_map[canon_key] = FonteItem(
                            url=clean_url,
                            titulo=cand_title,
                            dominio=domain,
                        )

        # 3. Determinação de estado, contagens e partição
        has_evidence = len(consultadas_map) > 0

        if not has_evidence and not has_dossier:
            # Pesquisa recém-criada sem coletas e sem dossiê
            return FontesResumo(
                id_pesquisa=id_pesquisa,
                status="indisponivel",
                total_consultadas=None,
                total_utilizadas=None,
                total_nao_utilizadas=None,
                consultadas=[],
                utilizadas=[],
                nao_utilizadas=[],
                observacao="Nenhuma evidência ou relatório disponível para esta pesquisa.",
                artifact_hash=None,
            )

        if not has_evidence and has_dossier:
            # Relatório legado: dossiê publicado existe, mas evidências de coleta são indisponíveis
            utilizadas_list = sorted(used_untraced_map.values(), key=lambda x: (x.dominio or "", x.url))
            return FontesResumo(
                id_pesquisa=id_pesquisa,
                status="indisponivel",
                total_consultadas=None,
                total_utilizadas=len(utilizadas_list),
                total_nao_utilizadas=None,
                consultadas=[],
                utilizadas=utilizadas_list,
                nao_utilizadas=[],
                observacao="Evidências brutas de coleta indisponíveis para este relatório legado.",
                artifact_hash=artifact_hash,
            )

        # Há evidências de leitura (has_evidence is True)
        consultadas_list = sorted(consultadas_map.values(), key=lambda x: (x.dominio or "", x.url))

        if not has_dossier:
            # PRD v2, I-5/RF-004: o uso é computável já na fase de busca — fonte eleita
            # pelas personas (urls_fonte) é "utilizada"; as demais read_ok são
            # "lida_nao_utilizada". Nada depende do dossiê nem de dossier_override.
            utilizadas_busca: List[FonteItem] = []
            nao_utilizadas_busca: List[FonteItem] = []
            for canon_key, item in sorted(
                consultadas_map.items(), key=lambda kv: (kv[1].dominio or "", kv[1].url)
            ):
                if canon_key in urls_fonte_keys:
                    item.uso = "utilizada"
                    utilizadas_busca.append(item)
                else:
                    item.uso = "lida_nao_utilizada"
                    nao_utilizadas_busca.append(item)
            return FontesResumo(
                id_pesquisa=id_pesquisa,
                status="parcial",
                total_consultadas=len(consultadas_list),
                total_utilizadas=len(utilizadas_busca),
                total_nao_utilizadas=len(nao_utilizadas_busca),
                consultadas=consultadas_list,
                utilizadas=utilizadas_busca,
                nao_utilizadas=nao_utilizadas_busca,
                observacao=(
                    "Dossiê final ainda não publicado; uso classificado na fase de busca "
                    "(urls_fonte das personas contra fontes read_ok)."
                ),
                artifact_hash=None,
            )

        unused_keys = set(consultadas_map.keys()) - set(used_traced_map.keys())
        unused_list = sorted([consultadas_map[k] for k in unused_keys], key=lambda x: (x.dominio or "", x.url))

        if len(used_untraced_map) > 0:
            # Parcial: evidências existem, mas há citações sem registro de leitura correspondente
            combined_used = list(used_traced_map.values()) + list(used_untraced_map.values())
            utilizadas_list = sorted(combined_used, key=lambda x: (x.dominio or "", x.url))
            return FontesResumo(
                id_pesquisa=id_pesquisa,
                status="parcial",
                total_consultadas=len(consultadas_list),
                total_utilizadas=len(utilizadas_list),
                total_nao_utilizadas=None,  # Partição estrita não pode ser assegurada
                consultadas=consultadas_list,
                utilizadas=utilizadas_list,
                nao_utilizadas=unused_list,
                observacao="Evidências de coleta parciais; algumas citações não foram vinculadas às leituras registradas.",
                artifact_hash=artifact_hash,
            )

        # Caso canônico e íntegro: todas as citações são rastreáveis
        utilizadas_list = sorted(used_traced_map.values(), key=lambda x: (x.dominio or "", x.url))
        return FontesResumo(
            id_pesquisa=id_pesquisa,
            status="completo",
            total_consultadas=len(consultadas_list),
            total_utilizadas=len(utilizadas_list),
            total_nao_utilizadas=len(unused_list),
            consultadas=consultadas_list,
            utilizadas=utilizadas_list,
            nao_utilizadas=unused_list,
            observacao=None,
            artifact_hash=artifact_hash,
        )
