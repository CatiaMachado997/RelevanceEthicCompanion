-- Add authentication fields to users table
-- Run this migration to add password and timezone support

-- Add password_hash field for storing hashed passwords
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- Add timezone field for user preference
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'UTC';

-- Add deleted_at for soft deletes (account deletion)
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

-- Add index on deleted_at to filter out deleted users
CREATE INDEX IF NOT EXISTS idx_users_deleted_at ON public.users(deleted_at);

-- Update RLS policies to exclude deleted users
DROP POLICY IF EXISTS "Users can view own data" ON public.users;
CREATE POLICY "Users can view own data"
    ON public.users FOR SELECT
    USING (auth.uid() = id AND deleted_at IS NULL);

-- Policy to allow users to update their own profile
DROP POLICY IF EXISTS "Users can update own data" ON public.users;
CREATE POLICY "Users can update own data"
    ON public.users FOR UPDATE
    USING (auth.uid() = id AND deleted_at IS NULL);

-- Policy to allow new user registration (needed for signup)
DROP POLICY IF EXISTS "Users can insert own data" ON public.users;
CREATE POLICY "Users can insert own data"
    ON public.users FOR INSERT
    WITH CHECK (true); -- Service key will handle this
