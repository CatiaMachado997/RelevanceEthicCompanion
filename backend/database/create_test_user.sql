-- Create test user for API testing
-- Run this in Supabase SQL Editor

-- First, create the auth user (this requires service_role permissions)
-- Note: In production, users would be created through Supabase Auth signup
-- This is ONLY for testing purposes

INSERT INTO auth.users (
    id,
    instance_id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    created_at,
    updated_at,
    confirmation_token,
    recovery_token
) VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated',
    'authenticated',
    'test@ethiccompanion.com',
    crypt('test123', gen_salt('bf')), -- password: test123
    NOW(),
    NOW(),
    NOW(),
    '',
    ''
) ON CONFLICT (id) DO NOTHING;

-- Then create the public user profile
INSERT INTO public.users (
    id,
    email,
    full_name,
    avatar_url
) VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'test@ethiccompanion.com',
    'Test User',
    NULL
) ON CONFLICT (id) DO UPDATE SET
    email = EXCLUDED.email,
    full_name = EXCLUDED.full_name;

-- Verify
SELECT id, email, full_name FROM public.users WHERE id = '00000000-0000-0000-0000-000000000001';
