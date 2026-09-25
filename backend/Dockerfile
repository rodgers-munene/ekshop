FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# psycopg (non-binary) needs a C toolchain and libpq headers
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Gunicorn + Uvicorn workers. Each worker loads the Kenya boundary layers
# (about 100 MB; a worker uses roughly 250 MB in all), so size WORKERS to the
# instance: docker run -e WORKERS=1 ...
ENV WORKERS=2
CMD exec gunicorn app.main:app --workers "$WORKERS" --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 --timeout 120 --keep-alive 5 --max-requests 1000 --max-requests-jitter 50
