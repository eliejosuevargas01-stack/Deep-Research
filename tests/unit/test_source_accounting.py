"""Testes unitários para o serviço contábil de fontes (SourceAccountingService).

Valida os 6 eixos de conformidade e correções de defeitos:
1. Exclusão estrita de falhas com urls_lidas contraditório (metadados explícitos de falha dominam).
2. Exigência de corpus material comprovado (read_ok vazio/sem corpo é rejeitado).
3. Preservação estrita da semântica de caminhos (sem remoção arbitrária de barras finais).
4. Robustez de URLs: portas inválidas (ex: :bad), IPv6, controle de caracteres sem lançar exceções.
5. Parser de citações Markdown: parênteses Wikipédia balanceados, títulos de links, referências usadas vs não usadas.
6. Projeção pública segura: exclusão de credenciais e parâmetros sensíveis de autenticação mantendo queries legítimas.
"""

import hashlib
import json
from typing import Any, cast
import pytest
from app.db.models import ConteudoColetado, Pesquisa
from app.schemas.sources import FonteItem, FontesResumo
from app.services.source_accounting_service import (
    SourceAccountingService,
    extract_markdown_citations,
    normalize_and_validate_url,
)


class DummyRepo:
    """Mock assíncrono em memória para o repositório de pesquisas."""

    def __init__(self, pesquisa=None, coletas=None):
        self._pesquisa = pesquisa
        self._coletas = coletas or []

    async def get_research(self, id_pesquisa: str):
        if self._pesquisa and self._pesquisa.id_pesquisa == id_pesquisa:
            return self._pesquisa
        return None

    async def get_collected_content(self, id_pesquisa: str):
        return [c for c in self._coletas if c.id_pesquisa == id_pesquisa]


def test_url_normalization_and_safety():
    """Valida normalização, remoção de credenciais, queries sensíveis e rejeição de URLs inseguras."""
    # 1. URL HTTP válida simples
    res = normalize_and_validate_url("https://example.com/artigo")
    assert res is not None
    canon, clean, domain = res
    assert canon == "https://example.com/artigo"
    assert clean == "https://example.com/artigo"
    assert domain == "example.com"

    # 2. Remoção de credenciais (userinfo) para proteção de privacidade
    res = normalize_and_validate_url("https://admin:supersecret@example.com/secure/page")
    assert res is not None
    canon, clean, domain = res
    assert "supersecret" not in canon
    assert "supersecret" not in clean
    assert canon == "https://example.com/secure/page"
    assert clean == "https://example.com/secure/page"
    assert domain == "example.com"

    # 3. Remoção de parâmetros sensíveis de consulta (token, api_key, etc.) preservando legítimos
    res_sensitive = normalize_and_validate_url(
        "https://api.example.com/data?token=abc123secret&q=pesquisa&api_key=key999&page=1"
    )
    assert res_sensitive is not None
    canon, clean, _ = res_sensitive
    assert "abc123secret" not in canon
    assert "key999" not in canon
    assert "q=pesquisa" in canon
    assert "page=1" in canon

    # 4. Normalização de portas padrão (80 para http, 443 para https) e preservação de não-padrão
    res_http = normalize_and_validate_url("http://example.org:80/path")
    assert res_http is not None
    assert res_http[0] == "http://example.org/path"

    res_https = normalize_and_validate_url("https://example.org:443/path")
    assert res_https is not None
    assert res_https[0] == "https://example.org/path"

    res_custom = normalize_and_validate_url("https://example.org:8443/path")
    assert res_custom is not None
    assert res_custom[0] == "https://example.org:8443/path"
    assert res_custom[2] == "example.org"

    # 5. Preservação estrita da semântica de path (NÃO remove barras finais de forma arbitrária)
    res_slash = normalize_and_validate_url("https://example.com/docs/")
    res_noslash = normalize_and_validate_url("https://example.com/docs")
    assert res_slash is not None and res_noslash is not None
    assert res_slash[0] == "https://example.com/docs/"
    assert res_noslash[0] == "https://example.com/docs"
    assert res_slash[0] != res_noslash[0]

    # 6. Remoção de fragmentos (âncoras no mesmo documento)
    res_frag = normalize_and_validate_url("https://example.com/page#section-1")
    assert res_frag is not None
    assert res_frag[0] == "https://example.com/page"
    assert res_frag[1] == "https://example.com/page"

    # 7. Robustez contra URLs malformadas que geram exceções em urlsplit (.port ou caracteres de controle)
    assert normalize_and_validate_url("https://example.org:bad/a") is None
    assert normalize_and_validate_url("https://example.com/path\x00with/control") is None
    assert normalize_and_validate_url("https://example.com/path\nwith/newline") is None

    # 8. Rejeição de esquemas não-HTTP
    assert normalize_and_validate_url("javascript:alert(1)") is None
    assert normalize_and_validate_url("data:text/html;base64,PHNjcmlwdD4=") is None
    assert normalize_and_validate_url("file:///etc/passwd") is None
    assert normalize_and_validate_url("mailto:user@example.com") is None
    assert normalize_and_validate_url("ftp://ftp.example.com/file") is None
    assert normalize_and_validate_url("") is None
    assert normalize_and_validate_url(None) is None


