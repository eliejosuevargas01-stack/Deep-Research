# Multi-stage build: etapa 1 compila o frontend React; etapa 2 provê runtime Python enxuto.
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Etapa 2: Runtime da aplicação FastAPI sem runtime Node.js
FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY --from=frontend-builder /frontend/dist ./frontend/dist

RUN pip install --no-cache-dir . && mkdir -p /app/data

# Bind local seguro por padrão em 127.0.0.1; portas configuráveis via HOST e PORT
ENV HOST=127.0.0.1
ENV PORT=8000

EXPOSE 8000

# Execução de produção do servidor FastAPI com bind local e variáveis configuráveis
CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-127.0.0.1} --port ${PORT:-8000}"]
