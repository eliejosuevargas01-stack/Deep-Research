#!/bin/sh
set -e
cd /root/projects/deep-research
docker rm -f deep-research-test >/dev/null 2>&1 || true
docker create --name deep-research-test --restart unless-stopped --network proxy -p 8020:8000 \
  --entrypoint uvicorn \
  -v /root/.hermes/projects/deep-research/test-data:/app/data \
  -v /root/.hermes/projects/deep-research/frontend/dist:/app/frontend/dist \
  --env-file .env \
  -e HOST=0.0.0.0 -e PORT=8000 \
  -e LLM_BASE_URL=http://9router:20128/v1 \
  -e LLM_MODEL_STRONG=ocg/deepseek-v4.1-flash -e LLM_MODEL_LIGHT=gemini/gemini-3.5-flash-lite \
  -e N_PONTOS=1 -e DR_MAX_RODADAS=1 -e DR_PLAN_TIMEOUT=420 -e TRUST_LOCAL_NETWORK=1 -e HERMES_ALLOW_ROOT_GATEWAY=1 \
  -e 'PERSONAS_CONFIG=planejador,historiador,visionario,cetico,futurista,auditor,redator final' \
  -e CALLBACK_WEBHOOK_URL= \
  -e DATABASE_URL=sqlite+aiosqlite:////app/data/deep_research.db \
  -e DR_HERMES_PESQUISAS_DIR=/app/data/pesquisas \
  -e DR_HERMES_PROFILE=deep-research -e HERMES_PROFILE=deep-research \
  -e HERMES_HOME=/app/hermes_home \
  -e JINA_API_KEY= -e JINA_BASE_URL= -e JINA_READER_BASE_URL= \
  "${IMAGE:-deep-research-api:v28}" app.main:app --host 0.0.0.0 --port 8000 >/dev/null
docker start deep-research-test >/dev/null
sleep 8
docker exec -u root deep-research-test chown -R 0:0 /app/hermes_home
curl -s -m 10 http://127.0.0.1:8020/health
echo