def test_extract_markdown_citations_advanced():
    """Valida extração de referências com parênteses Wikipédia, títulos e referências usadas vs não usadas."""
    md_text = """
    # Relatório de Investigação

    Conforme indicado por [Python Wiki](https://en.wikipedia.org/wiki/Python_(programming_language) "Linguagem Python"),
    a linguagem é extensamente utilizada.

    Outro documento relevante: [Exemplo com Título](https://example.org/doc 'Documentação Oficial').

    Veja também estudo em texto cru: (veja https://pt.wikipedia.org/wiki/Inteligencia_artificial_(contexto) para detalhes).
    E autolink canônico: <https://standards.org/rfc-1234>.

    Referência utilizada no corpo [1] e outra [Estudo][2].

    ```markdown
    [Exemplo Não Contabilizado](https://ignorado-no-codigo.com/fake)
    https://outro-ignorado.com
    [3]: https://ignorado-no-codigo.com/ref-3
    ```

    [1]: https://exemplo.org/referencia-usada-1 "Título Ref 1"
    [2]: https://exemplo.org/referencia-usada-2
    [nao_usada]: https://exemplo.org/referencia-nunca-usada "Não Deve Entrar"
    """
    citations = extract_markdown_citations(md_text)
    urls = [c[0] for c in citations]
    titles = {c[0]: c[1] for c in citations}

    # 1. Parênteses balanceados em URLs da Wikipédia preservados integralmente
    assert "https://en.wikipedia.org/wiki/Python_(programming_language)" in urls
    assert titles["https://en.wikipedia.org/wiki/Python_(programming_language)"] == "Linguagem Python"

    # 2. Link com título extraído
    assert "https://example.org/doc" in urls
    assert titles["https://example.org/doc"] == "Documentação Oficial"

    # 3. URL crua envolvida em parênteses na frase preserva o fechamento balanceado
    assert "https://pt.wikipedia.org/wiki/Inteligencia_artificial_(contexto)" in urls

    # 4. Autolink extraído
    assert "https://standards.org/rfc-1234" in urls

    # 5. Definições de referência usadas no corpo são contabilizadas
    assert "https://exemplo.org/referencia-usada-1" in urls
    assert titles["https://exemplo.org/referencia-usada-1"] == "Título Ref 1"
    assert "https://exemplo.org/referencia-usada-2" in urls

    # 6. Definição de referência NUNCA referenciada no corpo NÃO entra como citação
    assert "https://exemplo.org/referencia-nunca-usada" not in urls

    # 7. Código cercado não entra
    assert "https://ignorado-no-codigo.com/fake" not in urls
    assert "https://ignorado-no-codigo.com/ref-3" not in urls


