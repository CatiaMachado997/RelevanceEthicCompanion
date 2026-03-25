-- V2 Sprint Migration — new tables for feedback loop, ESL sensitivity, email/slack M1
-- Run with: psql -h localhost -U postgres -d ethic-companion -f backend/database/migration_v2_sprint.sql

CREATE TABLE IF NOT EXISTS relevance_adjustments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL,
    multiplier FLOAT NOT NULL DEFAULT 1.0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, signal_type)
);

CREATE INDEX IF NOT EXISTS idx_relevance_adjustments_user_id ON relevance_adjustments(user_id);

CREATE TABLE IF NOT EXISTS user_esl_sensitivity (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content_category TEXT NOT NULL,
    sensitivity_boost FLOAT DEFAULT 0.0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, content_category)
);

CREATE TABLE IF NOT EXISTS email_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source TEXT NOT NULL DEFAULT 'gmail',
    external_id TEXT NOT NULL,
    subject TEXT,
    sender TEXT,
    snippet TEXT,
    received_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_email_messages_user_received ON email_messages(user_id, received_at DESC);

CREATE TABLE IF NOT EXISTS slack_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    sender_id TEXT,
    text TEXT,
    ts TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, channel, ts)
);

CREATE INDEX IF NOT EXISTS idx_slack_messages_user_created ON slack_messages(user_id, created_at DESC);

ALTER TABLE relevance_feedback ADD COLUMN IF NOT EXISTS additional_notes TEXT;

-- Weight columns for user-tunable relevance
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS weight_goal_alignment FLOAT DEFAULT 1.0;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS weight_time_sensitivity FLOAT DEFAULT 1.0;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS weight_personal_values FLOAT DEFAULT 1.0;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS weight_context_relevance FLOAT DEFAULT 1.0;
