FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir . && mkdir -p /app/data

EXPOSE 8000

# Sem --reload: container de produção. DATABASE_URL aponta para volume persistente.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