@pytest.mark.asyncio
async def test_contradictory_state_read_failed_dominates_urls_lidas():
    """Defeito 1 reproduzido e resolvido: status=read_failed e corpo vazio não é consultada mesmo se presente em urls_lidas."""
    id_p = "test-contradictory"
    pesquisa = Pesquisa(
        id_pesquisa=id_p,
        tema="Tema Contraditório",
        criado_em="2026-10-26T10:00:00Z",
        dossier_final="# Título\n\nCitando [Falha](https://failed.org/artigo).",
    )

    meta = {
        "fontes": {
            "src_1": {
                "source_id": "src_1",
                "url": "https://failed.org/artigo",
                "status": "read_failed",
                "body": "",
                "length": 0,
            }
        }
    }
    coleta = ConteudoColetado(
        id="col-1",
        id_pesquisa=id_p,
        ponto_id="ponto-1",
        rodada=1,
        tema="Tema",
        ponto="P1",
        conteudo_coletado="",
        urls_lidas=json.dumps(["https://failed.org/artigo"]),  # Contraditório com o status real
        urls_fonte=json.dumps(["https://failed.org/artigo"]),
        metadados_coleta=json.dumps(meta),
        criado_em="2026-10-26T10:00:00Z",
    )

    repo = DummyRepo(pesquisa=pesquisa, coletas=[coleta])
    service = SourceAccountingService(research_repo=cast(Any, repo))

    summary = await service.get_source_summary(id_p)
    assert summary is not None
    # Como a fonte falhou na leitura real, ela NÃO pode constar como consultada!
    assert len(summary.consultadas) == 0
    # O dossiê cita uma fonte não lida, logo é indisponível sem fabricar total_consultadas=1
    assert summary.status == "indisponivel"
    assert summary.total_consultadas is None
    assert summary.total_nao_utilizadas is None
    assert summary.total_utilizadas == 1  # citação conhecida no dossiê
    assert len(summary.utilizadas) == 1
    assert summary.utilizadas[0].url == "https://failed.org/artigo"




@pytest.mark.asyncio
async def test_candidate_only_and_failed_exclusion():
    """Garante que snippet_only e leituras com falha NÃO contam como consultadas."""
    id_p = "test-p1"
    pesquisa = Pesquisa(
        id_pesquisa=id_p,
        tema="Inteligência Artificial",
        criado_em="2026-10-26T10:00:00Z",
        dossier_final="# Título\n\nTexto com citação [Fonte](https://ok.org/artigo).",
    )

    meta = {
        "fontes": {
            "src_1": {
                "source_id": "src_1",
                "url": "https://ok.org/artigo",
                "status": "read_ok",
                "body": "Corpus substancial de texto com mais de 200 caracteres para evidência.",
                "title": "Artigo Aprovado",
                "length": 1500,
            },
            "src_2": {
                "source_id": "src_2",
                "url": "https://candidata.org/apenas-snippet",
                "status": "snippet_only",
                "body": "",
                "title": "Candidata SERP",
                "length": 0,
            },
            "src_3": {
                "source_id": "src_3",
                "url": "https://falha.org/timeout",
                "status": "failed",
                "body": "",
                "title": "Leitura com Falha",
                "length": 0,
            },
        }
    }
    coleta = ConteudoColetado(
        id="col-1",
        id_pesquisa=id_p,
        ponto_id="ponto-1",
        rodada=1,
        tema="Inteligência Artificial",
        ponto="Ponto 1",
        conteudo_coletado="Corpus lido",
        urls_lidas=json.dumps(["https://ok.org/artigo"]),
        urls_fonte=json.dumps(["https://ok.org/artigo", "https://candidata.org/apenas-snippet", "https://falha.org/timeout"]),
        metadados_coleta=json.dumps(meta),
        criado_em="2026-10-26T10:05:00Z",
    )

    repo = DummyRepo(pesquisa=pesquisa, coletas=[coleta])
    service = SourceAccountingService(research_repo=cast(Any, repo))

    summary = await service.get_source_summary(id_p)
    assert summary is not None
    assert summary.status == "completo"
    assert summary.total_consultadas == 1
    assert summary.total_utilizadas == 1
    assert summary.total_nao_utilizadas == 0
    assert len(summary.consultadas) == 1
    assert summary.consultadas[0].url == "https://ok.org/artigo"
    assert summary.consultadas[0].titulo == "Artigo Aprovado"


