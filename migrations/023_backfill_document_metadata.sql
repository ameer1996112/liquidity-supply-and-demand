-- Migration 023: Backfill missing timeframe metadata on RAG documents
--
-- Problem: Documents ingested via harvest_youtube.py and ingest_youtube_transcripts.py
-- were missing the "timeframe" key in their JSONB metadata. The brain's RAG query
-- filtered by {"timeframe": "5m"}, causing these documents to be silently excluded
-- from all similarity searches (pgvector @> containment operator).
--
-- Fix: Add "timeframe" and "strategy" to all documents that don't have them.
-- The brain.py query no longer filters by timeframe, but we add the metadata
-- anyway for future filtering and auditability.

UPDATE public.documents
SET metadata = metadata || '{"timeframe": "5m", "strategy": "supply_demand_5m"}'::jsonb
WHERE NOT (metadata ? 'timeframe');

-- Verify: Count documents by metadata completeness
-- SELECT
--   COUNT(*) FILTER (WHERE metadata ? 'timeframe') AS has_timeframe,
--   COUNT(*) FILTER (WHERE NOT (metadata ? 'timeframe')) AS missing_timeframe,
--   COUNT(*) AS total
-- FROM public.documents;
