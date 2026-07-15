import { createBrowserClient } from '@supabase/ssr'

// createBrowserClient (from @supabase/ssr) stores the PKCE code verifier in
// cookies instead of localStorage, so it survives the redirect to /auth/callback
// even when the magic link opens in a new tab or after a navigation.
export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  {
    // The callback page exchanges PKCE codes explicitly. Keeping a single
    // owner avoids a race between client initialization and its auth listener.
    auth: { detectSessionInUrl: false },
  },
)
