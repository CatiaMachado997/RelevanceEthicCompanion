'use client'

import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { Shield, Mail } from 'lucide-react'

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
      setError(err instanceof Error ? err.message : 'Sign in failed. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-4">
      <div className="w-full max-w-md rounded-2xl border border-[#e4dee7] bg-white shadow-[0_4px_24px_rgba(42,34,45,0.08)] p-8">
        <div className="flex flex-col items-center gap-4 mb-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#2a222d]">
            <Shield className="h-6 w-6 text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-tight text-[#332b36]">Welcome back</h1>
            <p className="text-sm text-[#695e6e] mt-1">
              Enter your email to sign in to your Ethic Companion
            </p>
          </div>
        </div>

        {sent ? (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <Mail className="h-10 w-10 text-[#332b36]" />
            <p className="text-sm font-medium text-[#332b36]">Check your email</p>
            <p className="text-xs text-[#695e6e]">
              We sent a magic link to <strong>{email}</strong>. Click it to sign in.
            </p>
            <button
              onClick={() => { setSent(false); setEmail('') }}
              className="text-xs text-[#695e6e] underline mt-2"
            >
              Use a different email
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">
                Email
              </label>
              <input
                type="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isSubmitting}
                className="h-10 w-full rounded-xl border border-[#e4dee7] bg-white px-3 text-sm text-[#332b36] placeholder:text-[#b0a6b4] focus:border-[#332b36] focus:outline-none focus:ring-1 focus:ring-[#332b36] disabled:opacity-50"
              />
            </div>
            {error && <p className="text-xs text-red-500">{error}</p>}
            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-2 h-10 w-full rounded-[14px] bg-[#332b36] text-white text-sm font-medium transition-opacity hover:opacity-80 disabled:opacity-50"
            >
              {isSubmitting ? 'Sending link...' : 'Send Magic Link'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
