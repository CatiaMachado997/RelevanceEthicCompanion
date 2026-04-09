-- Migration 006: Auth audit log
-- Records login, logout, and token validation events for security auditing

CREATE TABLE IF NOT EXISTS auth_audit_log (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID,                                    -- NULL for pre-auth failures
    event       TEXT        NOT NULL,                    -- login_success | logout | token_invalid | token_expired | rate_limited | session_exchanged
    ip_address  TEXT,
    user_agent  TEXT,
    detail      JSONB,                                   -- optional extra context
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_audit_user_id   ON auth_audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_auth_audit_created_at ON auth_audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_audit_event      ON auth_audit_log (event);
