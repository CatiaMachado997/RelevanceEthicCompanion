-- Sprint C Task 1: unified tool-call telemetry.
-- Captures every tool invocation across chat turns AND scheduled flows.
-- Append-only; retention policy deferred to ops.

CREATE TABLE IF NOT EXISTS public.tool_call_events (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    tool_name       TEXT        NOT NULL,
    source          TEXT        NOT NULL,                     -- 'chat' | 'scheduled'
    source_ref      TEXT,                                     -- conversation_id or job name
    input           JSONB       NOT NULL DEFAULT '{}'::jsonb,
    output          JSONB,                                    -- nullable on early failure
    status          TEXT        NOT NULL,                     -- 'success' | 'error' | 'vetoed' | 'pending_confirmation'
    error_message   TEXT,
    esl_decision    TEXT,                                     -- 'APPROVED' | 'MODIFIED' | 'VETOED' | NULL
    latency_ms      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_call_events_user_time
    ON public.tool_call_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_call_events_tool_time
    ON public.tool_call_events (tool_name, created_at DESC);
