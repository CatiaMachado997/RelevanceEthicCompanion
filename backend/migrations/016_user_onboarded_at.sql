-- Sprint H Task 1: first-run onboarding state.
--
-- A single nullable timestamp on `users` is the source of truth for whether
-- the user has completed (or explicitly skipped) the first-run wizard. The
-- has_data_source / has_value / has_goal flags surfaced to the frontend are
-- derived live from the underlying tables, so we don't have to keep a
-- multi-step state machine in sync.
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS onboarded_at TIMESTAMPTZ NULL;
