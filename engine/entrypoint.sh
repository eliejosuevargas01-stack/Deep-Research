#!/bin/sh
# Renderiza $HERMES_HOME/profiles/deep-research/config.yaml a partir de env.
# Segredos (base_url/api_key) nunca entram no arquivo: o provider `custom`
# do Hermes lê OPENAI_BASE_URL/OPENAI_API_KEY do ambiente.
set -eu

HERMES_HOME="${HERMES_HOME:-/opt/data}"
PERFIL="$HERMES_HOME/profiles/deep-research"
PLUGIN="$HERMES_HOME/plugins/delegation/por_papel"
MODELO="${LLM_MODEL:-${DR_ENGINE_MODEL:-ocg/deepseek-v4.1-flash}}"
FORTE="${MODELO_FORTE_PADRAO:-ocg/deepseek-v4.1-flash}"
LEVE="${MODELO_LEVE_PADRAO:-gemini/gemini-3.5-flash-lite}"
BASE_URL="${LLM_BASE_URL:-}"
CHAVE="${LLM_API_KEY:-}"

esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

modelo_do_papel() {
  # Fallback explícito por papel: variável vazia nunca herda o forte.
  case "$1" in
    PLANNER) _m="${LLM_MODEL_PLANNER:-}" ; [ -n "$_m" ] || _m="${LLM_MODEL:-}" ; [ -n "$_m" ] || _m="$FORTE" ;;
    HISTORIADOR) _m="${LLM_MODEL_HISTORIADOR:-}" ; [ -n "$_m" ] || _m="$LEVE" ;;
    CETICO) _m="${LLM_MODEL_CETICO:-}" ; [ -n "$_m" ] || _m="$LEVE" ;;
    VISIONARIO) _m="${LLM_MODEL_VISIONARIO:-}" ; [ -n "$_m" ] || _m="$LEVE" ;;
    FUTURISTA) _m="${LLM_MODEL_FUTURISTA:-}" ; [ -n "$_m" ] || _m="$LEVE" ;;
    AUDITOR) _m="${LLM_MODEL_AUDITOR:-}" ; [ -n "$_m" ] || _m="$FORTE" ;;
    REDATOR) _m="${LLM_MODEL_REDATOR:-}" ; [ -n "$_m" ] || _m="$FORTE" ;;
    *) _m="$LEVE" ;;
  esac
  printf '%s' "$_m"
}

mkdir -p "$PERFIL" "$PLUGIN" /workspaces

# Semeia SOUL.md e plugin vindos da imagem quando o volume está vazio.
[ -f "$PERFIL/SOUL.md" ] || cp -r /app/seed/profile/. "$PERFIL/" 2>/dev/null || true
# O loader de plugins de usuário procura $HERMES_HOME/plugins/<nome>; o caminho
# aninhado em delegation/ é o do plugin bundled.
for destino in "$HERMES_HOME/plugins/por_papel" "$HERMES_HOME/plugins/delegation/por_papel"; do
  mkdir -p "$destino"
  [ -f "$destino/__init__.py" ] || cp -r /app/seed/plugin/. "$destino/" 2>/dev/null || true
done

{
  printf 'model:\n  default: "%s"\n  provider: env\n' "$(esc "$MODELO")"
  printf 'providers:\n  env:\n    name: env\n    base_url: "%s"\n    key_env: LLM_API_KEY\n    model: "%s"\n' "$(esc "$BASE_URL")" "$(esc "$MODELO")"
  printf 'delegation:\n  backend: por_papel\n  max_concurrent_children: 40\n  max_spawn_depth: 2\n  oneshot_max_children: 0\n  backends:\n    por_papel:\n      modelos:\n'
  # ponytail: teto em 7 papéis do plugin por_papel; novo papel exige
  # LLM_MODEL_<PAPEL> aqui + entrada no plugin + service.py/PAPEIS.
  for p in PLANNER HISTORIADOR CETICO VISIONARIO FUTURISTA AUDITOR REDATOR; do
    minus=$(printf '%s' "$p" | tr 'A-Z' 'a-z')
    printf '        %s: "%s"\n' "$minus" "$(esc "$(modelo_do_papel "$p")")"
  done
  printf 'plugins:\n  enabled: [por_papel]\nagent:\n  disabled_toolsets: [terminal, browser, computer_use, code_execution, cronjob, session_search]\n'
} > "$PERFIL/config.yaml.tmp"
mv "$PERFIL/config.yaml.tmp" "$PERFIL/config.yaml"

export OPENAI_BASE_URL="$BASE_URL"
export OPENAI_API_KEY="$CHAVE"
# O Hermes resolve `key_env` pelo cofre de segredos do perfil (`.env`), não pelo
# env do processo. Grava só dentro do container/volume, nunca no repositório.
if [ -n "$CHAVE" ]; then
  for alvo in "$HERMES_HOME/.env" "$PERFIL/.env"; do
    mkdir -p "$(dirname "$alvo")"
    touch "$alvo"
    grep -v '^LLM_API_KEY=' "$alvo" > "$alvo.tmp" 2>/dev/null || true
    printf 'LLM_API_KEY=%s\n' "$CHAVE" >> "$alvo.tmp"
    mv "$alvo.tmp" "$alvo"
    chmod 600 "$alvo" 2>/dev/null || true
  done
fi
if [ "$(id -u)" = "0" ]; then
  export HERMES_ALLOW_ROOT_GATEWAY=1
fi
export PYTHONPATH=/app/engine
export PATH="/opt/hermes/bin:$PATH"
export HERMES_WRITE_SAFE_ROOT="/workspaces:/opt/data"
cd /app/engine
exec /opt/hermes/.venv/bin/python -m uvicorn service:app --host 0.0.0.0 --port 8100