@pytest.mark.asyncio
async def test_deduplication_across_personas_points_and_retries():
    """Garante deduplicação canônica quando a mesma URL é lida por diferentes personas e rodadas."""
    id_p = "test-dedup"
    pesquisa = Pesquisa(
        id_pesquisa=id_p,
        tema="Energia Renovável",
        criado_em="2026-10-26T10:00:00Z",
        dossier_final="Relatório citando [Fonte](https://example.com/solar).",
    )

    meta_rodada_1 = {
        "fontes": {
            "src_1": {
                "url": "https://example.com/solar",
                "status": "read_ok",
                "body": "Texto substantivo sobre energia solar.",
                "title": "Energia Solar",
            },
            "src_2": {
                "url": "https://example.com/wind",
                "status": "read_ok",
                "body": "Texto substantivo sobre energia eólica.",
                "title": "Energia Eólica",
            },
        }
    }
    meta_rodada_2 = {
        "fontes": {
            "src_1": {
                "url": "https://example.com/solar",
                "status": "read_ok",
                "body": "Texto atualizado sobre energia solar.",
                "title": "Energia Solar (atualizada)",
            },
            "src_3": {
                "url": "https://example.com/wind",
                "status": "read_ok",
                "body": "Texto sobre eólica na rodada 2.",
                "title": "Energia Eólica",
            },
        }
    }

    coleta1 = ConteudoColetado(
        id="col-1",
        id_pesquisa=id_p,
        ponto_id="p-1",
        rodada=1,
        tema="Tema",
        ponto="P1",
        conteudo_coletado="c1",
        urls_lidas=json.dumps(["https://example.com/solar", "https://example.com/wind"]),
        urls_fonte="[]",
        metadados_coleta=json.dumps(meta_rodada_1),
        criado_em="2026-10-26T10:01:00Z",
    )
    coleta2 = ConteudoColetado(
        id="col-2",
        id_pesquisa=id_p,
        ponto_id="p-1",
        rodada=2,
        tema="Tema",
        ponto="P1",
        conteudo_coletado="c2",
        urls_lidas=json.dumps(["https://example.com/solar", "https://example.com/wind"]),
        urls_fonte="[]",
        metadados_coleta=json.dumps(meta_rodada_2),
        criado_em="2026-10-26T10:02:00Z",
    )

    repo = DummyRepo(pesquisa=pesquisa, coletas=[coleta1, coleta2])
    service = SourceAccountingService(research_repo=cast(Any, repo))

    summary = await service.get_source_summary(id_p)
    assert summary is not None
    assert summary.total_consultadas == 2
    assert summary.total_utilizadas == 1  # solar
    assert summary.total_nao_utilizadas == 1  # wind
    assert summary.status == "completo"


@pytest.mark.asyncio
async def test_legacy_report_without_evidence_honest_nulls():
    """Em relatório legado sem coletas salvas, exibe status indisponivel e contagens None (não 0)."""
    id_p = "legacy-report-1"
    dossier = "Dossiê legado citando [Estudo](https://antigo.org/artigo-2024)."
    doc_hash = hashlib.sha256(dossier.encode("utf-8")).hexdigest()

    pesquisa = Pesquisa(
        id_pesquisa=id_p,
        tema="Tema Legado",
        criado_em="2024-01-01T00:00:00Z",
        dossier_final=dossier,
    )
    repo = DummyRepo(pesquisa=pesquisa, coletas=[])
    service = SourceAccountingService(research_repo=cast(Any, repo))

    summary = await service.get_source_summary(id_p)
    assert summary is not None
    assert summary.status == "indisponivel"
    assert summary.total_consultadas is None  # Não inventa 0
    assert summary.total_nao_utilizadas is None  # Não inventa 0
    assert summary.total_utilizadas == 1
    assert len(summary.consultadas) == 0
    assert len(summary.utilizadas) == 1
    assert summary.utilizadas[0].url == "https://antigo.org/artigo-2024"
    assert summary.artifact_hash == doc_hash
    assert "legado" in (summary.observacao or "").lower()


@pytest.mark.asyncio
async def test_partial_evidence_when_untraced_citation_exists():
    """Quando o dossiê cita fontes não encontradas nas evidências de leitura, status é parcial."""
    id_p = "partial-test"
    dossier = (
        "Artigo citando fonte lida [Lida](https://lida.com/artigo) "
        "e fonte desconhecida [Desconhecida](https://desconhecida.com/artigo)."
    )
    pesquisa = Pesquisa(
        id_pesquisa=id_p,
        tema="Tema",
        criado_em="2026-10-26T10:00:00Z",
        dossier_final=dossier,
    )
    meta = {
        "fontes": {
            "src_1": {"url": "https://lida.com/artigo", "status": "read_ok", "body": "Texto substantivo", "title": "Lida OK"},
            "src_2": {"url": "https://lida.com/nao-citada", "status": "read_ok", "body": "Texto substantivo 2", "title": "Não Citada"},
        }
    }
    coleta = ConteudoColetado(
        id="col-1",
        id_pesquisa=id_p,
        ponto_id="p1",
        rodada=1,
        tema="Tema",
        ponto="P1",
        conteudo_coletado="c",
        urls_lidas=json.dumps(["https://lida.com/artigo", "https://lida.com/nao-citada"]),
        urls_fonte="[]",
        metadados_coleta=json.dumps(meta),
        criado_em="2026-10-26T10:01:00Z",
    )

    repo = DummyRepo(pesquisa=pesquisa, coletas=[coleta])
    service = SourceAccountingService(research_repo=cast(Any, repo))

    summary = await service.get_source_summary(id_p)
    assert summary is not None
    assert summary.status == "parcial"
    assert summary.total_consultadas == 2
    assert summary.total_utilizadas == 2  # 1 lida + 1 desconhecida
    assert summary.total_nao_utilizadas is None  # Partição incompleta
    assert len(summary.nao_utilizadas) == 1
    assert summary.nao_utilizadas[0].url == "https://lida.com/nao-citada"


