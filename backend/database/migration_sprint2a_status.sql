-- Sprint 2a: User status + settings schema additions
ALTER TABLE public.user_settings
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'focus', 'do_not_disturb', 'away')),
    ADD COLUMN IF NOT EXISTS status_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS timezone TEXT,
    ADD COLUMN IF NOT EXISTS language TEXT;
