-- Sprint J Task 4: per-tool safety preferences (finest grain).
--
-- A user can toggle "always ask before tool X" for any registered
-- tool. The "Trust this tool from now on" button in the paused-action
-- prompt deletes the matching row here (but does NOT touch the
-- master toggle or category preferences).

CREATE TABLE IF NOT EXISTS public.user_tool_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    requires_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, tool_name)
);

CREATE INDEX IF NOT EXISTS idx_user_tool_preferences_user
    ON public.user_tool_preferences (user_id);
