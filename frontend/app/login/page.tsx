'use client'

import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
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
  const [error, setError] = useState<string | null>(null)
  const { signIn } = useAuth()

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
    <div className="min-h-screen flex" style={{ background: '#f9f6fa' }}>

      {/* Left panel — brand / atmospheric */}
      <div
        className="hidden lg:flex flex-col justify-between w-[480px] shrink-0 p-12 relative overflow-hidden"
        style={{ background: '#1c1520' }}
      >
        {/* Noise texture overlay */}
        <div className="absolute inset-0 opacity-[0.04]" style={{
          backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 256 256\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\'/%3E%3C/svg%3E")',
          backgroundRepeat: 'repeat',
        }} />

        {/* Glowing orb */}
        <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full opacity-20" style={{
          background: 'radial-gradient(circle, #9b7ec8 0%, transparent 70%)',
        }} />
        <div className="absolute bottom-0 right-0 w-64 h-64 rounded-full opacity-10" style={{
          background: 'radial-gradient(circle, #c78b8b 0%, transparent 70%)',
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
                <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: '#9b7ec8' }} />
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
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: '#1c1520' }}>
              <Shield size={14} color="white" />
            </div>
            <span className="text-sm font-medium" style={{ color: '#332b36' }}>Ethic Companion</span>
          </div>

          {sent ? (
            <div className="space-y-6">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{ background: '#f0ede8', border: '1px solid #e4dee7' }}>
                <Mail size={22} style={{ color: '#332b36' }} />
              </div>
              <div>
                <h1 className="text-2xl font-semibold mb-2" style={{ fontFamily: 'var(--font-fraunces)', color: '#1c1520', fontWeight: 400 }}>
                  Check your inbox
                </h1>
                <p className="text-sm leading-relaxed" style={{ color: '#695e6e' }}>
                  We sent a magic link to{' '}
                  <span className="font-medium" style={{ color: '#332b36' }}>{email}</span>.
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
                style={{ color: '#695e6e' }}
              >
                Use a different email
              </button>
            </div>
          ) : (
            <div className="space-y-8">
              <div>
                <h1 className="text-3xl mb-2" style={{ fontFamily: 'var(--font-fraunces)', color: '#1c1520', fontWeight: 400 }}>
                  Welcome back
                </h1>
                <p className="text-sm" style={{ color: '#695e6e' }}>
                  Enter your email to receive a sign-in link.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium tracking-widest uppercase" style={{ color: '#b0a6b4' }}>
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
                      border: '1px solid #e4dee7',
                      color: '#1c1520',
                    }}
                    onFocus={(e) => { e.currentTarget.style.borderColor = '#9b7ec8'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(155,126,200,0.12)' }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = '#e4dee7'; e.currentTarget.style.boxShadow = 'none' }}
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
                  style={{ background: '#1c1520', color: '#ffffff' }}
                  onMouseEnter={(e) => { if (!isSubmitting) e.currentTarget.style.background = '#2e2434' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = '#1c1520' }}
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

              <p className="text-xs text-center" style={{ color: '#b0a6b4' }}>
                No account yet? Just enter your email — we&apos;ll create one.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
