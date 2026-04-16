'use client'

import { useState, useEffect, useRef } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { supabase } from '@/lib/supabase'
import { Shield, ArrowRight, Mail, CheckCircle } from 'lucide-react'

function friendlyAuthError(msg: string): string {
  if (msg.includes('Invalid login credentials')) return 'Incorrect email or password.'
  if (msg.includes('Email not confirmed')) return 'Please verify your email first.'
  if (msg.includes('Too many requests')) return 'Too many attempts. Please wait a moment.'
  if (msg.includes('rate limit')) return 'Too many attempts. Please wait a moment.'
  if (msg.includes('Unable to validate email')) return 'Please enter a valid email address.'
  return msg
}

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [oauthLoading, setOauthLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [signedOut, setSignedOut] = useState(false)
  const { signIn } = useAuth()

  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => { isMounted.current = false }
  }, [])

  const handleOAuthSignIn = async (provider: 'google' | 'azure' | 'github') => {
    setOauthLoading(provider)
    setError(null)
    const redirectTo = `${process.env.NEXT_PUBLIC_SITE_URL ?? window.location.origin}/auth/callback`
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo },
    })
    if (error) {
      if (isMounted.current) setError(friendlyAuthError(error.message))
      if (isMounted.current) setOauthLoading(null)
    } else {
      // Reset after 10 s in case the redirect is blocked (pop-up blocker, etc.)
      setTimeout(() => { if (isMounted.current) setOauthLoading(null) }, 10_000)
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('signed_out') === '1') {
      setSignedOut(true)
      window.history.replaceState({}, '', '/login')
      setTimeout(() => setSignedOut(false), 4000)
    }
  }, [])

  useEffect(() => {
    if (!sent) return
    const interval = setInterval(async () => {
      const { data: { session } } = await supabase.auth.getSession()
      if (session) {
        clearInterval(interval)
        const lastRoute = localStorage.getItem('ec_lastRoute') || '/dashboard'
        localStorage.removeItem('ec_lastRoute')
        window.location.href = lastRoute
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [sent])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email) return
    setIsSubmitting(true)
    setError(null)
    try {
      await signIn(email)
      setSent(true)
    } catch (err: unknown) {
      setError(friendlyAuthError(err instanceof Error ? err.message : 'Sign in failed. Please try again.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex" style={{ background: '#f2f2f2' }}>

      {/* Left panel — brand / atmospheric */}
      <div
        className="hidden lg:flex flex-col justify-between w-[480px] shrink-0 p-12 relative overflow-hidden"
        style={{ background: '#111111' }}
      >
        {/* Noise texture overlay */}
        <div className="absolute inset-0 opacity-[0.04]" style={{
          backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 256 256\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\'/%3E%3C/svg%3E")',
          backgroundRepeat: 'repeat',
        }} />

        {/* Glowing orb */}
        <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full opacity-15" style={{
          background: 'radial-gradient(circle, #4a7c59 0%, transparent 70%)',
        }} />
        <div className="absolute bottom-0 right-0 w-64 h-64 rounded-full opacity-10" style={{
          background: 'radial-gradient(circle, #4a7c59 0%, transparent 70%)',
        }} />

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.15)' }}>
            <Shield size={16} color="white" />
          </div>
          <span className="text-sm font-medium" style={{ color: 'rgba(255,255,255,0.7)' }}>Ethic Companion</span>
        </div>

        {/* Hero copy */}
        <div className="relative z-10 space-y-6">
          <div>
            <h2
              className="text-4xl leading-tight mb-4"
              style={{ fontFamily: 'var(--font-fraunces)', color: '#ffffff', fontWeight: 300 }}
            >
              AI that works<br />
              <em>for you.</em><br />
              Not against you.
            </h2>
            <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.45)' }}>
              Every decision reviewed. Every boundary respected.<br />
              Your values, encoded.
            </p>
          </div>

          {/* Feature list */}
          <div className="space-y-3">
            {[
              'Ethical safeguard on every action',
              'Your values encoded, not assumed',
              'Zero engagement manipulation',
            ].map((item) => (
              <div key={item} className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: '#4a7c59' }} />
                <span className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>{item}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom quote */}
        <div className="relative z-10">
          <p className="text-xs italic" style={{ color: 'rgba(255,255,255,0.25)' }}>
            &ldquo;Trust over engagement, always.&rdquo;
          </p>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-[400px]">

          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-10 lg:hidden">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: '#111111' }}>
              <Shield size={14} color="white" />
            </div>
            <span className="text-sm font-medium" style={{ color: '#1a1a1a' }}>Ethic Companion</span>
          </div>

          {sent ? (
            <div className="space-y-6">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{ background: '#f0f0f0', border: '1px solid #e0e0e0' }}>
                <Mail size={22} style={{ color: '#1a1a1a' }} />
              </div>
              <div>
                <h1 className="text-2xl font-semibold mb-2" style={{ fontFamily: 'var(--font-fraunces)', color: '#111111', fontWeight: 400 }}>
                  Check your inbox
                </h1>
                <p className="text-sm leading-relaxed" style={{ color: '#666666' }}>
                  We sent a magic link to{' '}
                  <span className="font-medium" style={{ color: '#1a1a1a' }}>{email}</span>.
                  Click it to sign in — no password needed.
                </p>
              </div>

              <div className="rounded-xl p-4 flex items-start gap-3" style={{ background: '#f5f2ef', border: '1px solid #e8e2dc' }}>
                <CheckCircle size={15} className="mt-0.5 shrink-0" style={{ color: '#7a6e65' }} />
                <p className="text-xs leading-relaxed" style={{ color: '#7a6e65' }}>
                  The link expires in 10 minutes. If you don&apos;t see the email, check your spam folder.
                </p>
              </div>

              <button
                onClick={() => { setSent(false); setEmail('') }}
                className="text-xs underline underline-offset-2 transition-opacity hover:opacity-60"
                style={{ color: '#666666' }}
              >
                Use a different email
              </button>
            </div>
          ) : (
            <div className="space-y-8">
              {signedOut && (
                <div
                  className="rounded-lg px-4 py-3 text-sm flex items-center gap-2"
                  style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534' }}
                >
                  <CheckCircle size={14} />
                  You&apos;ve been signed out.
                </div>
              )}

              <div>
                <h1 className="text-3xl mb-2" style={{ fontFamily: 'var(--font-fraunces)', color: '#111111', fontWeight: 400 }}>
                  Welcome back
                </h1>
                <p className="text-sm" style={{ color: '#666666' }}>
                  Enter your email to receive a sign-in link.
                </p>
              </div>

              {/* OAuth provider buttons */}
              <div className="flex flex-col gap-2 mb-6">
                {/* Google */}
                <button
                  type="button"
                  onClick={() => handleOAuthSignIn('google')}
                  disabled={!!oauthLoading}
                  className="w-full h-11 rounded-xl flex items-center gap-3 px-4 text-sm font-medium border transition-all disabled:opacity-50"
                  style={{ background: '#fff', borderColor: '#e0e0e0', color: '#111' }}
                  onMouseEnter={e => { if (!oauthLoading) e.currentTarget.style.borderColor = '#4a7c59' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = '#e0e0e0' }}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  {oauthLoading === 'google' ? 'Redirecting…' : 'Continue with Google'}
                </button>

                {/* Microsoft */}
                <button
                  type="button"
                  onClick={() => handleOAuthSignIn('azure')}
                  disabled={!!oauthLoading}
                  className="w-full h-11 rounded-xl flex items-center gap-3 px-4 text-sm font-medium border transition-all disabled:opacity-50"
                  style={{ background: '#fff', borderColor: '#e0e0e0', color: '#111' }}
                  onMouseEnter={e => { if (!oauthLoading) e.currentTarget.style.borderColor = '#4a7c59' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = '#e0e0e0' }}
                >
                  <svg width="18" height="18" viewBox="0 0 21 21" aria-hidden="true">
                    <rect x="1" y="1" width="9" height="9" fill="#f25022"/>
                    <rect x="11" y="1" width="9" height="9" fill="#7fba00"/>
                    <rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>
                    <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
                  </svg>
                  {oauthLoading === 'azure' ? 'Redirecting…' : 'Continue with Microsoft'}
                </button>

                {/* GitHub */}
                <button
                  type="button"
                  onClick={() => handleOAuthSignIn('github')}
                  disabled={!!oauthLoading}
                  className="w-full h-11 rounded-xl flex items-center gap-3 px-4 text-sm font-medium border transition-all disabled:opacity-50"
                  style={{ background: '#fff', borderColor: '#e0e0e0', color: '#111' }}
                  onMouseEnter={e => { if (!oauthLoading) e.currentTarget.style.borderColor = '#4a7c59' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = '#e0e0e0' }}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
                  </svg>
                  {oauthLoading === 'github' ? 'Redirecting…' : 'Continue with GitHub'}
                </button>
              </div>

              {/* Divider */}
              <div className="flex items-center gap-3 mb-6">
                <div className="flex-1 h-px" style={{ background: '#e0e0e0' }} />
                <span className="text-xs" style={{ color: '#9e9e9e' }}>or continue with email</span>
                <div className="flex-1 h-px" style={{ background: '#e0e0e0' }} />
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium tracking-widest uppercase" style={{ color: '#9e9e9e' }}>
                    Email address
                  </label>
                  <input
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={isSubmitting}
                    className="w-full h-12 rounded-xl px-4 text-sm transition-all outline-none disabled:opacity-50"
                    style={{
                      background: '#ffffff',
                      border: '1px solid #e0e0e0',
                      color: '#111111',
                    }}
                    onFocus={(e) => { e.currentTarget.style.borderColor = '#4a7c59'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(74,124,89,0.12)' }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = '#e0e0e0'; e.currentTarget.style.boxShadow = 'none' }}
                  />
                </div>

                {error && (
                  <div className="rounded-lg px-4 py-3 text-sm" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c' }}>
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isSubmitting || !email}
                  className="w-full h-12 rounded-xl flex items-center justify-center gap-2 text-sm font-medium transition-all disabled:opacity-40"
                  style={{ background: '#4a7c59', color: '#ffffff' }}
                  onMouseEnter={(e) => { if (!isSubmitting) e.currentTarget.style.background = '#3d6b4a' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = '#4a7c59' }}
                >
                  {isSubmitting ? (
                    <>
                      <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      Send magic link
                      <ArrowRight size={15} />
                    </>
                  )}
                </button>
              </form>

              <p className="text-xs text-center" style={{ color: '#9e9e9e' }}>
                No account yet? Just enter your email — we&apos;ll create one.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
