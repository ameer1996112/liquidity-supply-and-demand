-- 038_webhook_receipt_id.sql
-- Persist incoming webhooks at API level so signals appear in frontend even if
-- the worker never processes them (e.g. Redis down, worker down).
-- The API generates a receipt_id, inserts a "received" row, and passes the
-- receipt_id to the worker. The worker updates that row instead of inserting.

ALTER TABLE public.trading_signals
    ADD COLUMN IF NOT EXISTS webhook_receipt_id VARCHAR(64) NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_trading_signals_webhook_receipt_id
    ON public.trading_signals (webhook_receipt_id)
    WHERE webhook_receipt_id IS NOT NULL;

COMMENT ON COLUMN public.trading_signals.webhook_receipt_id IS
    'UUID from API when webhook received; worker updates this row instead of inserting.';