@pytest.mark.asyncio
async def test_privacy_and_security_guarantees():
    """Garante que nenhum ID interno ou dado confidencial vaza no schema público."""
    id_p = "privacy-test"
    pesquisa = Pesquisa(
        id_pesquisa=id_p,
        tema="Privacidade",
        criado_em="2026-10-26T10:00:00Z",
        dossier_final="Citando [Fonte](https://privacidade.org/doc).",
    )
    meta = {
        "fontes": {
            "src_secret_uuid_999": {
                "source_id": "src_secret_uuid_999",
                "url": "https://privacidade.org/doc",
                "status": "read_ok",
                "title": "Documento Público",
                "body": "Texto confidencial de 5000 palavras...",
                "body_hash": "deadbeef1234",
            }
        }
    }
    coleta = ConteudoColetado(
        id="col-priv",
        id_pesquisa=id_p,
        ponto_id="p1",
        rodada=1,
        tema="Tema",
        ponto="Ponto",
        conteudo_coletado="Corpus interno",
        urls_lidas=json.dumps(["https://privacidade.org/doc"]),
        urls_fonte="[]",
        metadados_coleta=json.dumps(meta),
        criado_em="2026-10-26T10:00:00Z",
    )

    repo = DummyRepo(pesquisa=pesquisa, coletas=[coleta])
    service = SourceAccountingService(research_repo=cast(Any, repo))

    summary = await service.get_source_summary(id_p)
    assert summary is not None
    data = summary.model_dump()

    # Valida campos permitidos (uso é classificação pública desde I-5/RF-004)
    for key in ("consultadas", "utilizadas", "nao_utilizadas"):
        for item in data[key]:
            assert set(item.keys()) == {"url", "titulo", "dominio", "uso"}
            assert "source_id" not in item
            assert "body" not in item
            assert "body_hash" not in item
            assert "deadbeef" not in json.dumps(item)
            assert "src_secret_uuid_999" not in json.dumps(item)


@pytest.mark.asyncio
async def test_exact_slash_identity_no_invented_equivalence():
    """Defeito review2.1: https://example.org/a/ consultada e https://example.org/a citada NÃO são equivalentes sem alias real."""
    id_p = "test-slash-diff"
    pesquisa = Pesquisa(
        id_pesquisa=id_p,
        tema="Tema Barra",
        criado_em="2026-10-26T10:00:00Z",
        dossier_final="Citando [Fonte](https://example.org/a).",
    )
    meta = {
        "fontes": {
            "src_1": {
                "source_id": "src_1",
                "url": "https://example.org/a/",
                "status": "read_ok",
                "title": "Página com Barra",
                "body": "Texto substantivo de evidência lida.",
                "length": 100,
            }
        }
    }
    coleta = ConteudoColetado(
        id="col-1",
        id_pesquisa=id_p,
        ponto_id="p1",
        rodada=1,
        tema="Tema",
        ponto="P1",
        conteudo_coletado="c",
        urls_lidas=json.dumps(["https://example.org/a/"]),
        urls_fonte="[]",
        metadados_coleta=json.dumps(meta),
        criado_em="2026-10-26T10:00:00Z",
    )

    repo = DummyRepo(pesquisa=pesquisa, coletas=[coleta])
    service = SourceAccountingService(research_repo=cast(Any, repo))

    summary = await service.get_source_summary(id_p)
    assert summary is not None
    # Como as identidades diferem (/a/ vs /a), a citação não é rastreada na fonte lida: estado deve ser parcial
    assert summary.status == "parcial"
    assert summary.total_consultadas == 1
    assert summary.consultadas[0].url == "https://example.org/a/"
    assert summary.total_utilizadas == 1
    assert summary.utilizadas[0].url == "https://example.org/a"
    assert summary.total_nao_utilizadas is None


