-- Ethic Companion Database Schema
-- For Supabase (Postgres + pgvector)
-- Version: 1.0

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector for semantic memory (M2)
CREATE EXTENSION IF NOT EXISTS vector;

-- ==================== Users Table ====================
-- Managed by Supabase Auth, but we can extend it

CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only read their own data
CREATE POLICY "Users can view own data"
    ON public.users FOR SELECT
    USING (auth.uid() = id);

-- ==================== User Values Table ====================
-- Critical: Stores user boundaries and preferences for ESL

CREATE TABLE IF NOT EXISTS public.user_values (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('boundary', 'preference', 'topic_filter', 'time_window')),
    value TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_user_values_user_id ON public.user_values(user_id);
CREATE INDEX idx_user_values_active ON public.user_values(active);
CREATE INDEX idx_user_values_priority ON public.user_values(priority);

-- Enable RLS
ALTER TABLE public.user_values ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Users can view own values"
    ON public.user_values FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own values"
    ON public.user_values FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own values"
    ON public.user_values FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own values"
    ON public.user_values FOR DELETE
    USING (auth.uid() = user_id);

-- ==================== Goals Table ====================

CREATE TABLE IF NOT EXISTS public.goals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
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
CREATE INDEX idx_goals_user_id ON public.goals(user_id);
CREATE INDEX idx_goals_status ON public.goals(status);
CREATE INDEX idx_goals_priority ON public.goals(priority);

-- Enable RLS
ALTER TABLE public.goals ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Users can view own goals"
    ON public.goals FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own goals"
    ON public.goals FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own goals"
    ON public.goals FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own goals"
    ON public.goals FOR DELETE
    USING (auth.uid() = user_id);

-- ==================== Events Table ====================
-- Calendar events and scheduled items

CREATE TABLE IF NOT EXISTS public.events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
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
CREATE INDEX idx_events_user_id ON public.events(user_id);
CREATE INDEX idx_events_start_time ON public.events(start_time);
CREATE INDEX idx_events_source ON public.events(source);

-- Enable RLS
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Users can view own events"
    ON public.events FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own events"
    ON public.events FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ==================== ESL Audit Log Table ====================
-- CRITICAL: Logs every ESL decision for transparency and research

CREATE TABLE IF NOT EXISTS public.esl_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
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
CREATE INDEX idx_esl_audit_user_id ON public.esl_audit_log(user_id);
CREATE INDEX idx_esl_audit_timestamp ON public.esl_audit_log(timestamp);
CREATE INDEX idx_esl_audit_decision_status ON public.esl_audit_log(decision_status);

-- Enable RLS
ALTER TABLE public.esl_audit_log ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Users can view own audit logs"
    ON public.esl_audit_log FOR SELECT
    USING (auth.uid() = user_id);

-- Note: Only backend can insert audit logs (no INSERT policy for users)

-- ==================== Semantic Memory Table (M2) ====================
-- Vector embeddings for conversations, notes, context

CREATE TABLE IF NOT EXISTS public.semantic_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536), -- OpenAI ada-002 embedding size
    source TEXT NOT NULL, -- 'conversation', 'note', 'calendar'
    source_id TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_semantic_memory_user_id ON public.semantic_memory(user_id);
CREATE INDEX idx_semantic_memory_timestamp ON public.semantic_memory(timestamp);

-- Vector similarity search index (HNSW for fast approximate search)
CREATE INDEX idx_semantic_memory_embedding ON public.semantic_memory
    USING hnsw (embedding vector_cosine_ops);

-- Enable RLS
ALTER TABLE public.semantic_memory ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Users can view own semantic memory"
    ON public.semantic_memory FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own semantic memory"
    ON public.semantic_memory FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ==================== User Sessions Table ====================
-- Track user state (focus mode, etc.)

