-- Create conversation_turns table for reliable ordered conversation history
-- This serves as M1 backup for Weaviate semantic memory

CREATE TABLE IF NOT EXISTS public.conversation_turns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient user + time-based queries
CREATE INDEX IF NOT EXISTS idx_conversation_turns_user_time
    ON public.conversation_turns(user_id, created_at DESC);

-- Enable Row Level Security
ALTER TABLE public.conversation_turns ENABLE ROW LEVEL SECURITY;

-- RLS Policies: users can only view and insert their own rows
CREATE POLICY "Users can view own conversation turns"
    ON public.conversation_turns FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own conversation turns"
    ON public.conversation_turns FOR INSERT
    WITH CHECK (auth.uid() = user_id);
