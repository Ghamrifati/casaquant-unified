-- CasaQuant Unified — Initial schema migration
-- Creates all tables for the unified architecture

-- ── Tickers ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tickers (
    id SERIAL PRIMARY KEY,
    code_bc VARCHAR(20) UNIQUE NOT NULL,
    nom VARCHAR(200) NOT NULL,
    secteur VARCHAR(100),
    actif BOOLEAN DEFAULT true,
    illiquide BOOLEAN DEFAULT false
);

-- ── Intraday snapshots ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_snapshots (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    session_time TIMESTAMPTZ NOT NULL,
    price NUMERIC(12,4),
    volume BIGINT,
    bid NUMERIC(12,4),
    ask NUMERIC(12,4),
    source VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_session ON market_snapshots(ticker_id, session_time);

-- ── Daily features (EOD aggregates) ────────────────────────────
CREATE TABLE IF NOT EXISTS market_features (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    date DATE NOT NULL,
    open NUMERIC(12,4),
    high NUMERIC(12,4),
    low NUMERIC(12,4),
    close NUMERIC(12,4),
    volume BIGINT,
    vwap NUMERIC(12,4),
    UNIQUE(ticker_id, date)
);

-- ── OHLCV (EOD) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ohlcv (
    id BIGSERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    date DATE NOT NULL,
    open NUMERIC(12,4),
    high NUMERIC(12,4),
    low NUMERIC(12,4),
    close NUMERIC(12,4),
    volume BIGINT,
    UNIQUE(ticker_id, date)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_date ON ohlcv(ticker_id, date);

-- ── Indicators ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS indicators_snapshot (
    ticker_id INTEGER PRIMARY KEY REFERENCES tickers(id),
    computed_at TIMESTAMPTZ,
    sma20 NUMERIC(12,4),
    sma50 NUMERIC(12,4),
    sma200 NUMERIC(12,4),
    rsi NUMERIC(5,2),
    macd NUMERIC(12,4),
    bb_pct NUMERIC(5,4),
    adx NUMERIC(5,2),
    atr NUMERIC(12,4)
);

-- ── MASI Index ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS masi_index (
    id BIGSERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    open NUMERIC(12,4),
    high NUMERIC(12,4),
    low NUMERIC(12,4),
    close NUMERIC(12,4),
    volume BIGINT
);

-- ── Scoring ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scoring_final (
    ticker_id INTEGER PRIMARY KEY REFERENCES tickers(id),
    score_momentum NUMERIC(5,2),
    score_trend NUMERIC(5,2),
    score_risk NUMERIC(5,2),
    score_value NUMERIC(5,2),
    score_liquidity NUMERIC(5,2),
    score_final NUMERIC(5,2),
    computed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS scoring_history (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    date DATE NOT NULL,
    score_momentum NUMERIC(5,2),
    score_trend NUMERIC(5,2),
    score_risk NUMERIC(5,2),
    score_value NUMERIC(5,2),
    score_liquidity NUMERIC(5,2),
    score_final NUMERIC(5,2),
    computed_at TIMESTAMPTZ DEFAULT now()
);

-- ── Backtest ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backtest_results (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    strategy_version VARCHAR(10) NOT NULL,
    win_rate NUMERIC(5,2),
    profit_val NUMERIC(15,2),
    max_drawdown NUMERIC(5,2),
    sharpe NUMERIC(5,2),
    start_date DATE,
    end_date DATE,
    params_hash VARCHAR(64),
    computed_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_backtest_version ON backtest_results(ticker_id, strategy_version, computed_at);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id BIGSERIAL PRIMARY KEY,
    result_id INTEGER REFERENCES backtest_results(id),
    entry_date DATE,
    exit_date DATE,
    entry_price NUMERIC(12,4),
    exit_price NUMERIC(12,4),
    qty INTEGER,
    pnl NUMERIC(15,2),
    fees NUMERIC(15,2),
    exit_reason VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS backtest_lab_runs (
    id SERIAL PRIMARY KEY,
    strategy_version VARCHAR(10),
    description TEXT,
    params TEXT,
    win_rate NUMERIC(5,2),
    profit_val NUMERIC(15,2),
    max_drawdown NUMERIC(5,2),
    computed_at TIMESTAMPTZ DEFAULT now()
);

-- ── Portfolio ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    qty INTEGER DEFAULT 0,
    avg_price NUMERIC(12,4),
    opened_at DATE,
    strategy VARCHAR(10) DEFAULT 'v4',
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    date DATE,
    type VARCHAR(10), -- 'ACHAT' | 'VENTE'
    qty INTEGER DEFAULT 0,
    price NUMERIC(12,4),
    brokerage NUMERIC(15,2),
    tax NUMERIC(15,2),
    vat NUMERIC(15,2),
    total NUMERIC(15,2),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS virements (
    id SERIAL PRIMARY KEY,
    date DATE,
    type VARCHAR(20),
    amount NUMERIC(15,2),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Paper Trading ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS paper_trades (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    type VARCHAR(10),
    qty INTEGER DEFAULT 0,
    price NUMERIC(12,4),
    status VARCHAR(20) DEFAULT 'OPEN',
    pnl NUMERIC(15,2),
    opened_at DATE,
    closed_at DATE,
    strategy VARCHAR(10) DEFAULT 'v4',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Watchlist ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    note TEXT,
    alert_price NUMERIC(12,4),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Alerts ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_rules (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    condition VARCHAR(100),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alert_events (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES alert_rules(id),
    triggered_at TIMESTAMPTZ DEFAULT now(),
    value NUMERIC(12,4),
    message TEXT,
    sent BOOLEAN DEFAULT false
);

-- ── AI ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ia_analyses (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    mode VARCHAR(30),
    model VARCHAR(50),
    prompt_hash VARCHAR(64),
    response TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cached BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ia_cache ON ia_analyses(ticker_id, mode, model, prompt_hash, created_at);

-- ── Cache ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cache_kv (
    key VARCHAR(255) PRIMARY KEY,
    value BYTEA,
    expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_kv(expires_at);

-- ── Job Tracking ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(50),
    status VARCHAR(20),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    detail JSONB,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobruns_status ON job_runs(status, started_at);

-- ── Juste Valeur ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS juste_valeur (
    id SERIAL PRIMARY KEY,
    ticker_id INTEGER REFERENCES tickers(id),
    date DATE NOT NULL,
    valeur NUMERIC(12,4),
    per NUMERIC(5,2),
    dividend_yield NUMERIC(5,2),
    source VARCHAR(50),
    UNIQUE(ticker_id, date)
);
CREATE INDEX IF NOT EXISTS idx_jv_ticker_date ON juste_valeur(ticker_id, date);

-- ── Ingestion Log ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_log (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50),
    records_count INTEGER,
    status VARCHAR(20),
    detail TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Quality Report ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quality_report (
    id SERIAL PRIMARY KEY,
    date DATE,
    ticker_coverage_pct NUMERIC(5,2),
    missing_tickers INTEGER,
    stale_tickers INTEGER,
    quarantine_count INTEGER,
    computed_at TIMESTAMPTZ DEFAULT now()
);
