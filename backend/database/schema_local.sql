-- Ethic Companion Database Schema (Local Development)
-- For Local PostgreSQL + pgvector
-- Version: 1.0

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector for semantic memory (M2)
CREATE EXTENSION IF NOT EXISTS vector;

-- ==================== Users Table ====================
-- Simple local version (no Supabase Auth)

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==================== User Values Table ====================
-- Critical: Stores user boundaries and preferences for ESL

CREATE TABLE IF NOT EXISTS user_values (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('boundary', 'preference', 'topic_filter', 'time_window')),
    value TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_user_values_user_id ON user_values(user_id);
CREATE INDEX IF NOT EXISTS idx_user_values_active ON user_values(active);
CREATE INDEX IF NOT EXISTS idx_user_values_priority ON user_values(priority);

-- ==================== Goals Table ====================

CREATE TABLE IF NOT EXISTS goals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused', 'archived')),
    priority INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    target_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_goals_user_id ON goals(user_id);
CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_goals_priority ON goals(priority);

-- ==================== Events Table ====================
-- Calendar events and scheduled items

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    location TEXT,
    source TEXT NOT NULL, -- 'google_calendar', 'manual', etc.
    source_id TEXT, -- External ID from source
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);

-- ==================== ESL Audit Log Table ====================
-- CRITICAL: Logs every ESL decision for transparency and research

CREATE TABLE IF NOT EXISTS esl_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    proposed_action JSONB NOT NULL, -- ProposedAction serialized
    decision_status TEXT NOT NULL CHECK (decision_status IN ('APPROVED', 'VETOED', 'MODIFIED')),
    decision_reason TEXT NOT NULL,
    violated_values TEXT[] DEFAULT '{}',
    applied_rules TEXT[] DEFAULT '{}',
    confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    context_snapshot JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_esl_audit_user_id ON esl_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_esl_audit_timestamp ON esl_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_esl_audit_decision_status ON esl_audit_log(decision_status);

-- ==================== Semantic Memory Table (M2) ====================
-- Vector embeddings for conversations, notes, context

CREATE TABLE IF NOT EXISTS semantic_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536), -- OpenAI ada-002 embedding size
    source TEXT NOT NULL, -- 'conversation', 'note', 'calendar'
    source_id TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_semantic_memory_user_id ON semantic_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_semantic_memory_timestamp ON semantic_memory(timestamp);

-- Vector similarity search index (HNSW for fast approximate search)
CREATE INDEX IF NOT EXISTS idx_semantic_memory_embedding ON semantic_memory
    USING hnsw (embedding vector_cosine_ops);

-- ==================== User Sessions Table ====================
-- Track user state (focus mode, etc.)

CREATE TABLE IF NOT EXISTS user_sessions (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    focus_mode BOOLEAN NOT NULL DEFAULT FALSE,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==================== Functions ====================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_values_updated_at ON user_values;
CREATE TRIGGER update_user_values_updated_at
    BEFORE UPDATE ON user_values
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_sessions_updated_at ON user_sessions;
CREATE TRIGGER update_user_sessions_updated_at
    BEFORE UPDATE ON user_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==================== Create Test User ====================
-- Insert a default test user for local development (matching backend MOCK_USER_ID)

INSERT INTO users (id, email, full_name)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'test@example.com',
    'Test User'
)
ON CONFLICT (id) DO NOTHING;

-- ==================== Sample Data ====================

-- Insert sample values for test user
INSERT INTO user_values (user_id, type, value, priority)
VALUES
    ('00000000-0000-0000-0000-000000000000', 'boundary', 'No work notifications after 7pm', 1),
    ('00000000-0000-0000-0000-000000000000', 'preference', 'Prefer morning meetings', 5)
ON CONFLICT DO NOTHING;

-- Insert sample goals for test user
INSERT INTO goals (user_id, title, description, status, priority)
VALUES
    ('00000000-0000-0000-0000-000000000000', 'Complete project MVP', 'Build the minimum viable product', 'active', 1),
    ('00000000-0000-0000-0000-000000000000', 'Learn PostgreSQL', 'Master database design and queries', 'active', 3)
ON CONFLICT DO NOTHING;

-- ==================== User Settings Table ====================

