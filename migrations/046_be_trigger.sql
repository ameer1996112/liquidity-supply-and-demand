-- Migration 046: Add break-even trigger fields to trading_signals
-- These allow the backend BreakevenManager to move SL on the broker
-- when price hits the pre-computed trigger level (sent by Pine Script webhook).

ALTER TABLE public.trading_signals
    ADD COLUMN IF NOT EXISTS be_trigger_price NUMERIC(20, 8),
    ADD COLUMN IF NOT EXISTS be_sl_price      NUMERIC(20, 8),
    ADD COLUMN IF NOT EXISTS be_triggered     BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN public.trading_signals.be_trigger_price IS
    'Price level at which the SL should be moved to break-even (computed by Pine).';
COMMENT ON COLUMN public.trading_signals.be_sl_price IS
    'New SL price to set when be_trigger_price is hit (entry or entry+n pips).';
COMMENT ON COLUMN public.trading_signals.be_triggered IS
    'True once the BreakevenManager has successfully moved the SL on the broker.';

CREATE INDEX IF NOT EXISTS idx_trading_signals_be_pending
    ON public.trading_signals (be_trigger_price, be_triggered, status)
    WHERE be_trigger_price IS NOT NULL AND be_triggered = FALSE AND status = 'OPEN';
