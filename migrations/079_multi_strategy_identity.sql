alter table trading_signals
  add column if not exists strategy_id text,
  add column if not exists strategy_version text,
  add column if not exists strategy_name text,
  add column if not exists strategy_config_id bigint;

create index if not exists idx_trading_signals_strategy_id_created_at
  on trading_signals (strategy_id, created_at desc);

alter table optimizer_runs
  add column if not exists strategy_id text,
  add column if not exists strategy_version text;

create index if not exists idx_optimizer_runs_strategy_id_created_at
  on optimizer_runs (strategy_id, created_at desc);
