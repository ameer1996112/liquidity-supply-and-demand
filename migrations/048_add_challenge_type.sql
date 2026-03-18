-- Migration 048: Add challenge_type to broker_profiles

ALTER TABLE public.broker_profiles 
    ADD COLUMN IF NOT EXISTS challenge_type text 
    CHECK (challenge_type IN ('phase_1', 'phase_2', 'funded'));
