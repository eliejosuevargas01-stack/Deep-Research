import json
from pathlib import Path
from typing import Any

PERSONA_NAMES: tuple[str, ...] = ("historian", "skeptic", "pragmatist", "futurist")

_PERSONA_PROMPT_KEYS: dict[str, str] = {
    "historian": "historian_prompt",
    "skeptic": "skeptic_prompt",
    "pragmatist": "pragmatist_prompt",
    "futurist": "futurist_prompt",
}


def load_persona_prompts(
    prompts_path: str | Path = "app/prompts/personas.json",
) -> dict[str, str]:
    """Carrega app/prompts/personas.json e mapeia as 4 personas para seus prompts base."""
    path = Path(prompts_path)
    if not path.is_absolute():
        # Fallback para resolver relativo a raiz do projeto ou cwd
        if not path.exists():
            root_path = Path(__file__).resolve().parents[2] / path
            if root_path.exists():
                path = root_path

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    persona_prompts: dict[str, str] = {}
    for persona, prompt_key in _PERSONA_PROMPT_KEYS.items():
        if prompt_key not in data:
            raise KeyError(
                f"Chave '{prompt_key}' para persona '{persona}' não encontrada em {path}"
            )
        persona_prompts[persona] = data[prompt_key]

    return persona_prompts


def build_persona_system_prompt(
    persona: str,
    step_title: str,
    research_theme: str | None = None,
    prompts_path: str | Path = "app/prompts/personas.json",
) -> str:
    """Constrói o system prompt instruindo o papel cognitivo da persona, uso de ferramentas,
    citação e formato de saída JSON estrito.
    """
    if persona not in PERSONA_NAMES:
        raise ValueError(
            f"Persona desconhecida: '{persona}'. Personas válidas: {PERSONA_NAMES}"
        )

    prompts = load_persona_prompts(prompts_path)
    base_prompt = prompts[persona]

    theme_context = (
        f"Tema Geral de Pesquisa: {research_theme}\n" if research_theme else ""
    )

    system_prompt = f"""{base_prompt}

{theme_context}Ponto Específico de Investigação: {step_title}

Instruções Operacionais Obrigatórias:
1. Ferramenta de Busca: Você deve utilizar a ferramenta 'jina_search' para pesquisar na web informações relevantes sobre o ponto específico. Você pode realizar no máximo 3 buscas.
2. Parada Voluntária: Você tem autonomia para encerrar suas pesquisas a qualquer momento assim que julgar ter obtido evidências suficientes.
3. Citação Factual Estrita: Baseie suas análises rigorosamente nas fontes encontradas via 'jina_search'. Utilize citação direta/verbatim dos fatos e dados extraídos das páginas lidas.
4. Formato de Saída Final: Sua resposta final DEVE ser estritamente um único objeto JSON válido, sem texto explicativo adicional, markdown ou blocos fora do JSON, obedecendo ao seguinte formato:
{{
  "result": "<texto analítico detalhado integrando as evidências encontradas e a perspectiva da persona>",
  "used_urls": ["<url1>", "<url2>"]
}}
"""
    return system_prompt.strip()


def get_model_for_persona(
    persona: str,
    app_settings_models: dict[str, Any] | None = None,
) -> str:
    """Retorna o modelo de LLM configurado para a persona com fallbacks:
    1. app_settings_models[persona] (se string não-vazia)
    2. app_settings_models["scout"] (se string não-vazia)
    3. Fallback padrão final: "openai/implement"
    """
    if app_settings_models and isinstance(app_settings_models, dict):
        persona_model = app_settings_models.get(persona)
        if isinstance(persona_model, str) and persona_model.strip():
            return persona_model.strip()

        scout_model = app_settings_models.get("scout")
        if isinstance(scout_model, str) and scout_model.strip():
            return scout_model.strip()

    return "openai/implement"
