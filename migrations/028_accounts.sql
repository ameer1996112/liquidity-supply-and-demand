-- 028_accounts.sql
-- Multi-account routing foundation (Sprint 2.3).
-- One row per logical trading account; referenced by pipeline_traces.account_id.

CREATE TABLE IF NOT EXISTS public.accounts (
    -- ── Identity ─────────────────────────────────────────────────────────────
    id              BIGSERIAL PRIMARY KEY,
    account_id      VARCHAR(128) NOT NULL UNIQUE,   -- "default", "prop-acc-1", …
    name            VARCHAR(255) NOT NULL,

    -- ── Broker integration ───────────────────────────────────────────────────
    broker_type     VARCHAR(64) NOT NULL DEFAULT 'paper',  -- paper | metaapi | mock
    metaapi_account_id  VARCHAR(255),                       -- MT5 account ID (nullable)

    -- ── Lifecycle ────────────────────────────────────────────────────────────
    status          VARCHAR(32) NOT NULL DEFAULT 'active'  -- active | paused | disabled
                        CHECK (status IN ('active', 'paused', 'disabled')),

    -- ── Risk limits (per-account overrides) ──────────────────────────────────
    -- Stored as JSONB so limits can be extended without schema migrations.
    -- Keys mirror Settings fields, e.g.:
    --   {"max_daily_loss_pct": 3.0, "max_positions": 2, "risk_percent": 0.5}
    risk_limits     JSONB NOT NULL DEFAULT '{}',

    -- ── Routing ──────────────────────────────────────────────────────────────
    -- Redis queue key for this account's signal stream.
    -- "default" account uses the legacy "trading_queue" key for zero-change behaviour.
    -- All other accounts use "trading_queue:<account_id>".
    queue_key       VARCHAR(255) GENERATED ALWAYS AS (
                        CASE WHEN account_id = 'default'
                             THEN 'trading_queue'
                             ELSE 'trading_queue:' || account_id
                        END
                    ) STORED,

    -- ── Tags (free-form labels) ───────────────────────────────────────────────
    tags            TEXT[] NOT NULL DEFAULT '{}',

    -- ── Bookkeeping ──────────────────────────────────────────────────────────
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Trigger: keep updated_at current
CREATE OR REPLACE FUNCTION public.set_accounts_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_accounts_updated_at ON public.accounts;
CREATE TRIGGER trg_accounts_updated_at
    BEFORE UPDATE ON public.accounts
    FOR EACH ROW EXECUTE FUNCTION public.set_accounts_updated_at();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_accounts_status   ON public.accounts (status);
CREATE INDEX IF NOT EXISTS idx_accounts_broker   ON public.accounts (broker_type);

-- ── Seed: one default account so single-account deployments are unaffected ───
INSERT INTO public.accounts (account_id, name, broker_type, status, risk_limits, tags)
VALUES ('default', 'Default Account', 'paper', 'active', '{}', '{}')
ON CONFLICT (account_id) DO NOTHING;
