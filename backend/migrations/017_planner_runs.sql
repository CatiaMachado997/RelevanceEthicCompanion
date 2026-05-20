-- Sprint I Task 1: planner_runs — one row per planner invocation (turn).
--
-- Captures the full ReAct trace as a JSONB blob in `plan_steps`. The
-- row is INSERTed when the planner first runs in a turn (status='running')
-- and UPDATEd at the end of the turn with totals + final status.
--
-- We also denormalize plan_steps into conversation_turns.metadata for
-- fast chat rendering, but this table is the source of truth and the
-- target of any future "show me the trace for that turn" queries.

CREATE TABLE IF NOT EXISTS public.planner_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    conversation_id UUID,
    conversation_turn_id UUID,
    intent TEXT,
    total_steps INTEGER NOT NULL DEFAULT 0,
    total_actions INTEGER NOT NULL DEFAULT 0,
    total_duration_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'cap_hit', 'error', 'vetoed')),
    plan_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_planner_runs_user_conv_created
    ON public.planner_runs (user_id, conversation_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_planner_runs_turn
    ON public.planner_runs (conversation_turn_id)
    WHERE conversation_turn_id IS NOT NULL;
