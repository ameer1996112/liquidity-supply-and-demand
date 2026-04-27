-- 083_optimizer_validate_modes.sql
-- Adds validate-mode metadata and broker dimension for OOS optimizer runs.

alter table public.optimizer_runs
    add column if not exists source_run_id UUID references public.optimizer_runs(id) on delete set null,
    add column if not exists brokers JSONB not null default '[]',
    add column if not exists backtest_range TEXT,
    add column if not exists custom_start_date DATE,
    add column if not exists custom_end_date DATE;

alter table public.optimizer_run_results
    add column if not exists broker TEXT,
    add column if not exists skip_reason TEXT;

alter table public.optimizer_run_results
    drop constraint if exists optimizer_run_results_status_check;

alter table public.optimizer_run_results
    add constraint optimizer_run_results_status_check
    check (status in ('pending', 'running', 'completed', 'failed', 'cancelled', 'skipped'));

alter table public.optimizer_run_events
    drop constraint if exists optimizer_run_events_event_type_check;

alter table public.optimizer_run_events
    add constraint optimizer_run_events_event_type_check
    check (event_type in (
        'run_started',
        'pair_started',
        'pair_completed',
        'pair_failed',
        'pair_skipped',
        'log',
        'run_finished',
        'run_failed',
        'run_cancelled'
    ));

alter table public.optimizer_run_results
    drop constraint if exists optimizer_run_results_run_id_symbol_key;

create unique index if not exists optimizer_run_results_run_symbol_broker_key
    on public.optimizer_run_results (run_id, symbol, coalesce(broker, ''));

create index if not exists idx_optimizer_runs_source_run_id
    on public.optimizer_runs (source_run_id);

create index if not exists idx_optimizer_run_results_run_symbol_broker
    on public.optimizer_run_results (run_id, symbol, broker);
