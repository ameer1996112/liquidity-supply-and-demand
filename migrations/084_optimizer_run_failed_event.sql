-- Allow the local optimizer agent to record terminal failures.
-- 083 added validate-mode events but missed run_failed, which the agent already emits.

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