CREATE TABLE IF NOT EXISTS public.user_sessions (
    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    focus_mode BOOLEAN NOT NULL DEFAULT FALSE,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.user_sessions ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Users can view own session"
    ON public.user_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update own session"
    ON public.user_sessions FOR UPDATE
    USING (auth.uid() = user_id);

-- ==================== Conversations Table (named chat threads) ====================

CREATE TABLE IF NOT EXISTS public.conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL DEFAULT 'New conversation',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON public.conversations(user_id, updated_at DESC);

-- ==================== Conversation Turns Table ====================
-- Reliable ordered history for LLM context (M1 backup for Weaviate)

CREATE TABLE IF NOT EXISTS public.conversation_turns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_conversation_turns_user_time
    ON public.conversation_turns(user_id, created_at DESC);

ALTER TABLE public.conversation_turns ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_conversation_turns_conv_id ON public.conversation_turns(conversation_id, created_at ASC);

-- Enable RLS
ALTER TABLE public.conversation_turns ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Users can view own conversation turns"
    ON public.conversation_turns FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own conversation turns"
    ON public.conversation_turns FOR INSERT
    WITH CHECK (auth.uid() = user_id);

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
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_values_updated_at
    BEFORE UPDATE ON public.user_values
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_sessions_updated_at
    BEFORE UPDATE ON public.user_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==================== Sample Data (for testing) ====================

-- Insert a test user value (example)
-- INSERT INTO public.user_values (user_id, type, value, priority)
-- VALUES (
--     'YOUR_USER_ID_HERE',
--     'boundary',
--     'no_work_after_19h',
--     1
-- );

-- ==================== User Settings Table ====================
-- Created via migration_profile_notifications_settings.sql; reproduced here for completeness

CREATE TABLE IF NOT EXISTS public.user_settings (
  user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  email_notifications BOOLEAN DEFAULT FALSE,
  push_notifications BOOLEAN DEFAULT FALSE,
  esl_alerts BOOLEAN DEFAULT TRUE,
  share_analytics BOOLEAN DEFAULT FALSE,
  pii_protection BOOLEAN DEFAULT TRUE,
  weight_goal_alignment    FLOAT DEFAULT 1.0,
  weight_time_sensitivity  FLOAT DEFAULT 1.0,
  weight_personal_values   FLOAT DEFAULT 1.0,
  weight_context_relevance FLOAT DEFAULT 1.0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==================== Relevance Adjustments Table ====================
-- User-specific multipliers nudged by feedback signals

CREATE TABLE IF NOT EXISTS public.relevance_adjustments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  signal_type TEXT NOT NULL,  -- 'goal_alignment', 'timeliness', 'recency', 'query_match'
  multiplier FLOAT NOT NULL DEFAULT 1.0,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, signal_type)
);

CREATE INDEX IF NOT EXISTS idx_relevance_adjustments_user_id ON public.relevance_adjustments(user_id);

-- ==================== User ESL Sensitivity Table ====================
-- Accumulates sensitivity boosts from value_conflict feedback

CREATE TABLE IF NOT EXISTS public.user_esl_sensitivity (
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  content_category TEXT NOT NULL,
  sensitivity_boost FLOAT DEFAULT 0.0,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, content_category)
);

-- ==================== Email Messages Table (M1) ====================
-- Structured storage for Gmail messages (complements M2 semantic search)

CREATE TABLE IF NOT EXISTS public.email_messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_email_messages_user_received ON public.email_messages(user_id, received_at DESC);

-- ==================== Slack Messages Table (M1) ====================
-- Structured storage for Slack messages (complements M2 semantic search)

CREATE TABLE IF NOT EXISTS public.slack_messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  channel TEXT NOT NULL,
  sender_id TEXT,
  text TEXT,
  ts TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, channel, ts)
);

CREATE INDEX IF NOT EXISTS idx_slack_messages_user_created ON public.slack_messages(user_id, created_at DESC);

-- ==================== Helpful Queries ====================

-- Get user's boundaries
-- SELECT * FROM public.user_values
-- WHERE user_id = 'YOUR_USER_ID'
--   AND type = 'boundary'
--   AND active = TRUE
-- ORDER BY priority;

-- Get ESL decisions for a user (last 7 days)
-- SELECT timestamp, decision_status, decision_reason
-- FROM public.esl_audit_log
-- WHERE user_id = 'YOUR_USER_ID'
--   AND timestamp > NOW() - INTERVAL '7 days'
-- ORDER BY timestamp DESC;

-- Vector similarity search example
-- SELECT content, 1 - (embedding <=> '[YOUR_QUERY_EMBEDDING]'::vector) AS similarity
-- FROM public.semantic_memory
-- WHERE user_id = 'YOUR_USER_ID'
-- ORDER BY embedding <=> '[YOUR_QUERY_EMBEDDING]'::vector
-- LIMIT 5;
