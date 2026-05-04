# CasaQuant Unified — Dockerfile
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installer les dépendances en premier (cache Docker)
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install -e ".[dev]"

# Installer Playwright (binaire chromium)
RUN playwright install chromium && playwright install-deps chromium

# Copier le code applicatif
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Créer le dossier de données
RUN mkdir -p /app/data

EXPOSE 8000

# Stage de production
FROM base AS production
ENV CASAQUANT_ENV=production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Stage de développement (hot-reload)
FROM base AS development
ENV CASAQUANT_ENV=development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
