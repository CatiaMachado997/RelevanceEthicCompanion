-- Sprint B: connector backfill tracking + DocumentMemory source attribution.
-- The Weaviate property addition is performed at runtime by weaviate_client.py;
-- this migration only handles Postgres state.

CREATE TABLE IF NOT EXISTS public.connector_backfill_jobs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    source_type     TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending',  -- pending|running|complete|failed
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    items_processed INTEGER     NOT NULL DEFAULT 0,
    error_message   TEXT,
    UNIQUE (user_id, source_type, started_at)
);

CREATE INDEX IF NOT EXISTS idx_backfill_user_source
    ON public.connector_backfill_jobs (user_id, source_type, started_at DESC);
