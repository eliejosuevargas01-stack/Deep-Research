"""Orquestrador da etapa 1: Plano de Investigação (persona planejador).

Formulam-se queries exploratórias, consultam-se exclusivamente metadados da SERP
(sem download do corpo das páginas), geram-se exatamente N pontos focais via LLM
e persistem-se a pesquisa e seus pontos com status 'pendente'.
Atende a RF-001, RF-002 do PRD e RF-01 a RF-06 da SDD de planejamento (T026).
"""

import os
from typing import Any, Dict, List, Optional
from app.config import get_settings
from app.db.models import Pesquisa
from app.db.research_repository import ResearchRepository
from app.tools.jina_client import JinaClient
from app.tools.llm_client import LLMClient


class Planner:
    """Orquestrador do domínio para formulação de plano investigativo."""

    def __init__(
        self,
        research_repo: ResearchRepository,
        jina_client: JinaClient,
        llm_client: LLMClient,
        n_pontos: Optional[int] = None,
        personas: Optional[List[str]] = None,
    ) -> None:
        self.research_repo = research_repo
        self.jina_client = jina_client
        self.llm_client = llm_client

        # RN-02: N_PONTOS estritamente via ambiente ou parâmetro explícito, sem fallback hardcoded
        resolved_n = n_pontos
        if resolved_n is None:
            settings = get_settings()
            resolved_n = settings.n_pontos or os.environ.get("N_PONTOS")

        if resolved_n is None:
            raise ValueError("Configuração ausente: N_PONTOS deve ser definida via ambiente ou banco.")

        try:
            self.n_pontos = int(resolved_n)
            if self.n_pontos <= 0:
                raise ValueError("N_PONTOS deve ser um número inteiro positivo.")
        except (TypeError, ValueError) as exc:
            raise ValueError("Configuração ausente: N_PONTOS deve ser definida via ambiente ou banco.") from exc

        # RN-02: Personas do sistema sem fallback hardcoded
        if personas is not None:
            self.personas = [p.strip() for p in personas if str(p).strip()]
        else:
            personas_config = get_settings().personas_config or os.environ.get("PERSONAS_CONFIG")
            if not personas_config or not str(personas_config).strip():
                raise ValueError("Configuração ausente: PERSONAS_CONFIG não informada no ambiente.")
            self.personas = [p.strip() for p in str(personas_config).split(",") if p.strip()]

        if "planejador" not in self.personas:
            raise ValueError("Configuração inválida: persona 'planejador' não encontrada em PERSONAS_CONFIG.")

    def __repr__(self) -> str:
        return f"Planner(n_pontos={self.n_pontos})"

    async def execute_plan(
        self,
        tema: str,
        id_pesquisa: Optional[str] = None,
    ) -> Pesquisa:
        """Executa a formulação do plano investigativo com metadados SERP e inferência LLM."""
        if not tema or not tema.strip():
            raise ValueError("O tema da pesquisa não pode ser vazio.")
        tema_limpo = tema.strip()
        if len(tema_limpo) < 5:
            raise ValueError("O tema deve conter no mínimo 5 caracteres.")
        if len(tema_limpo) > 500:
            raise ValueError("O tema deve conter no máximo 500 caracteres.")

        # Consulta exclusiva a metadados da SERP (RN-03, vedado scraper de páginas no plano)
        serp_results = await self.jina_client.search(query=tema_limpo)
        snippets: List[str] = []
        for item in serp_results:
            t = item.get("title", "")
            u = item.get("url", "")
            d = item.get("description", "")
            snippets.append(f"- Título: {t}\n  URL: {u}\n  Resumo: {d}")
        serp_context = "\n".join(snippets)

        # Invocação da persona planejador com geração estruturada em JSON
        system_prompt = (
            "Você é a persona planejador do sistema Deep Research. "
            f"Sua missão é decompor o tema em exatamente {self.n_pontos} pontos focais de investigação, "
            "com relevância analítica, baseando-se estritamente nos metadados da SERP fornecidos. "
            "Responda estritamente em formato JSON com a chave 'pontos', contendo uma lista de strings "
            f"com exatamente {self.n_pontos} itens investigativos detalhados."
        )
        user_prompt = (
            f"Tema da Investigação: {tema_limpo}\n\n"
            f"Metadados Exploratórios da SERP:\n{serp_context}\n\n"
            f"Formule exatamente {self.n_pontos} pontos de investigação em JSON sob a chave 'pontos'."
        )
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        res_json = await self.llm_client.generate_json(
            model_type="light",
            messages=messages,
            return_reasoning=True,
        )
        parsed, reasoning = res_json if isinstance(res_json, tuple) else (res_json, None)
        pontos_raw = parsed.get("pontos", [])
        if not isinstance(pontos_raw, list):
            raise ValueError("Formato de resposta inválido do LLM: 'pontos' deve ser uma lista.")

        pontos = [str(p).strip() for p in pontos_raw if str(p).strip()]

        # Validação quantitativa estrita (G-01, RF-05)
        if len(pontos) != self.n_pontos:
            raise ValueError(
                f"O modelo gerou {len(pontos)} pontos, mas eram esperados exatamente {self.n_pontos}."
            )

        # ponytail: persistência atômica no SQLite; se id_pesquisa já existir, reaproveita sem duplicar raiz
        pesquisa = await self.research_repo.create_research(
            tema=tema_limpo,
            pontos_textos=pontos,
            id_pesquisa=id_pesquisa,
            reasoning_planejamento=reasoning,
        )
        return pesquisa
