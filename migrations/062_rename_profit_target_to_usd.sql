-- Migration 062: Rename broker_profiles.profit_target → profit_target_usd
-- The Python code references profit_target_usd everywhere; the DB had it as profit_target.
-- This migration renames the column to match the codebase.

ALTER TABLE broker_profiles
  RENAME COLUMN profit_target TO profit_target_usd;
