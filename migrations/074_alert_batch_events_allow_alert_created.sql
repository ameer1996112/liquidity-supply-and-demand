-- 074_alert_batch_events_allow_alert_created.sql
-- Allow alert-created event rows emitted by the local alert runner.

ALTER TABLE public.alert_batch_events
    DROP CONSTRAINT IF EXISTS alert_batch_events_event_type_check;

ALTER TABLE public.alert_batch_events
    ADD CONSTRAINT alert_batch_events_event_type_check
    CHECK (
        event_type IN (
            'batch_started',
            'pair_started',
            'alert_created',
            'pair_completed',
            'pair_failed',
            'log',
            'batch_finished',
            'batch_cancelled'
        )
    );
