-- Persistent observability for APScheduler jobs.

CREATE TABLE IF NOT EXISTS public.scheduled_job_runs (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    error_message TEXT,
    duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_scheduled_job_runs_job_id_started
    ON public.scheduled_job_runs (job_id, started_at DESC);

CREATE OR REPLACE VIEW public.v_scheduled_job_health AS
WITH latest AS (
    SELECT DISTINCT ON (job_id)
        job_id,
        started_at AS last_run_at,
        finished_at AS last_finished_at,
        status AS last_status,
        error_message AS last_error_message,
        duration_ms AS last_duration_ms
    FROM public.scheduled_job_runs
    ORDER BY job_id, started_at DESC, id DESC
),
last_success AS (
    SELECT job_id, MAX(id) AS last_success_id
    FROM public.scheduled_job_runs
    WHERE status = 'succeeded'
    GROUP BY job_id
),
failures AS (
    SELECT
        runs.job_id,
        COUNT(*) FILTER (
            WHERE runs.status = 'failed'
              AND runs.id > COALESCE(success.last_success_id, 0)
        )::int AS consecutive_failure_count
    FROM public.scheduled_job_runs AS runs
    LEFT JOIN last_success AS success USING (job_id)
    GROUP BY runs.job_id
)
SELECT
    latest.job_id,
    latest.last_run_at,
    latest.last_finished_at,
    latest.last_status,
    latest.last_error_message,
    latest.last_duration_ms,
    failures.consecutive_failure_count
FROM latest
JOIN failures USING (job_id);
