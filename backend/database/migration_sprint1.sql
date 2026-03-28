-- Sprint 1: Add source_items normalized ingestion table
-- This table provides a canonical normalized view of all ingested data,
-- independent of source-specific tables (calendar_events, slack_messages, etc.)
-- Safe to run multiple times (IF NOT EXISTS / ON CONFLICT DO NOTHING)

CREATE TABLE IF NOT EXISTS source_items (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type       TEXT        NOT NULL,        -- 'google_calendar', 'gmail', 'slack', 'upload'
    source_item_type  TEXT        NOT NULL,        -- 'event', 'email', 'message', 'document'
    external_id       TEXT,                        -- original ID in the source system
    title             TEXT,
    body              TEXT,
    metadata          JSONB       NOT NULL DEFAULT '{}',
    item_at           TIMESTAMPTZ,                 -- when the item occurred (event start, email sent...)
    synced_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    embedding_status  TEXT        NOT NULL DEFAULT 'pending',  -- 'pending' | 'indexed' | 'failed'
    sensitivity       INTEGER     NOT NULL DEFAULT 0,          -- 0=normal 1=sensitive 2=private
    relevance_hints   JSONB       NOT NULL DEFAULT '{}',
    UNIQUE (user_id, source_type, external_id)
);

CREATE INDEX IF NOT EXISTS idx_source_items_user_source
    ON source_items (user_id, source_type);

CREATE INDEX IF NOT EXISTS idx_source_items_user_item_at
    ON source_items (user_id, item_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_source_items_embedding_pending
    ON source_items (embedding_status)
    WHERE embedding_status = 'pending';
