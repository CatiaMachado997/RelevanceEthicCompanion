-- Database safety net for repeated chat-created personal writes.
-- Existing and manually-created rows remain unconstrained because their key is NULL.

ALTER TABLE public.goals
    ADD COLUMN IF NOT EXISTS chat_dedupe_key TEXT;
ALTER TABLE public.tasks
    ADD COLUMN IF NOT EXISTS chat_dedupe_key TEXT;
ALTER TABLE public.user_values
    ADD COLUMN IF NOT EXISTS chat_dedupe_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_active_chat_goal
    ON public.goals (user_id, chat_dedupe_key)
    WHERE chat_dedupe_key IS NOT NULL AND status IN ('active', 'paused');

CREATE UNIQUE INDEX IF NOT EXISTS uq_open_chat_task
    ON public.tasks (user_id, chat_dedupe_key)
    WHERE chat_dedupe_key IS NOT NULL AND status IN ('todo', 'in_progress');

CREATE UNIQUE INDEX IF NOT EXISTS uq_active_chat_value
    ON public.user_values (user_id, chat_dedupe_key)
    WHERE chat_dedupe_key IS NOT NULL AND active;
