'use client'

import { useEffect, useState, useCallback } from 'react'
import { supabase } from '@/lib/supabase'
import type { Session, User } from '@supabase/supabase-js'

export type { User }

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? ''

async function exchangeSessionCookie(session: Session, rememberMe = false) {
  try {
    await fetch(`${API_URL}/api/auth/session`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        access_token: session.access_token,
        remember_me: rememberMe,
      }),
    })
    // Store only display state — never the token — in localStorage
    localStorage.setItem(
      'ec_display',
      JSON.stringify({
        displayName:
          session.user?.user_metadata?.full_name ?? session.user?.email,
        avatarUrl: session.user?.user_metadata?.avatar_url,
      }),
    )
  } catch (e) {
    console.warn('Cookie session setup failed (non-critical):', e)
  }
}

async function clearSessionCookie() {
  try {
    await fetch(`${API_URL}/api/auth/session`, {
      method: 'DELETE',
      credentials: 'include',
    })
    localStorage.removeItem('ec_display')
  } catch (e) {
    console.warn('Cookie session clear failed (non-critical):', e)
  }
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Restore session from localStorage on mount (handles page refresh)
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Keep in sync with auth state changes (sign in / sign out / token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        setUser(session?.user ?? null)
        if ((event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') && session) {
          exchangeSessionCookie(session)
        } else if (event === 'SIGNED_OUT') {
          clearSessionCookie()
        }
      }
    )
    return () => subscription.unsubscribe()
  }, [])

  const signIn = useCallback(async (email: string) => {
    const redirectTo = `${process.env.NEXT_PUBLIC_SITE_URL ?? (typeof window !== 'undefined' ? window.location.origin : '')}/auth/callback`
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: redirectTo },
    })
    if (error) throw error
  }, [])

  const signOut = useCallback(async () => {
    // Clear backend session cookie first — before Supabase signOut fires SIGNED_OUT
    // to avoid race where redirect lands before cookie is cleared
    await clearSessionCookie()
    const { error } = await supabase.auth.signOut()
    if (error) throw error
    localStorage.removeItem('ec_display')
    localStorage.removeItem('ec_lastRoute')
    if (typeof window !== 'undefined') window.location.href = '/login?signed_out=1'
  }, [])

  return {
    user,
    loading,
    isAuthenticated: !!user,
    signIn,
    signOut,
  }
}
