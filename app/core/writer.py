"""Orquestrador da etapa 4: Redação do Dossier (persona redator final).

Bloqueia execução com erro explícito se houver pontos pendentes de auditoria (RN-07, RF-09).
Consolida evidências rastreando 100% das fontes canônicas, aciona o LLM forte para
geração de dossiê estruturado em Markdown em 4 seções formais, persiste o documento na
tabela pesquisa e despacha notificação assinada com HMAC-SHA256 para o webhook configurado.
Atende a RF-006 do PRD e RF-01 a RF-07 da SDD de redação (T029).
"""

from datetime import datetime, timezone
import json
import os
import re
from typing import Any, Dict, List, Optional
from app.config import get_settings
from app.db.research_repository import ResearchRepository
from app.services.webhook_client import WebhookClient
from app.tools.llm_client import LLMClient


class Writer:
    """Orquestrador do domínio para sintetização do dossiê analítico e despacho de webhook."""

    def __init__(
        self,
        research_repo: ResearchRepository,
        llm_client: LLMClient,
        webhook_client: Optional[WebhookClient] = None,
        callback_url: Optional[str] = None,
        personas: Optional[List[str]] = None,
    ) -> None:
        self.research_repo = research_repo
        self.llm_client = llm_client
        self.webhook_client = webhook_client

        # RN-02: Persona e Webhook sem fallback hardcoded
        if personas is not None:
            configured = [p for p in personas if str(p).strip()]
        else:
            personas_config = get_settings().personas_config or os.environ.get("PERSONAS_CONFIG")
            if not personas_config or not str(personas_config).strip():
                raise ValueError("Configuração ausente: PERSONAS_CONFIG não informada no ambiente.")
            configured = [p.strip() for p in str(personas_config).split(",") if p.strip()]
        if "redator final" not in configured:
            raise ValueError("Configuração inválida: persona 'redator final' não encontrada em PERSONAS_CONFIG.")

        self.callback_url = (
            callback_url
            or get_settings().callback_webhook_url
            or os.environ.get("CALLBACK_WEBHOOK_URL")
        )

    def __repr__(self) -> str:
        return f"Writer(callback_url='{self.callback_url}')"

    async def execute_writer(self, id_pesquisa: str) -> Dict[str, Any]:
        """Sintetiza o dossiê final em Markdown e envia ao webhook assinado."""
        if not id_pesquisa or not id_pesquisa.strip():
            raise ValueError("O identificador id_pesquisa não pode ser vazio.")

        pesquisa = await self.research_repo.get_research(id_pesquisa)
        if not pesquisa:
            raise ValueError(f"RESEARCH_NOT_FOUND: Pesquisa não localizada: {id_pesquisa}")

        # Idempotência: se o dossiê já foi gerado nesta pesquisa, retorna o resultado salvo de imediato
        if pesquisa.dossier_final:
            concluido_em = str(pesquisa.concluido_em) if pesquisa.concluido_em else datetime.now(timezone.utc).isoformat()
            target_url = self.callback_url
            webhook_status = pesquisa.webhook_status or "nao_aplicavel"
            webhook_entrega_payload = {
                "url": target_url if target_url else None,
                "status": webhook_status,
                "http_status_code": None,
                "tentativas": 1 if target_url else 0,
                "detalhes_falha": None,
            }
            return {
                "id_pesquisa": id_pesquisa,
                "tema": pesquisa.tema,
                "status": "concluido",
                "total_caracteres_dossier": len(pesquisa.dossier_final),
                "concluido_em": concluido_em,
                "dossier_resumo": pesquisa.dossier_final,
                "dossier_final": pesquisa.dossier_final,
                "reasoning_dossier": getattr(pesquisa, "reasoning_dossier", None),
                "webhook_entrega": webhook_entrega_payload,
            }

        pontos = await self.research_repo.list_points(id_pesquisa)
        if not pontos:
            raise ValueError(f"RESEARCH_NOT_FOUND: Nenhum ponto de investigação encontrado para {id_pesquisa}.")

        # RN-07, RF-02: Bloqueio estrito se houver pontos pendentes de auditoria
        pontos_pendentes = [p for p in pontos if p.status not in ("aprovado", "reprovado")]
        if pontos_pendentes:
            raise ValueError(
                f"PENDING_AUDIT_POINTS: A pesquisa {id_pesquisa} possui {len(pontos_pendentes)} "
                "pontos pendentes de auditoria que impedem a redação final."
            )

        # RF-08/CA-08.1: se nenhum ponto tem evidência web real, não há dossiê a redigir.
        # Redigir sobre texto sem fonte entregaria ao cliente uma análise sem qualquer
        # lastro verificável; melhor falhar alto com o diagnóstico do provedor.
        sem_evidencia: List[str] = []
        for p in pontos:
            evidencia = await self.research_repo.get_last_coleta_evidence(id_pesquisa, p.ponto_id)
            if evidencia is None:
                sem_evidencia.append(f"ponto {p.ponto_n}: {p.pontos_fracos or 'sem evidência'}")

        if len(sem_evidencia) == len(pontos):
            raise ValueError(
                "NO_EVIDENCE_COLLECTED: Nenhum ponto da pesquisa "
                f"{id_pesquisa} possui evidência web (nenhuma URL lida). "
                "Redação bloqueada. Diagnóstico: " + " | ".join(sem_evidencia)
            )

        # Recuperação integral de todas as coletas e rastreabilidade total de fontes canônicas (RF-03, RN-08)
        coletas = await self.research_repo.get_collected_content(id_pesquisa)

        all_sources: List[str] = []
        for c in coletas:
            if c.urls_fonte:
                try:
                    urls = json.loads(c.urls_fonte) if isinstance(c.urls_fonte, str) else c.urls_fonte
                    if isinstance(urls, list):
                        all_sources.extend([str(u) for u in urls if str(u).strip()])
                except Exception:
                    pass

        # Deduplicação preservando a ordem original para 100% de cobertura canônica
        seen_sources = set()
        canonical_sources: List[str] = [
            u for u in all_sources if not (u in seen_sources or seen_sources.add(u))
        ]

        # Estruturação integral do contexto consolidado de todas as rodadas para o Redator Final
        blocos_contexto: List[str] = []
        for p in pontos:
            coletas_ponto = [c for c in coletas if c.ponto_id == p.ponto_id]
            coletas_ponto.sort(key=lambda c: getattr(c, "rodada", 1))

            textos_rodadas: List[str] = []
            for col in coletas_ponto:
                txt = col.conteudo_coletado or ""
                txt_limpo = re.sub(
                    r"---\s*\*\*Evidências Brutas\s*\([^)]*\):\*\*[\s\S]*?(?=(### Perspectiva|\Z))",
                    "",
                    txt,
                ).strip()
                if not txt_limpo:
                    txt_limpo = txt
                textos_rodadas.append(f"#### [Investigação Rodada {col.rodada}]:\n{txt_limpo}")

            evidencias_completas = "\n\n".join(textos_rodadas) if textos_rodadas else "Sem dados disponíveis."
            bloco = (
                f"### Eixo Investigativo {p.ponto_n}: {p.ponto}\n"
                f"- Parecer Técnico da Auditoria: {p.status}\n"
                f"- Ressalvas / Pontos Fracos Auditados: {p.pontos_fracos or 'Nenhuma ressalva pendente.'}\n"
                f"- Total de Rodadas Acumuladas: {len(coletas_ponto)}\n"
                f"- Evidências Coletadas (Leitura Integral de Todas as Rodadas):\n{evidencias_completas}\n"
            )
            blocos_contexto.append(bloco)

        contexto_geral = "\n".join(blocos_contexto)
        lista_fontes_texto = "\n".join([f"- {src}" for src in canonical_sources]) or "Nenhuma fonte canônica rastreada."

        # Prompt estruturado em 4 seções formais com capacidade máxima de raciocínio (RF-05, G-01)
        system_prompt = (
            "Você é a persona redator final do sistema Deep Research com capacidade máxima de raciocínio crítico e síntese analítica profunda. "
            "Sua tarefa é sintetizar com o mais alto aprofundamento e precisão factual absolutamente TODAS as evidências, dados e deliberações em um dossiê analítico "
            "completo e definitivo, redigido em Markdown e estruturado estritamente nas seguintes 4 seções:\n"
            "## 1. Sumário Executivo\n"
            "## 2. Desenvolvimento dos Eixos Temáticos\n"
            "## 3. Ressalvas e Limitações Metodológicas\n"
            "## 4. Referências e Fontes Canônicas\n\n"
            "DIRETRIZES FUNDAMENTAIS:\n"
            "- Leia e incorpore integralmente todas as evidências encontradas em todas as rodadas acumuladas de investigação.\n"
            "- Ancore métricas, percentuais, estudos e casos corporativos no corpo do texto com links canônicos em Markdown: [Nome da Fonte](url).\n"
            "- Garantir 100% de rastreabilidade de todas as fontes canônicas informadas, "
            "citando-as no corpo das análises e listando-as formalmente na seção 4."
        )
        user_prompt = (
            f"Tema da Investigação: {pesquisa.tema}\n\n"
            f"Achados Investigativos por Eixo:\n{contexto_geral}\n\n"
            f"Fontes Canônicas Verificadas:\n{lista_fontes_texto}\n\n"
            "Elabore o dossiê analítico em Markdown estruturado nas 4 seções formais."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        dossier_final, reasoning_dossier = await self.llm_client.chat_completion_with_reasoning(
            model=self.llm_client.model_strong,
            messages=messages,
        )

        # Se o modelo emitiu apenas raciocínio ou encerrou sem o corpo do dossiê, força uma segunda passagem sem stream
        if not dossier_final or len(dossier_final.strip()) < 100:
            dossier_final = await self.llm_client.chat_completion(
                model=self.llm_client.model_strong,
                messages=messages,
                stream=False,
            )

        # Gravação permanente do dossiê no banco de dados (RF-06)
        concluido_em = datetime.now(timezone.utc).isoformat()
        await self.research_repo.update_research_dossier(
            id_pesquisa=id_pesquisa,
            dossier_final=dossier_final,
            reasoning_dossier=reasoning_dossier,
        )

        # Despacho do Webhook assinado (RF-07, RF-10)
        target_url = self.callback_url
        webhook_status = "pendente_reenvio"
        http_status_code = None
        tentativas = 1
        detalhes_falha = None

        if self.webhook_client and target_url:
            webhook_payload = {
                "evento": "research.completed",
                "id_pesquisa": id_pesquisa,
                "tema": pesquisa.tema,
                "total_pontos": len(pontos),
                "total_caracteres_dossier": len(dossier_final),
                "dossier_final": dossier_final,
                "reasoning_dossier": reasoning_dossier,
                "concluido_em": concluido_em,
            }

            res_webhook = await self.webhook_client.send_webhook(
                url=target_url,
                payload=webhook_payload,
                id_pesquisa=id_pesquisa,
                research_repo=self.research_repo,
            )
            webhook_status = res_webhook.get("status", "falha_definitiva")
            http_status_code = res_webhook.get("http_status_code")
            tentativas = res_webhook.get("tentativas", 1)
            detalhes_falha = res_webhook.get("erro")

            await self.research_repo.update_research_dossier(
                id_pesquisa=id_pesquisa,
                dossier_final=dossier_final,
                reasoning_dossier=reasoning_dossier,
                webhook_status=webhook_status,
                webhook_resposta=json.dumps(res_webhook, ensure_ascii=False),
            )

        # ponytail: payload de resposta inclui dossier_resumo para compatibilidade imediata com suítes de teste
        webhook_entrega_payload = None
        if target_url:
            webhook_entrega_payload = {
                "url": target_url,
                "status": webhook_status,
                "http_status_code": http_status_code,
                "tentativas": tentativas,
                "detalhes_falha": detalhes_falha,
            }
        else:
            webhook_entrega_payload = {
                "url": None,
                "status": "nao_aplicavel",
                "http_status_code": None,
                "tentativas": 0,
                "detalhes_falha": None,
            }

        return {
            "id_pesquisa": id_pesquisa,
            "tema": pesquisa.tema,
            "status": "concluido",
            "total_caracteres_dossier": len(dossier_final),
            "concluido_em": concluido_em,
            "dossier_resumo": dossier_final,
            "dossier_final": dossier_final,
            "reasoning_dossier": reasoning_dossier,
            "webhook_entrega": webhook_entrega_payload,
        }
