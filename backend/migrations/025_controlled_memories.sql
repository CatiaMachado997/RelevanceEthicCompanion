CREATE TABLE IF NOT EXISTS public.user_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    content TEXT NOT NULL CHECK (char_length(content) BETWEEN 1 AND 2000),
    kind TEXT NOT NULL DEFAULT 'fact' CHECK (kind IN ('fact', 'preference', 'summary')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    source_turn_id UUID REFERENCES public.conversation_turns(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_memories_active
    ON public.user_memories (user_id, updated_at DESC)
    WHERE active = TRUE;