CREATE TABLE IF NOT EXISTS user_settings (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  email_notifications BOOLEAN DEFAULT FALSE,
  push_notifications BOOLEAN DEFAULT FALSE,
  esl_alerts BOOLEAN DEFAULT TRUE,
  share_analytics BOOLEAN DEFAULT FALSE,
  pii_protection BOOLEAN DEFAULT TRUE,
  weight_goal_alignment    FLOAT DEFAULT 1.0,
  weight_time_sensitivity  FLOAT DEFAULT 1.0,
  weight_personal_values   FLOAT DEFAULT 1.0,
  weight_context_relevance FLOAT DEFAULT 1.0,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available','focus','do_not_disturb','away')),
  status_until TIMESTAMPTZ,
  timezone TEXT,
  language TEXT
);

-- ==================== V2 Tables ====================

-- Data sources (Google Calendar, future: Gmail)
CREATE TABLE IF NOT EXISTS data_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('google_calendar', 'gmail', 'slack', 'notes', 'browsing_history')),
    oauth_token_encrypted TEXT,
    oauth_refresh_token_encrypted TEXT,
    token_expires_at TIMESTAMP WITH TIME ZONE,
    enabled BOOLEAN DEFAULT TRUE,
    last_sync TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_data_sources_user_id ON data_sources(user_id);
CREATE INDEX IF NOT EXISTS idx_data_sources_source_type ON data_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_data_sources_enabled ON data_sources(enabled);

-- Relevance feedback for tuning (V2)
CREATE TABLE IF NOT EXISTS relevance_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL CHECK (item_type IN ('search_result', 'memory', 'calendar_event', 'summary', 'proactive_suggestion')),
    item_id TEXT NOT NULL,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('thumbs_up', 'thumbs_down', 'dismiss', 'engage')),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    context_snapshot JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_relevance_feedback_user_id ON relevance_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_relevance_feedback_timestamp ON relevance_feedback(timestamp);
CREATE INDEX IF NOT EXISTS idx_relevance_feedback_feedback_type ON relevance_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_relevance_feedback_item_type ON relevance_feedback(item_type);

-- Context snapshots for relevance scoring (V2)
CREATE TABLE IF NOT EXISTS context_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    active_goals TEXT[],
    recent_events TEXT[],
    focus_mode BOOLEAN DEFAULT FALSE,
    current_context_summary TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_context_snapshots_user_id ON context_snapshots(user_id);
CREATE INDEX IF NOT EXISTS idx_context_snapshots_snapshot_time ON context_snapshots(snapshot_time);

-- ==================== Conversations Table (named chat threads) ====================

CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL DEFAULT 'New conversation',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id, updated_at DESC);

-- ==================== Conversation Turns Table ====================
-- Reliable ordered history for LLM context (M1 backup for Weaviate)

CREATE TABLE IF NOT EXISTS conversation_turns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversation_turns_user_time
    ON conversation_turns(user_id, created_at DESC);

ALTER TABLE conversation_turns ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_conversation_turns_conv_id ON conversation_turns(conversation_id, created_at ASC);

-- ==================== Relevance Adjustments Table ====================
-- User-specific multipliers nudged by feedback signals

CREATE TABLE IF NOT EXISTS relevance_adjustments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL,  -- 'goal_alignment', 'timeliness', 'recency', 'query_match'
    multiplier FLOAT NOT NULL DEFAULT 1.0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, signal_type)
);

CREATE INDEX IF NOT EXISTS idx_relevance_adjustments_user_id ON relevance_adjustments(user_id);

-- ==================== User ESL Sensitivity Table ====================

CREATE TABLE IF NOT EXISTS user_esl_sensitivity (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content_category TEXT NOT NULL,
  sensitivity_boost FLOAT DEFAULT 0.0,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, content_category)
);

-- ==================== Email Messages Table (M1) ====================

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

-- ==================== Slack Messages Table (M1) ====================

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

-- ==================== Additional notes on relevance_feedback ====================
-- The local schema feedback table may need additional_notes column
ALTER TABLE relevance_feedback ADD COLUMN IF NOT EXISTS additional_notes TEXT;

-- Daily AI insights (one per user per day, cached)
CREATE TABLE IF NOT EXISTS daily_insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  generated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_insights_user_date ON daily_insights(user_id, date);

-- ==================== Source Items Table (Sprint 2 connector foundation) ====================
-- Canonical normalized view of all ingested data, independent of source-specific tables

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

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Database schema initialized successfully!';
    RAISE NOTICE '👤 Test user created: test@example.com (ID: 00000000-0000-0000-0000-000000000000)';
    RAISE NOTICE '📊 Sample data inserted';
    RAISE NOTICE '✅ V2 tables created: data_sources, relevance_feedback, context_snapshots';
END $$;
