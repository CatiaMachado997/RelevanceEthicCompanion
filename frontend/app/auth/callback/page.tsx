'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { Shield } from 'lucide-react'

export default function AuthCallbackPage() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const handle = async () => {
      try {
        const params = new URLSearchParams(window.location.search)
        const errorCode = params.get('error')
        const errorDescription = params.get('error_description')

        if (errorCode) {
          setError(errorDescription ?? 'Authentication failed.')
          return
        }

        // createBrowserClient (@supabase/ssr) automatically exchanges the
        // ?code= param and stores the PKCE verifier in cookies — we just
        // need to wait for the session to be ready via onAuthStateChange.
        // Calling exchangeCodeForSession() manually would consume the
        // verifier a second time and throw "PKCE code verifier not found".
        const { data: { session }, error: sessionError } = await supabase.auth.getSession()

        if (sessionError) {
          setError(sessionError.message)
          return
        }

        if (!session) {
          // Session not ready yet — wait for auth state change
          const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (event, newSession) => {
              if (event === 'SIGNED_IN' && newSession) {
                subscription.unsubscribe()
                await syncSessionCookie(newSession.access_token)
                router.push('/dashboard')
              } else if (event === 'SIGNED_OUT') {
                subscription.unsubscribe()
                setError('Sign in failed. Please try again.')
              }
            }
          )
          return
        }

        await syncSessionCookie(session.access_token)
        router.push('/dashboard')
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Something went wrong.')
      }
    }

    handle()
  }, [router])

  return error ? (
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#f2f2f2' }}>
      <div className="text-center space-y-4 max-w-sm px-6">
        <p className="text-sm" style={{ color: '#b04a3a' }}>{error}</p>
        <button
          onClick={() => router.push('/login')}
          className="text-xs underline underline-offset-2"
          style={{ color: '#555555' }}
        >
          Back to sign in
        </button>
      </div>
    </div>
  ) : (
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#f2f2f2' }}>
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center animate-pulse" style={{ background: '#111111' }}>
          <Shield size={18} color="white" />
        </div>
        <p className="text-sm" style={{ color: '#555555' }}>Signing you in…</p>
      </div>
    </div>
  )
}

async function syncSessionCookie(accessToken: string) {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? ''
    await fetch(`${apiUrl}/api/auth/session`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ access_token: accessToken }),
    })
  } catch {
    // Non-critical — middleware now uses Supabase session directly
  }
}