@pytest.mark.asyncio
async def test_read_ok_urls_contam_sem_depender_de_body():
    """PRD v3: o catálogo só tem URLs; read_ok basta, body/hash não existem mais."""
    id_p = "test-malformed-shape"
    pesquisa = Pesquisa(
        id_pesquisa=id_p,
        tema="Tema Malformado",
        criado_em="2026-10-26T10:00:00Z",
        dossier_final="Citando [Fonte](https://valid.org/doc).",
    )
    meta = {
        "versao": 3,
        "fontes": [
            {"url": "https://valid.org/doc", "uso": "utilizada", "titulo": "Documento Válido", "status": "read_ok"},
            {"url": "https://invalid-body.org/doc", "uso": "lida_nao_utilizada", "titulo": "Outro", "status": "read_ok"},
        ],
    }
    coleta = ConteudoColetado(
        id="col-1",
        id_pesquisa=id_p,
        ponto_id="p1",
        rodada=1,
        tema="Tema",
        ponto="P1",
        conteudo_coletado="c",
        urls_lidas=json.dumps(["https://valid.org/doc", "https://invalid-body.org/doc"]),
        urls_fonte=json.dumps(["https://valid.org/doc"]),
        metadados_coleta=json.dumps(meta),
        criado_em="2026-10-26T10:00:00Z",
    )

    repo = DummyRepo(pesquisa=pesquisa, coletas=[coleta])
    service = SourceAccountingService(research_repo=cast(Any, repo))

    summary = await service.get_source_summary(id_p)
    assert summary is not None
    assert summary.total_consultadas == 2
    assert {c.url for c in summary.consultadas} == {
        "https://valid.org/doc",
        "https://invalid-body.org/doc",
    }
    assert summary.status == "completo"


@pytest.mark.asyncio
async def test_evidence_with_no_dossier_classifica_uso_na_fase_de_busca():
    """PRD v2, I-5/RF-004: sem dossiê, o uso é classificado pelas urls_fonte das personas.

    Contrato alterado (antes: contadores desconhecidos/None). A classificação por
    URL precisa existir já na fase de busca, sem depender de dossier_override.
    """
    id_p = "test-no-dossier"
    pesquisa = Pesquisa(
        id_pesquisa=id_p,
        tema="Tema Sem Dossiê",
        criado_em="2026-10-26T10:00:00Z",
        dossier_final=None,  # Dossiê ainda não redigido
    )
    meta = {
        "fontes": {
            "src_1": {
                "source_id": "src_1",
                "url": "https://example.org/leitura",
                "status": "read_ok",
                "title": "Leitura Realizada",
                "body": "Texto substantivo de coleta em andamento.",
                "length": 500,
            },
            "src_2": {
                "source_id": "src_2",
                "url": "https://example.org/eleita",
                "status": "read_ok",
                "title": "Fonte Eleita",
                "body": "Outro texto substantivo lido e eleito como fonte.",
                "length": 500,
            },
        },
        "resultados_personas": {
            "historiador": {"urls_fonte": ["https://example.org/eleita"]},
        },
    }
    coleta = ConteudoColetado(
        id="col-1",
        id_pesquisa=id_p,
        ponto_id="p1",
        rodada=1,
        tema="Tema",
        ponto="P1",
        conteudo_coletado="c",
        urls_lidas=json.dumps(["https://example.org/leitura", "https://example.org/eleita"]),
        urls_fonte=json.dumps(["https://example.org/eleita"]),
        metadados_coleta=json.dumps(meta),
        criado_em="2026-10-26T10:00:00Z",
    )

    repo = DummyRepo(pesquisa=pesquisa, coletas=[coleta])
    service = SourceAccountingService(research_repo=cast(Any, repo))

    summary = await service.get_source_summary(id_p)
    assert summary is not None
    assert summary.status == "parcial"
    assert summary.total_consultadas == 2
    assert summary.total_utilizadas == 1
    assert summary.total_nao_utilizadas == 1
    assert [u.url for u in summary.utilizadas] == ["https://example.org/eleita"]
    assert summary.utilizadas[0].uso == "utilizada"
    assert [u.url for u in summary.nao_utilizadas] == ["https://example.org/leitura"]
    assert summary.nao_utilizadas[0].uso == "lida_nao_utilizada"
    assert summary.artifact_hash is None
