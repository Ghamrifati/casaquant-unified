"""CasaQuant Unified — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings

logger = logging.getLogger("casaquant.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup and cleanup on shutdown."""
    logger.info("CasaQuant Unified starting up — env=%s", settings.casaquant_env)

    # Initialize database schema (Alembic migrations should be run separately)
    # from app.domains.common.db import init_db
    # await init_db()

    # APScheduler / Celery Beat initialization happens in the worker container

    yield

    logger.info("CasaQuant Unified shutting down")


app = FastAPI(
    title="CasaQuant Unified API",
    description="Application unifiée d'analyse quantitative BVC/MASI.",
    version="3.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS is conservative: same-origin static files + localhost dev ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5500",
        "http://localhost:8000",
    ] if settings.is_sqlite else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ── Static Files (Frontend) ─────────────────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse, tags=["Santé"])
async def root():
    """Serve the main dashboard HTML."""
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CasaQuant Unified v3</title>
        <link rel="stylesheet" href="/static/src/styles.css">
    </head>
    <body>
        <div id="app">
            <h1>CasaQuant Unified v3.0</h1>
            <p>Architecture unifiée en cours de construction.</p>
            <a href="/docs">API Docs</a>
        </div>
        <script type="module" src="/static/src/main.js"></script>
    </body>
    </html>
    """


@app.get("/health", tags=["Santé"])
async def health():
    """Health check with basic system info."""
    return {
        "status": "ok",
        "version": "3.0.0",
        "env": settings.casaquant_env,
        "database": "connected" if not settings.is_sqlite else "sqlite",
    }


# ── Router Registration (Phase 2) ───────────────────────────────
# from app.domains.market.routes import router as market_router
# from app.domains.scoring.routes import router as scoring_router
# from app.domains.portfolio.routes import router as portfolio_router
# from app.domains.backtest.routes import router as backtest_router
# from app.domains.ai.routes import router as ai_router
# from app.domains.screener.routes import router as screener_router
# from app.domains.alerts.routes import router as alerts_router
# from app.domains.imports.routes import router as imports_router
# from app.domains.exports.routes import router as exports_router

# app.include_router(market_router, prefix="/api/market", tags=["Marché"])
# app.include_router(scoring_router, prefix="/api/scoring", tags=["Scoring"])
# app.include_router(portfolio_router, prefix="/api/portfolio", tags=["Portfolio"])
# app.include_router(backtest_router, prefix="/api/backtest", tags=["Backtest"])
# app.include_router(ai_router, prefix="/api/ia", tags=["IA"])
# app.include_router(screener_router, prefix="/api/screener", tags=["Screener"])
# app.include_router(alerts_router, prefix="/api/alerts", tags=["Alertes"])
# app.include_router(imports_router, prefix="/api/import", tags=["Import"])
# app.include_router(exports_router, prefix="/api/export", tags=["Export"])
