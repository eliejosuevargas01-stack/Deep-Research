"""Orquestrador da etapa 3: Auditoria de Qualidade (persona auditor).

Avalia o conteúdo coletado contra o checklist das 12 perguntas de qualidade via LLM forte,
sintetizando o histórico incremental de coletas por rodada, deliberando entre 'aprovado' e 'reprovado'
com base no índice mínimo de 85% de conformidade, identificando lacunas em 'pontos_fracos' (máx 3 reprovações)
e atualizando a tabela relacional de pontos sem perda de informações históricas.
Atende a RF-005 do PRD e RF-01 a RF-07 da SDD de auditoria (T028).
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
from app.config import get_settings
from app.db.models import Ponto
from app.db.research_repository import ResearchRepository
from app.tools.llm_client import LLMClient


class Auditor:
    """Orquestrador do domínio para auditoria de qualidade analítica com o LLM forte."""

    def __init__(
        self,
        research_repo: ResearchRepository,
        llm_client: LLMClient,
        persona_prompt: Optional[str] = None,
        personas: Optional[List[str]] = None,
    ) -> None:
        self.research_repo = research_repo
        self.llm_client = llm_client

        # RN-02: Persona sem fallback hardcoded
        if persona_prompt:
            self.persona_prompt = persona_prompt
        elif personas is not None and len(personas) > 0:
            if "auditor" not in personas:
                raise ValueError("Configuração inválida: persona 'auditor' não encontrada em PERSONAS_CONFIG.")
            self.persona_prompt = "Você é a persona auditor com rigor metodológico, objetividade e ceticismo analítico."
        else:
            personas_config = get_settings().personas_config or os.environ.get("PERSONAS_CONFIG")
            if not personas_config or not str(personas_config).strip():
                raise ValueError("Configuração ausente: PERSONAS_CONFIG não informada no ambiente.")
            configured = [p.strip() for p in str(personas_config).split(",") if p.strip()]
            if "auditor" not in configured:
                raise ValueError("Configuração inválida: persona 'auditor' não encontrada em PERSONAS_CONFIG.")
            self.persona_prompt = "Você é a persona auditor com rigor metodológico, objetividade e ceticismo analítico."

    def __repr__(self) -> str:
        return "Auditor(persona='auditor')"

    async def execute_audit(self, id_pesquisa: str) -> Dict[str, Any]:
        """Executa a auditoria analítica dos pontos coletados frente às 12 perguntas de qualidade."""
        if not id_pesquisa or not id_pesquisa.strip():
            raise ValueError("O identificador id_pesquisa não pode ser vazio.")

        pesquisa = await self.research_repo.get_research(id_pesquisa)
        if not pesquisa:
            raise ValueError(f"RESEARCH_NOT_FOUND: Pesquisa não localizada: {id_pesquisa}")

        todas_coletas = await self.research_repo.get_collected_content(id_pesquisa)
        if not todas_coletas:
            raise ValueError(
                f"SEARCH_NOT_COMPLETED: A pesquisa {id_pesquisa} não possui conteúdo coletado para auditoria."
            )

        pontos = await self.research_repo.list_points(id_pesquisa)
        if not pontos:
            raise ValueError(f"RESEARCH_NOT_FOUND: Nenhum ponto localizado para a pesquisa: {id_pesquisa}")

        auditorias: List[Dict[str, Any]] = []

        for ponto in pontos:
            # Resgata todas as coletas históricas registradas para este ponto específico (rodadas 1, 2, 3...)
            coletas_ponto = await self.research_repo.get_collected_content_for_point(id_pesquisa, ponto.ponto_id)

            # RF-07/CA-07.1: reprovacao deterministica sem chamada ao LLM quando nenhuma
            # rodada do ponto possui evidencia web real (zero URLs lidas). Texto analitico
            # volumoso nao reabilita ponto sem fonte (CA-07.2), entao a deliberacao e feita
            # antes de gastar tokens e sem risco de aprovacao indevida.
            evidencia = await self.research_repo.get_last_coleta_evidence(id_pesquisa, ponto.ponto_id)

            if evidencia is None:
                status = "reprovado"
                if not coletas_ponto:
                    pontos_fracos = "Nenhum conteúdo coletado encontrado para este ponto investigativo."
                else:
                    pontos_fracos = (
                        f"Reprovado sem análise de conteúdo: nenhuma das {len(coletas_ponto)} rodada(s) "
                        "de coleta deste ponto leu alguma URL. Sem fonte web verificável não há o que auditar. "
                        "Diagnóstico da coleta: "
                        f"{(ponto.pontos_fracos or 'falha de provedor não catalogada')}"
                    )
                resumo_auditoria = (
                    "Reprovado deterministicamente por ausência total de evidência web."
                )
                reasoning_audit = None
            else:
                # Sintetiza todas as coletas do histórico de forma 100% integral para o auditor
                blocos_sintetizados: List[str] = []
                todas_fontes: List[str] = []

                coletas_ordenadas = sorted(coletas_ponto, key=lambda c: getattr(c, "rodada", 1))

                for col in coletas_ordenadas:
                    txt = col.conteudo_coletado or ""
                    # Remove apenas eventuais cascas brutas de html residual se existirem, mantendo toda a substância
                    txt_limpo = re.sub(
                        r"---\s*\*\*Evidências Brutas\s*\([^)]*\):\*\*[\s\S]*?(?=(### Perspectiva|\Z))",
                        "",
                        txt,
                    ).strip()
                    if not txt_limpo:
                        txt_limpo = txt

                    rotulo = f"### [Investigação Completa - Rodada {col.rodada}]"
                    blocos_sintetizados.append(f"{rotulo}\n\n{txt_limpo}")
                    try:
                        fontes = json.loads(col.urls_fonte) if isinstance(col.urls_fonte, str) else col.urls_fonte
                        if isinstance(fontes, list):
                            todas_fontes.extend(fontes)
                    except Exception:
                        pass

                conteudo_unificado = "\n\n====================\n\n".join(blocos_sintetizados)
                fontes_dedup = list(dict.fromkeys(todas_fontes))

                # Checklist formal das 12 perguntas de qualidade com sarrafo de 85%
                system_prompt = (
                    f"{self.persona_prompt}\n\n"
                    "Avalie o conteúdo coletado consolidado contra o checklist formal das 12 perguntas de qualidade:\n"
                    "1. Clareza temática (aborda a questão com objetividade?)\n"
                    "2. Corroboração canônica (há fontes primárias verificáveis?)\n"
                    "3. Atualidade temporal (marcos vigentes e precisos?)\n"
                    "4. Ausência de contradições internas\n"
                    "5. Embasamento factual e empírico\n"
                    "6. Aderência estrita ao escopo do plano\n"
                    "7. Profundidade analítica para tomada de decisão\n"
                    "8. Precisão de dados e métricas citadas\n"
                    "9. Neutralidade e equilíbrio de tom\n"
                    "10. Densidade satisfatória de evidências\n"
                    "11. Declaração explícita de incertezas e lacunas\n"
                    "12. Solidez lógica entre premissas e conclusões.\n\n"
                    "CLARIFICAÇÃO METODOLÓGICA DAS 4 PERSONAS:\n"
                    "- As 4 personas (Historiador, Visionário, Cético e Futurista) são lentes complementares e deliberadamente divergentes por design.\n"
                    "- Divergências de tom, ênfase interpretativa ou projeções entre as personas são esperadas e desejáveis. NÃO as considere como 'contradição interna', desde que os dados citados sejam ancorados.\n"
                    "- Ancoragem factual: avalie se os dados e métricas possuem referência canônica direta.\n\n"
                    "DIRETRIZ DE APROVAÇÃO (85% MÍNIMO):\n"
                    "- Calcule uma pontuação percentual de conformidade de 0% a 100%.\n"
                    "- Para deliberar 'aprovado', o conteúdo deve atingir no mínimo 85% de conformidade com os critérios.\n"
                    "- Caso atinja menos de 85%, delibere estritamente como 'reprovado'.\n"
                    "- Em caso de reprovação, indique de forma concisa e direta os 'pontos_fracos' (as lacunas exatas a pesquisar).\n\n"
                    "Responda estritamente em JSON conciso com as chaves:\n"
                    "- 'status': 'aprovado' ou 'reprovado'\n"
                    "- 'pontuacao_percentual': número de 0 a 100\n"
                    "- 'pontos_fracos': texto sucinto com as lacunas faltantes (ou null se aprovado)\n"
                    "- 'resumo_auditoria': síntese executiva do parecer em até 3 frases"
                )
                user_prompt = (
                    f"Tema Geral: {ponto.tema}\n"
                    f"Ponto Investigativo {ponto.ponto_n}: {ponto.ponto}\n"
                    f"Total de Rodadas de Coleta Acumuladas: {len(coletas_ponto)}\n\n"
                    f"Conteúdo Consolidado das Rodadas:\n{conteudo_unificado}\n\n"
                    f"Fontes Canônicas Informadas ({len(fontes_dedup)} URLs):\n{fontes_dedup[:30]}\n\n"
                    "Execute a auditoria técnica e emita seu parecer estruturado em JSON."
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]

                parsed_tuple = await self.llm_client.generate_json(
                    model_type="strong",
                    messages=messages,
                    return_reasoning=True,
                )
                parsed, reasoning_audit = parsed_tuple if isinstance(parsed_tuple, tuple) else (parsed_tuple, None)

                status_raw = str(parsed.get("status", "reprovado")).strip().lower()
                status = "aprovado" if status_raw == "aprovado" else "reprovado"

                # Verifica conformidade com o mínimo de 85%
                pontuacao = parsed.get("pontuacao_percentual")
                if pontuacao is not None:
                    try:
                        if float(pontuacao) < 85.0:
                            status = "reprovado"
                    except (ValueError, TypeError):
                        pass

                pontos_fracos_raw = parsed.get("pontos_fracos")
                if status == "reprovado" and not pontos_fracos_raw:
                    pontos_fracos = "Insuficiência em critérios de qualidade (menos de 85% de conformidade)."
                elif isinstance(pontos_fracos_raw, list):
                    pontos_fracos = "\n".join(f"- {item}" for item in pontos_fracos_raw)
                elif isinstance(pontos_fracos_raw, dict):
                    pontos_fracos = json.dumps(pontos_fracos_raw, ensure_ascii=False)
                else:
                    pontos_fracos = str(pontos_fracos_raw) if pontos_fracos_raw else None

                resumo_auditoria = str(parsed.get("resumo_auditoria", ""))

                # Verificação de limite máximo de 3 reprovações
                tentativas_atuais = (ponto.tentativas_auditoria or 0) + 1
                if status == "reprovado" and tentativas_atuais >= 3:
                    resumo_auditoria = f"[Limite máximo de 3 reprovações atingido] {resumo_auditoria}".strip()

            # Persistência relacional do parecer (RF-06) sem quebra de tipos e com incremento de tentativa
            await self.research_repo.update_point_status(
                ponto_id=ponto.ponto_id,
                status=status,
                pontos_fracos=pontos_fracos,
                incrementar_tentativa=True,
                reasoning_auditoria=reasoning_audit,
            )

            auditorias.append({
                "ponto_id": ponto.ponto_id,
                "ponto_n": ponto.ponto_n,
                "status": status,
                "pontos_fracos": pontos_fracos,
                "reasoning_auditoria": reasoning_audit,
                "resumo_auditoria": resumo_auditoria,
            })

        aprovados = sum(1 for a in auditorias if a["status"] == "aprovado")
        reprovados = sum(1 for a in auditorias if a["status"] == "reprovado")

        return {
            "id_pesquisa": id_pesquisa,
            "total_pontos": len(auditorias),
            "aprovados": aprovados,
            "reprovados": reprovados,
            "status_geral": "auditado",
            "auditorias": auditorias,
        }
