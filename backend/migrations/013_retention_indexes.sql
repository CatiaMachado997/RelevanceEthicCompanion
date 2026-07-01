-- Sprint E Task 1: indexes to support the daily retention prune job.
--
-- The prune job runs `DELETE ... WHERE created_at < cutoff` on tool_call_events
-- and `DELETE ... WHERE timestamp < cutoff` on esl_audit_log. Both should be
-- index-supported.
--
-- tool_call_events already has (user_id, created_at DESC) and (tool_name, created_at DESC)
-- composite indexes from migration 012; PostgreSQL can use either for a range
-- scan on created_at, so no new index is required there.
--
-- esl_audit_log has idx_esl_audit_timestamp in the canonical schema, but older
-- environments may have been provisioned before that index existed. This
-- migration ensures it exists. Idempotent.

CREATE INDEX IF NOT EXISTS idx_esl_audit_timestamp
    ON public.esl_audit_log (timestamp);
