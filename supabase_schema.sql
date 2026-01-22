-- Supabase Schema for Trading Bot
-- Run this in your Supabase SQL Editor

-- Create the main alerts table (trading_signals)
CREATE TABLE IF NOT EXISTS public.trading_signals (
    id BIGSERIAL PRIMARY KEY,

    -- Core trade info
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry REAL NOT NULL,
    sl REAL NOT NULL,
    tp REAL NOT NULL,
    size REAL NOT NULL,
    rr_ratio REAL,
    zone_id INTEGER,
    status TEXT DEFAULT 'pending',
    outcome TEXT,
    pnl REAL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Zone info
    zone_type TEXT,
    zone_top REAL,
    zone_bottom REAL,
    zone_size_pips REAL,
    entry_model TEXT,

    -- Liquidity flags
    liq_swept BOOLEAN DEFAULT FALSE,
    target_swept BOOLEAN DEFAULT FALSE,
    caused_sweep BOOLEAN DEFAULT FALSE,
    is_accuracy BOOLEAN DEFAULT FALSE,

    -- Mode and simulation
    mode TEXT DEFAULT 'manual',
    simulated_pnl REAL,
    close_price REAL,
    close_time TIMESTAMPTZ,

    -- Exit telemetry
    exit_type TEXT,
    bars_held INTEGER,
    mae_pips REAL,
    pnl_r REAL,

    -- V7.1 AI Features (18 total)
    score REAL,
    freshness INTEGER,
    session INTEGER,
    atr_ratio REAL,
    trend INTEGER,
    rsi REAL,
    htf_trend INTEGER,
    rvol REAL,
    adx REAL,
    touch_count INTEGER,
    base_quality REAL,
    departure_strength REAL,
    liquidity_distance REAL,
    liquidity_spread REAL,
    return_strength REAL,

    -- Computed features
    time_to_target_ratio REAL,
    drawdown_liq_alignment REAL,
    liq_invalidation_rate INTEGER,
    liq_confidence_score REAL
);

-- Create index on zone_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_trading_signals_zone_id ON public.trading_signals(zone_id);

-- Create index on created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_trading_signals_created_at ON public.trading_signals(created_at DESC);

-- Create index on status for filtering
CREATE INDEX IF NOT EXISTS idx_trading_signals_status ON public.trading_signals(status);

-- Disable Row Level Security (for testing - enable in production with proper policies)
ALTER TABLE public.trading_signals DISABLE ROW LEVEL SECURITY;

-- Or if you want RLS enabled, use these policies instead:
-- ALTER TABLE public.trading_signals ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Enable all for anon" ON public.trading_signals FOR ALL USING (true) WITH CHECK (true);

-- Create a function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to auto-update updated_at
CREATE TRIGGER update_trading_signals_updated_at
    BEFORE UPDATE ON public.trading_signals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust based on your needs)
GRANT ALL ON public.trading_signals TO anon;
GRANT ALL ON public.trading_signals TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE trading_signals_id_seq TO anon;
GRANT USAGE, SELECT ON SEQUENCE trading_signals_id_seq TO authenticated;
