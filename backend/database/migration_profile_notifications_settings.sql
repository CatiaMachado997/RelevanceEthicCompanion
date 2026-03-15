-- Add profile fields to users table
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
-- Note: timezone may already exist as TEXT from add_auth_fields.sql (IF NOT EXISTS is safe)
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';

-- Notifications
CREATE TABLE IF NOT EXISTS public.user_notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  type VARCHAR(50) NOT NULL,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'
);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_notification_type'
      AND conrelid = 'public.user_notifications'::regclass
  ) THEN
    ALTER TABLE public.user_notifications
      ADD CONSTRAINT chk_notification_type
      CHECK (type IN ('esl_block', 'goal_completed', 'info', 'warning'));
  END IF;
END$$;
CREATE INDEX IF NOT EXISTS idx_user_notifications_user_created
  ON public.user_notifications (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_notifications_unread
  ON public.user_notifications (user_id, created_at DESC)
  WHERE read = FALSE;

-- Settings
CREATE TABLE IF NOT EXISTS public.user_settings (
  user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  email_notifications BOOLEAN DEFAULT FALSE,
  push_notifications BOOLEAN DEFAULT FALSE,
  esl_alerts BOOLEAN DEFAULT TRUE,
  share_analytics BOOLEAN DEFAULT FALSE,
  pii_protection BOOLEAN DEFAULT TRUE,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Keep updated_at current on settings changes
CREATE OR REPLACE TRIGGER update_user_settings_updated_at
  BEFORE UPDATE ON public.user_settings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
