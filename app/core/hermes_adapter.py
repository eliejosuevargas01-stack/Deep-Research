"""Adaptador entre a UI e o perfil Hermes embutido.

O ciclo Hermes grava artefatos JSON no workspace, um por etapa, com os mesmos campos
que o banco usa — nada aqui deriva dado de Markdown:

    PLAN.json                                  planner   (contrato DR-006 + personas)
    HISTORIADOR_SEARCH.json ... 4 personas     searchers (tentativas, URLs, lacunas)
    AUDITORIA.json                             auditor   (rodadas com os 12 critérios)
    DOSSIE.json                                redator   (dossiê final + fontes)

Cada artefato é validado por Pydantic; artefato torto vira 422 com diagnóstico, nunca
uma tela plausível e vazia. O que a API devolve vem do banco.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.core import hermes_planner
from app.core.hermes_ids import pontos_de
from app.core.urls import sanitizar_url_fonte, sanitizar_urls
from app.schemas.artefatos import (
    AuditoriaArtefato,
    BuscaArtefato,
    DossieArtefato,
    PlanoArtefato,
)
from app.schemas.plan import PlanoInvestigacao

_LOCKS: Dict[str, asyncio.Lock] = {}

PERSONA_ARQUIVOS = {
    "historiador": "HISTORIADOR_SEARCH.json",
    "visionario": "VISIONARIO_SEARCH.json",
    "cetico": "CETICO_SEARCH.json",
    "futurista": "FUTURISTA_SEARCH.json",
}
PLANO_ARQUIVO = "PLAN.json"
AUDITORIA_ARQUIVO = "AUDITORIA.json"
DOSSIE_ARQUIVO = "DOSSIE.json"
ARQUIVOS_OBRIGATORIOS = [
    PLANO_ARQUIVO,
    *PERSONA_ARQUIVOS.values(),
    AUDITORIA_ARQUIVO,
    DOSSIE_ARQUIVO,
]

CHAVES_PLANO = tuple(PlanoInvestigacao.model_fields)
_BLOCO_JSON = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)


def registrar_pontos(id_pesquisa: str, pontos) -> None:
    """Liga a pesquisa aos pontos do plano (os eventos caem no card certo)."""
    from app.core import hermes_ids

    hermes_ids.registrar(id_pesquisa, pontos)


def _pub(id_pesquisa: str, evento: str, **dados) -> None:
    """Publica no hub SSE; observabilidade nunca derruba a resposta HTTP."""
    try:
        from app.core import hermes_ids
        from app.core.pipeline_runner import get_pipeline_event_hub

        dados.setdefault("ponto_id", hermes_ids.ponto_de(id_pesquisa))
        get_pipeline_event_hub().publish(id_pesquisa, evento, {"id_pesquisa": id_pesquisa, **dados})
    except Exception:
        pass


def _ler_json(caminho: Path) -> Any:
    texto = caminho.read_text(encoding="utf-8", errors="replace").strip()
    cerca = _BLOCO_JSON.search(texto)
    if cerca:
        texto = cerca.group(1)
    return json.loads(texto)


def _artefato(modelo, caminho: Path) -> Dict[str, Any]:
    """Lê e valida um artefato: {"valido", "erro", "dados"}."""
    if not caminho.exists():
        return {"valido": False, "erro": f"{caminho.name} ausente", "dados": None}
    try:
        bruto = _ler_json(caminho)
    except json.JSONDecodeError as exc:
        return {"valido": False, "erro": f"JSON inválido em {caminho.name}: {exc}", "dados": None}
    try:
        return {"valido": True, "erro": None, "dados": modelo.model_validate(bruto).model_dump()}
    except ValidationError as exc:
        primeiro = exc.errors()[0]
        local = ".".join(str(p) for p in primeiro["loc"]) or "raiz"
        return {
            "valido": False,
            "erro": f"{caminho.name} fora do contrato em {local}: {primeiro['msg']}",
            "dados": None,
        }


def plan_payload(workspace: Path) -> Dict[str, Any]:
    """Plano estruturado: PLAN.json validado contra o contrato DR-006."""
    leitura = _artefato(PlanoArtefato, workspace / PLANO_ARQUIVO)
    if not leitura["valido"]:
        return {"valido": False, "erro": leitura["erro"], "plano": None}
    plano = dict(leitura["dados"])
    validado = PlanoInvestigacao.model_validate(plano).model_dump()
    validado["personas"] = plano["personas"]
    return {"valido": True, "erro": None, "plano": validado}


def pontos_do_plano(plano: Dict[str, Any], limite: Optional[int] = None) -> List[str]:
    """Um ponto por eixo; o card mostra a pergunta principal do eixo."""
    eixos = [e for e in (plano.get("eixos") or []) if isinstance(e, dict)]
    pontos = [str(e.get("pergunta_principal") or "").strip() for e in eixos]
    pontos = [p for p in pontos if p]
    if not pontos:
        pontos = [str(plano.get("pedido_original") or plano.get("pedido_normalizado") or "Investigação")]
    if limite and limite > 0:
        pontos = pontos[:limite]
    return pontos


def busca_personas(workspace: Path) -> List[Dict[str, Any]]:
    """Uma entrada por persona a partir dos quatro JSON de busca."""
    saida: List[Dict[str, Any]] = []
    for persona, nome in PERSONA_ARQUIVOS.items():
        leitura = _artefato(BuscaArtefato, workspace / nome)
        if not leitura["valido"]:
            continue
        tentativas = leitura["dados"]["tentativas"]
        analise = "\n\n".join(
            f"### Tentativa {t['rodada']}\n\n{t['analise']}" for t in tentativas
        )
        urls_lidas: List[str] = []
        urls_fonte: List[str] = []
        lacunas: List[str] = []
        for t in tentativas:
            for url in t["urls_lidas"]:
                if url not in urls_lidas:
                    urls_lidas.append(url)
            for url in t["urls_fonte"]:
                if url not in urls_fonte:
                    urls_fonte.append(url)
            lacunas.extend(t["lacunas"])
        saida.append(
            {
                "persona": persona,
                "analise": analise,
                "urls_fonte": urls_fonte,
                "urls_lidas": urls_lidas,
                "queries_executadas": sum(len(t["consultas"]) for t in tentativas),
                "tentativas": len(tentativas),
                "paginas_lidas": sum(t["paginas_lidas"] for t in tentativas),
                "falha_coleta": not urls_fonte,
                "lacunas": lacunas or None,
            }
        )
    return saida


def search_payload(pesquisa_id: str, workspace: Path) -> Dict[str, Any]:
    """SearchResponse a partir dos quatro *_SEARCH.json."""
    personas = busca_personas(workspace)
    total_lidas = sum(p["paginas_lidas"] for p in personas)
    total_fontes = sum(len(p["urls_fonte"]) for p in personas)
    caracteres = sum(len(p["analise"]) for p in personas)
    tentativas = max([p["tentativas"] for p in personas] or [1])
    pontos = pontos_de(pesquisa_id)
    api_personas = [
        {
            "persona": p["persona"],
            "analise": p["analise"],
            "urls_fonte": p["urls_fonte"],
            "urls_lidas": p["urls_lidas"],
            "queries_executadas": p["queries_executadas"],
            "falha_coleta": p["falha_coleta"],
            "lacunas": p["lacunas"],
        }
        for p in personas
    ]
    for indice, ponto_id in enumerate(pontos, start=1):
        for p in personas:
            _pub(
                pesquisa_id,
                "search.progress",
                ponto_id=ponto_id,
                persona=p["persona"],
                queries_executadas=p["queries_executadas"],
                urls_lidas=p["paginas_lidas"] or len(p["urls_lidas"]),
                falha_coleta=p["falha_coleta"],
                reasoning_coleta=p["analise"][-12000:],
            )
        _pub(pesquisa_id, "point.status", ponto_id=ponto_id, ponto_n=indice, status="coletado", tentativas=tentativas)
    return {
        "id_pesquisa": pesquisa_id,
        "total_pontos_processados": len(pontos),
        "status_pesquisa": "coletado",
        "total_falhas_coleta": sum(1 for p in personas if p["falha_coleta"]),
        "resumo_coletas": [
            {
                "ponto_id": ponto_id,
                "ponto_n": indice,
                "status": "coletado",
                "falha_coleta": not personas,
                "total_urls_lidas": total_lidas,
                "total_urls_fonte": total_fontes,
                "tamanho_conteudo_caracteres": caracteres,
                "tentativas": tentativas,
                "personas": api_personas,
            }
            for indice, ponto_id in enumerate(pontos, start=1)
        ],
    }


def audit_payload(pesquisa_id: str, workspace: Path, criterios_minimos: int = 11) -> Dict[str, Any]:
    """AuditResponse a partir da última rodada de AUDITORIA.json."""
    pontos = pontos_de(pesquisa_id)
    leitura = _artefato(AuditoriaArtefato, workspace / AUDITORIA_ARQUIVO)
    if not leitura["valido"]:
        return {
            "id_pesquisa": pesquisa_id,
            "total_pontos": len(pontos),
            "aprovados": 0,
            "reprovados": len(pontos),
            "pronto_para_writer": False,
            "auditorias": [
                {
                    "ponto_id": pesquisa_id,
                    "ponto_n": 1,
                    "status": "reprovado",
                    "pontuacao_percentual": 0.0,
                    "criterios_aprovados": 0,
                    "criterios_minimos": criterios_minimos,
                    "valido": False,
                    "diagnostico": leitura["erro"],
                }
            ],
        }
    rodada = leitura["dados"]["rodadas"][-1]
    aprovado = rodada["veredito"] == "APROVADO" and rodada["nota"] >= criterios_minimos
    criterios = [
        {
            "id": c["id"],
            "aprovado": c["aprovado"],
            "justificativa": c["justificativa"],
            "claim_ids": [],
            "source_ids": [],
        }
        for c in rodada["criterios"]
    ]
    fracos = rodada.get("lacunas")
    reasoning = json.dumps(rodada, ensure_ascii=False)
    for indice, ponto_id in enumerate(pontos, start=1):
        _pub(
            pesquisa_id,
            "audit.result",
            ponto_id=ponto_id,
            ponto_n=indice,
            status="aprovado" if aprovado else "reprovado",
            pontuacao_percentual=round(rodada["nota"] / 12 * 100, 2),
            criterios_aprovados=rodada["nota"],
            reasoning_auditoria=reasoning,
            pontos_fracos=fracos,
        )
        _pub(
            pesquisa_id,
            "point.status",
            ponto_id=ponto_id,
            ponto_n=indice,
            status="aprovado" if aprovado else "reprovado",
            tentativas=rodada["rodada"],
        )
    return {
        "id_pesquisa": pesquisa_id,
        "total_pontos": len(pontos),
        "aprovados": len(pontos) if aprovado else 0,
        "reprovados": 0 if aprovado else len(pontos),
        "pronto_para_writer": aprovado,
        "auditorias": [
            {
                "ponto_id": ponto_id,
                "ponto_n": indice,
                "status": "aprovado" if aprovado else "reprovado",
                "pontuacao_percentual": round(rodada["nota"] / 12 * 100, 2),
                "criterios_aprovados": rodada["nota"],
                "criterios_minimos": criterios_minimos,
                "valido": True,
                "criterios": criterios,
                "pontos_fracos": fracos,
                "reasoning_auditoria": reasoning,
                "resumo_auditoria": f"Rodada {rodada['rodada']}: {rodada['veredito']} {rodada['nota']}/12 (auditor Hermes)",
            }
            for indice, ponto_id in enumerate(pontos, start=1)
        ],
    }


def writer_payload(pesquisa_id: str, tema: str, workspace: Path) -> Dict[str, Any]:
    """WriterResponse a partir de DOSSIE.json."""
    leitura = _artefato(DossieArtefato, workspace / DOSSIE_ARQUIVO)
    texto = leitura["dados"]["dossier_final"] if leitura["valido"] else ""
    if texto.strip():
        _pub(pesquisa_id, "writer.progress", status="concluido", total_caracteres=len(texto))
        _pub(pesquisa_id, "pipeline.status", status_pipeline="concluido")
        _pub(
            pesquisa_id,
            "report.final",
            status="concluido",
            dossier_final=texto,
            total_caracteres=len(texto),
            concluido_em=None,
        )
    return {
        "id_pesquisa": pesquisa_id,
        "tema": tema,
        "status": "concluido" if texto.strip() else "falha",
        "total_caracteres_dossier": len(texto),
        "concluido_em": None,
        "webhook_entrega": None,
        "dossier_final": texto or None,
        "diagnostico": None if texto.strip() else leitura["erro"],
        "metadados": {"pipeline": "hermes", "diretorio": str(workspace), "artefato": DOSSIE_ARQUIVO},
    }


async def garantir_pesquisa(pesquisa_id: str, tema: str, n_pontos: int = 1) -> Path:
    """Garante o ciclo Hermes rodando e devolve o workspace assim que PLAN.json é válido."""
    workspace = hermes_planner.criar_workspace(pesquisa_id, tema)
    if plan_payload(workspace)["valido"] and (workspace / DOSSIE_ARQUIVO).exists():
        return workspace
    lock = _LOCKS.setdefault(pesquisa_id, asyncio.Lock())
    async with lock:
        ex = hermes_planner.execucao_existente(pesquisa_id)
        if ex is None or (ex.tarefa is not None and ex.tarefa.done()):
            ex = await hermes_planner.obter_ou_iniciar(tema, pesquisa_id, n_pontos)
        limite = time.monotonic() + float(os.environ.get("DR_PLAN_TIMEOUT", "180"))
        while time.monotonic() < limite:
            if plan_payload(workspace)["valido"]:
                return workspace
            if ex.tarefa is not None and ex.tarefa.done():
                break
            await asyncio.sleep(2.0)
    raise ValueError(f"planner não escreveu {PLANO_ARQUIVO} válido dentro do tempo esperado")


def _workspace_exato(pesquisa_id: str, tema: str) -> Path:
    """Workspace determinístico da pesquisa (mesma regra de `criar_workspace`)."""
    return hermes_planner.caminho_workspace(pesquisa_id, tema)


def _raiz_para(pesquisa_id: str) -> List[Path]:
    """Workspaces existentes para o id (o slug do tema varia).

    Só aceita pasta cuja marca `.pesquisa_id` confirma o dono ou, em workspaces
    antigos sem marca, o sufixo derivado do id — nunca `plan-179`, que era comum
    a todas as pesquisas da semana.
    """
    base = hermes_planner._raiz_pesquisas()
    if not base.exists():
        return []
    sufixos = {f"-{hermes_planner.sufixo_workspace(pesquisa_id)}"}
    legado = f"-{pesquisa_id[:8]}"
    if legado != sufixos.copy().pop():
        sufixos.add(legado)
    achados: List[Path] = []
    for diretorio in base.iterdir():
        if not diretorio.is_dir():
            continue
        marca = diretorio / ".pesquisa_id"
        if marca.exists():
            dono = marca.read_text(encoding="utf-8", errors="replace").strip()
            if dono == pesquisa_id:
                achados.append(diretorio)
            continue
        if any(diretorio.name.endswith(sufixo) for sufixo in sufixos):
            achados.append(diretorio)
    return sorted(achados)


async def aguardar_coletas(pesquisa_id: str, timeout: float = 3600.0) -> None:
    """Espera os quatro *_SEARCH.json existirem e pararem de crescer."""
    ex = hermes_planner.execucao_existente(pesquisa_id)
    if ex is None:
        return
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        tamanhos = {}
        for nome in PERSONA_ARQUIVOS.values():
            alvo = ex.workspace / nome
            tamanhos[nome] = alvo.stat().st_size if alvo.exists() else 0
        if all(tamanhos.values()):
            await asyncio.sleep(4.0)
            estaveis = all(
                (ex.workspace / nome).stat().st_size == tamanho
                for nome, tamanho in tamanhos.items()
                if (ex.workspace / nome).exists()
            )
            if estaveis:
                return
        if ex.tarefa is not None and ex.tarefa.done():
            return
        await asyncio.sleep(3.0)


async def aguardar_arquivo(
    pesquisa_id: str, nome: str, timeout: float = 3600.0, tema: Optional[str] = None
) -> Path:
    """Espera (sem reiniciar o ciclo) o arquivo aparecer; devolve o workspace.

    Com `tema`, o workspace é resolvido pelo slug exato: ids que compartilham os
    primeiros 8 caracteres (ex.: `plan-179…`) apontavam para a pasta de outra
    pesquisa e misturavam dossiê e tokens.
    """
    ex = hermes_planner.execucao_existente(pesquisa_id)
    if ex is not None:
        await ex.aguardar_arquivo(nome, timeout=timeout)
        return ex.workspace
    if tema:
        exato = _workspace_exato(pesquisa_id, tema)
        if (exato / nome).exists():
            return exato
        raise ValueError(f"{nome} ausente em {exato.name}")
    for workspace in _raiz_para(pesquisa_id):
        if (workspace / nome).exists():
            return workspace
    raise ValueError(f"pesquisa sem ciclo ativo e sem {nome}")


# ---------------------------------------------------------------------------
# Persistência: o JSON é a produção do agente, o banco é a verdade da tela.
# ---------------------------------------------------------------------------

async def _aplicar_tokens(repo, pesquisa_id: str, workspace: Path) -> None:
    """Copia o consumo acumulado da pesquisa — nunca regride para um turno parcial."""
    from app.core import usage as usage_mod

    resumo = usage_mod.gravar_resumo(workspace)
    total = resumo["total"]
    if not total.get("total_tokens"):
        return
    pesquisa = await repo.get_research(pesquisa_id)
    atuais = (
        int(getattr(pesquisa, "tokens_prompt", 0) or 0),
        int(getattr(pesquisa, "tokens_completion", 0) or 0),
        int(getattr(pesquisa, "tokens_total", 0) or 0),
    )
    novos = (
        int(total.get("input_tokens") or 0),
        int(total.get("output_tokens") or 0),
        int(total.get("total_tokens") or 0),
    )
    # Soma monotônica: o maior valor já persistido sobrevive a qualquer turno menor.
    finais = tuple(max(a, n) for a, n in zip(atuais, novos))
    if finais == atuais:
        return
    await repo.set_research_tokens(pesquisa_id, *finais)


async def persistir_busca(repo, pesquisa, workspace: Path) -> Dict[str, Any]:
    """Grava a coleta de cada persona em conteudo_coletado (idempotente)."""
    payload = search_payload(pesquisa.id_pesquisa, workspace)
    if not await repo.get_collected_content(pesquisa.id_pesquisa):
        resumo = payload["resumo_coletas"][0] if payload["resumo_coletas"] else None
        personas = resumo["personas"] if resumo else []
        urls_fonte = sanitizar_urls(u for p in personas for u in (p.get("urls_fonte") or []))
        lidas = {sanitizar_url_fonte(u) for p in personas for u in (p.get("urls_lidas") or [])}
        urls_lidas = sorted({u for u in lidas if u} | set(urls_fonte))
        conteudo = "\n\n".join(f"## {p['persona']}\n\n{p['analise']}" for p in personas)
        for ponto in await repo.list_points(pesquisa.id_pesquisa):
            await repo.save_collected_content(
                id_pesquisa=pesquisa.id_pesquisa,
                ponto_id=ponto.ponto_id,
                tema=pesquisa.tema,
                ponto=ponto.ponto,
                conteudo_coletado=conteudo,
                urls_lidas=urls_lidas,
                urls_fonte=urls_fonte,
                reasoning_coleta=None,
                status_ponto="coletado",
                metadados_coleta={
                    "personas": [p["persona"] for p in personas],
                    "tentativas": resumo["tentativas"] if resumo else 1,
                    "origem": "hermes-json",
                },
                invalidar_dossier=False,
                rodada=1,
            )
        await repo.update_pipeline_status(pesquisa.id_pesquisa, "coletado")
    await _aplicar_tokens(repo, pesquisa.id_pesquisa, workspace)
    return payload


async def persistir_auditoria(repo, pesquisa, workspace: Path) -> Dict[str, Any]:
    """Grava o veredito da última rodada nos pontos e no status da pesquisa."""
    payload = audit_payload(pesquisa.id_pesquisa, workspace)
    auditoria = payload["auditorias"][0] if payload["auditorias"] else {}
    aprovado = bool(payload["aprovados"])
    motivo = auditoria.get("pontos_fracos")
    for ponto in await repo.list_points(pesquisa.id_pesquisa):
        await repo.update_point_status(
            ponto.ponto_id,
            "aprovado" if aprovado else "reprovado",
            pontos_fracos=None if aprovado else (motivo or "auditoria reprovada"),
            incrementar_tentativa=True,
            reasoning_auditoria=auditoria.get("reasoning_auditoria"),
        )
    await repo.update_pipeline_status(pesquisa.id_pesquisa, "redigindo" if aprovado else "reprovado")
    await _aplicar_tokens(repo, pesquisa.id_pesquisa, workspace)
    return payload


async def persistir_dossie(repo, pesquisa, workspace: Path) -> Dict[str, Any]:
    """Grava o dossiê final e fecha a pesquisa como concluída."""
    payload = writer_payload(pesquisa.id_pesquisa, pesquisa.tema, workspace)
    if payload.get("dossier_final"):
        await repo.update_research_dossier(
            pesquisa.id_pesquisa,
            payload["dossier_final"],
            reasoning_dossier=payload.get("reasoning_dossier"),
        )
    await _aplicar_tokens(repo, pesquisa.id_pesquisa, workspace)
    return payload


def _artefato_usage(workspace: Path) -> Optional[Dict[str, Any]]:
    """`usage.json` do processo Hermes; ausente ou torto devolve None."""
    alvo = workspace / "usage.json"
    if not alvo.exists():
        return None
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    return dados if isinstance(dados, dict) else None


async def persistir_ciclo(pesquisa_id: str, workspace: Path) -> None:
    """Ao fim do ciclo, aplica tudo que existe em disco no banco. Nunca derruba a pesquisa."""
    from app.db.research_repository import ResearchRepository
    from app.db.session import get_sessionmaker

    try:
        async with get_sessionmaker()() as session:
            repo = ResearchRepository(session=session)
            pesquisa = await repo.get_research(pesquisa_id)
            if pesquisa is None:
                return
            await persistir_busca(repo, pesquisa, workspace)
            await persistir_auditoria(repo, pesquisa, workspace)
            await persistir_dossie(repo, pesquisa, workspace)

            # Consumo real do ciclo: o usage.json é a única fonte dos tokens gastos.
            await _aplicar_tokens(repo, pesquisa_id, workspace)
    except Exception as exc:
        print(f"[DR-PERSIST] {pesquisa_id}: {exc}", flush=True)


def meta_personas(workspace: Path) -> List[Dict[str, Any]]:
    """Resumo por persona lido dos JSON de busca."""
    return [
        {
            "persona": p["persona"],
            "tentativas": p["tentativas"],
            "urls": len(p["urls_fonte"]),
            "paginas_lidas": p["paginas_lidas"],
        }
        for p in busca_personas(workspace)
    ]


def relatorio(workspace: Path) -> Dict[str, Any]:
    """Inventário simples para diagnóstico (usado pelo endpoint e por testes)."""
    return {
        "arquivos": hermes_planner._inventario(workspace),
        "rodadas_auditoria": hermes_planner._conta_rodadas_auditoria(workspace),
        "urls_fora_do_acervo": hermes_planner._urls_fora_do_acervo(workspace),
    }


def estagio(workspace: Path) -> str:
    """Fase corrente derivada dos artefatos já gravados."""
    if (workspace / DOSSIE_ARQUIVO).exists():
        return "concluido"
    if (workspace / AUDITORIA_ARQUIVO).exists():
        return "auditando"
    buscas = sum(1 for nome in PERSONA_ARQUIVOS.values() if (workspace / nome).exists())
    if buscas:
        return f"buscando({buscas}/4)"
    if (workspace / PLANO_ARQUIVO).exists():
        return "planejado"
    return "iniciando"


def detalhe(pesquisa_id: str, obra: Path) -> Dict[str, Any]:
    """Payload de acompanhamento para a UI (polling): fase, plano, contratos."""
    plano = plan_payload(obra)
    return {
        "pesquisa_id": pesquisa_id,
        "diretorio": str(obra),
        "estagio": estagio(obra),
        "plano_valido": plano["valido"],
        "plano_erro": plano["erro"],
        "plano": plano["plano"],
        "metas_personas": meta_personas(obra),
        "rodadas_auditoria": hermes_planner._conta_rodadas_auditoria(obra),
        "arquivos": hermes_planner._inventario(obra),
        "urls_fora_do_acervo": hermes_planner._urls_fora_do_acervo(obra),
    }
