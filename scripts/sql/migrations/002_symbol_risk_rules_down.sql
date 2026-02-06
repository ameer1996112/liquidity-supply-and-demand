-- Rollback migration 002
DROP INDEX IF EXISTS idx_symbol_risk_rules_symbol;
DROP TABLE IF EXISTS public.symbol_risk_rules;
