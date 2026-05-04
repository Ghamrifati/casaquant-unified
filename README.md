# CasaQuant Unified v3.0

Application unifiée d'analyse quantitative pour la Bourse de Casablanca (BVC/MASI).

## Architecture

- **Monolithe modulaire** : FastAPI + SQLModel + Celery + Redis + PostgreSQL
- **Frontend** : Vanilla ES6/CSS3 servi par FastAPI (`static/`)
- **IA** : Ollama local via gateway résilient (circuit breaker, retry, backoff)
- **Scraping** : Celery Beat + Workers (Playwright fallback)
- **Base de données** : PostgreSQL (production) ou SQLite WAL (offline)

## Démarrage rapide

### Prérequis

- Python 3.12+
- Docker & Docker Compose (recommandé)
- Ollama (local ou via Docker)

### Mode Docker Compose (recommandé)

```bash
cp .env.example .env
# Éditer .env si nécessaire

docker compose up -d
```

L'API est accessible sur `http://localhost:8000`.

### Mode développement (local Python)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Base SQLite
export DATABASE_URL=sqlite:///data/casaquant.db

# Démarrer API
uvicorn app.main:app --reload --port 8000

# Démarrer worker (dans un autre terminal)
celery -A app.domains.scraping.tasks worker -l info

# Démarrer scheduler (dans un autre terminal)
celery -A app.domains.scraping.tasks beat -l info
```

## Structure

```
casaquant_unified/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Pydantic settings
│   ├── dependencies.py      # DI (DB session)
│   ├── static/              # Frontend vanilla
│   └── domains/
│       ├── common/          # DB, fees, exceptions
│       ├── market/          # Tickers, OHLCV, snapshots
│       ├── scoring/         # 5-pillar engine
│       ├── backtest/        # V4 + V7 strategies
│       ├── portfolio/       # Transactions, P&L
│       ├── pipeline/        # Recalc 6 steps
│       ├── ai/              # Gateway Ollama
│       ├── scraping/        # Celery tasks
│       ├── screener/        # Screen queries
│       ├── alerts/          # Rules & events
│       ├── imports/         # Excel / PDF
│       └── exports/         # Excel builder
├── alembic/                 # DB migrations
├── tests/                   # pytest + Playwright
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## Migration depuis CasaQuant legacy

Voir `docs/ARCHITECTURE_CIBLE_UNIFIEE.md` dans le repo legacy pour le plan complet.

## License

MIT
