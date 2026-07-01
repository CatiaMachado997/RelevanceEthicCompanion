-- Sprint J Task 3: category-level safety preferences.
--
-- Tools declare a `category` in metadata (one of four values listed
-- in the CHECK constraint below). A user can toggle "always ask
-- before anything in this category." Default: empty (no rows = no
-- category-level pauses).

CREATE TABLE IF NOT EXISTS public.user_category_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (category IN (
        'read-personal', 'read-external', 'write-personal', 'write-external'
    )),
    requires_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, category)
);

CREATE INDEX IF NOT EXISTS idx_user_category_preferences_user
    ON public.user_category_preferences (user_id);
