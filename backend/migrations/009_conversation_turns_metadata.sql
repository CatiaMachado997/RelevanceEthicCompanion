-- Migration 009: Add metadata JSONB to conversation_turns.
-- Carries per-turn structured data such as RAG document_sources (citations),
-- so re-rendered conversations show their source cards on the frontend.

ALTER TABLE public.conversation_turns
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
