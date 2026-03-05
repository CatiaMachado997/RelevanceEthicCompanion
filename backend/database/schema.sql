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
