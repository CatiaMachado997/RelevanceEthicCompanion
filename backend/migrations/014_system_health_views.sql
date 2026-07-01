-- Sprint E Task 2: system-health views.
--
-- Aggregates the data we already collect into per-user views that the
-- Transparency "System health" tab consumes (Task 3 builds the route + UI).
-- All views are idempotent (CREATE OR REPLACE).
--
-- v_tool_call_health: per-tool latency + success rate over the last 24h.
-- v_esl_decision_summary: ESL decision counts over 24h / 7d windows.

CREATE OR REPLACE VIEW public.v_tool_call_health AS
SELECT
    user_id,
    tool_name,
    source,
    COUNT(*)::int                                                    AS calls_24h,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE status = 'success')
              / NULLIF(COUNT(*), 0)
    )::int                                                           AS success_rate,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms)::int    AS p50_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)::int    AS p95_latency_ms
FROM public.tool_call_events
WHERE created_at >= NOW() - INTERVAL '24 hours'
  AND latency_ms IS NOT NULL
GROUP BY user_id, tool_name, source;

CREATE OR REPLACE VIEW public.v_esl_decision_summary AS
SELECT
    user_id,
    decision_status,
    COUNT(*) FILTER (WHERE timestamp >= NOW() - INTERVAL '24 hours')::int AS count_24h,
    COUNT(*) FILTER (WHERE timestamp >= NOW() - INTERVAL '7 days')::int   AS count_7d
FROM public.esl_audit_log
GROUP BY user_id, decision_status;
