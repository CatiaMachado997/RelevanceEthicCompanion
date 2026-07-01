// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

// Dummy Supabase env vars so `lib/supabase.ts` doesn't throw at module load
// when tests transitively import dashboard routes. Tests that need real
// Supabase behavior mock the module explicitly.
process.env.NEXT_PUBLIC_SUPABASE_URL ||= 'https://test.supabase.co';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||= 'test-anon-key';
process.env.NEXT_PUBLIC_API_URL ||= 'http://localhost:8000';
