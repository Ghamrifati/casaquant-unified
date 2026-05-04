-- CasaQuant Unified — Migration 002: enrich portfolio schema

-- Add missing transaction columns (capital gains, realized P&L)
ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS cmp_moment NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS plus_value_brute NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS impot_pv NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS profit_net NUMERIC(15,2),
    ADD COLUMN IF NOT EXISTS montant_encaisse NUMERIC(15,2);

-- Rename existing legacy column for consistency
-- Note: 'total' already exists as total_fees; montant_net is the net amount

-- Portfolio snapshots table (was missing from 001)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    valorisation NUMERIC(15,2) NOT NULL,
    cash NUMERIC(15,2) NOT NULL,
    nb_positions INTEGER DEFAULT 0,
    perf_jour_pct NUMERIC(5,2),
    perf_masi_pct NUMERIC(5,2),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Virement type constraint helper
UPDATE virements SET type = 'DEPOT' WHERE type IS NULL OR type = '';
