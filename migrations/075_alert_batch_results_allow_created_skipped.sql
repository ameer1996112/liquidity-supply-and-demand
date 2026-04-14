ALTER TABLE public.alert_batch_results
    DROP CONSTRAINT IF EXISTS alert_batch_results_status_check;

ALTER TABLE public.alert_batch_results
    ADD CONSTRAINT alert_batch_results_status_check
    CHECK (status IN ('pending', 'running', 'completed', 'created', 'skipped', 'failed', 'cancelled'));
