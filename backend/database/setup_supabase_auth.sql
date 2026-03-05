-- Supabase Auth Integration - Database Setup
-- This creates automatic sync between auth.users and public.users

-- ==================== Auto-Create User Profile ====================
-- When a user signs up via Supabase Auth, automatically create their profile

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  -- Insert into public.users when new user created in auth.users
  INSERT INTO public.users (id, email, full_name, created_at)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
    NEW.created_at
  )
  ON CONFLICT (id) DO NOTHING; -- Prevent duplicates
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Create trigger on auth.users insert
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- ==================== Remove Old Auth Fields ====================
-- We don't need password_hash anymore (Supabase handles it)
-- Safe to run even if column doesn't exist

DO $$ 
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' 
    AND table_name = 'users' 
    AND column_name = 'password_hash'
  ) THEN
    ALTER TABLE public.users DROP COLUMN password_hash;
  END IF;
END $$;

-- Keep timezone and deleted_at (still useful)

-- ==================== Update RLS Policies ====================
-- Use auth.uid() which Supabase provides automatically
-- Safe to run multiple times (DROP IF EXISTS handles idempotency)

-- Enable RLS on users table if not already enabled
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Users table policies
DROP POLICY IF EXISTS "Users can view own data" ON public.users;
CREATE POLICY "Users can view own data"
    ON public.users FOR SELECT
    USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own data" ON public.users;
CREATE POLICY "Users can update own data"
    ON public.users FOR UPDATE
    USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can insert own data" ON public.users;
CREATE POLICY "Users can insert own data"
    ON public.users FOR INSERT
    WITH CHECK (auth.uid() = id);

-- ==================== Test the Setup ====================
-- After running this, test with:
-- 1. Sign up via API: POST /api/auth/signup
-- 2. Check if user appears in both auth.users and public.users
-- 3. Login via API: POST /api/auth/login
-- 4. Access protected route with token

-- You can verify the trigger with:
-- SELECT * FROM public.users WHERE email = 'your_test_email@example.com';
