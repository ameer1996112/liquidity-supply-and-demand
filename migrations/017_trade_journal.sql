-- Migration 017: Trade Journal
-- Trading journal with notes, tags, and screenshots

CREATE TABLE IF NOT EXISTS public.trade_journal (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signal_id           bigint REFERENCES public.trading_signals(id) ON DELETE CASCADE,
    account_name        VARCHAR(100),
    trade_key           TEXT,

    -- Note content
    note_text           TEXT NOT NULL,
    note_type           VARCHAR(20) DEFAULT 'general',
                        -- general, pre_trade, post_trade, lesson, mistake

    -- Tags for categorization
    tags                TEXT[], -- ['mistake', 'great_entry', 'revenge_trade', 'patience']

    -- Attachments (URLs to uploaded files)
    screenshot_urls     TEXT[], -- Array of URLs to screenshots/charts

    -- Sentiment/rating
    trade_rating        INTEGER CHECK (trade_rating BETWEEN 1 AND 5), -- 1-5 stars
    emotional_state     VARCHAR(50), -- calm, anxious, FOMO, confident, etc.

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure note text is not empty
    CONSTRAINT check_note_not_empty CHECK (TRIM(note_text) != '')
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trade_journal_signal
  ON public.trade_journal(signal_id);

CREATE INDEX IF NOT EXISTS idx_trade_journal_account
  ON public.trade_journal(account_name);

CREATE INDEX IF NOT EXISTS idx_trade_journal_trade_key
  ON public.trade_journal(trade_key);

CREATE INDEX IF NOT EXISTS idx_trade_journal_created
  ON public.trade_journal(created_at DESC);

-- GIN index for tags array (enables fast tag searches)
CREATE INDEX IF NOT EXISTS idx_trade_journal_tags
  ON public.trade_journal USING GIN(tags);

-- Comments
COMMENT ON TABLE public.trade_journal IS
  'Trading journal for recording thoughts, lessons, and emotions about trades. Linked to trading_signals via signal_id.';

COMMENT ON COLUMN public.trade_journal.note_type IS
  'Type of note: general, pre_trade (before entry), post_trade (after exit), lesson (key learning), mistake (what went wrong)';

COMMENT ON COLUMN public.trade_journal.tags IS
  'Array of tags for categorization. Examples: mistake, great_entry, FOMO, patience, revenge_trade';

COMMENT ON COLUMN public.trade_journal.screenshot_urls IS
  'Array of URLs pointing to uploaded screenshots or charts (S3, CDN, or local storage)';

COMMENT ON COLUMN public.trade_journal.trade_rating IS
  'Self-rating of trade execution quality (1-5 stars). 1=poor, 5=perfect';

COMMENT ON COLUMN public.trade_journal.emotional_state IS
  'Emotional state during trade: calm, anxious, FOMO, confident, frustrated, etc.';

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_trade_journal_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_trade_journal_updated_at ON public.trade_journal;
CREATE TRIGGER trigger_trade_journal_updated_at
    BEFORE UPDATE ON public.trade_journal
    FOR EACH ROW
    EXECUTE FUNCTION update_trade_journal_updated_at();

-- Verification query
SELECT
    'trade_journal' AS table_name,
    COUNT(*) AS row_count
FROM public.trade_journal;

-- Sample tag queries (for testing)
COMMENT ON INDEX idx_trade_journal_tags IS
  'Example query: SELECT * FROM trade_journal WHERE tags @> ARRAY[''mistake''] ORDER BY created_at DESC;';
