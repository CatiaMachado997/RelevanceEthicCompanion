-- Durable idempotency ledger for side-effecting chat tool actions.
-- A unique action key is claimed before calling an external/write tool. If a
-- worker disappears after the side effect but before recording its response,
-- the same graph action is not executed a second time automatically.

CREATE TABLE IF NOT EXISTS public.tool_action_executions (
    action_key      TEXT        PRIMARY KEY,
    user_id         UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    conversation_id TEXT,
    planner_run_id  UUID,
    step_index      INTEGER     NOT NULL,
    action_index    INTEGER     NOT NULL,
    tool_name       TEXT        NOT NULL,
    input           JSONB       NOT NULL DEFAULT '{}'::jsonb,
    status          TEXT        NOT NULL DEFAULT 'started',
    output          JSONB,
    error_message   TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_action_executions_user_time
    ON public.tool_action_executions (user_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_action_executions_conversation
    ON public.tool_action_executions (conversation_id, started_at DESC)
    WHERE conversation_id IS NOT NULL;
