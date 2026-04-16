'use client'

import { Shield, ArrowRight } from 'lucide-react'
import Link from 'next/link'

export default function LandingPage() {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-6 text-center"
      style={{ background: '#fafafa' }}
    >
      {/* Logo */}
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center mb-8"
        style={{ background: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)' }}
      >
        <Shield size={24} color="white" />
      </div>

      {/* Wordmark */}
      <p className="text-xs font-medium uppercase tracking-[0.2em] mb-4" style={{ color: '#9e9e9e' }}>
        Ethic Companion
      </p>

      {/* Tagline */}
      <h1
        className="text-3xl sm:text-4xl mb-4 max-w-sm leading-tight"
        style={{ color: '#1a1a1a', fontWeight: 400, fontFamily: 'var(--font-fraunces)' }}
      >
        Your AI work companion that respects your boundaries.
      </h1>

      {/* Description */}
      <p className="text-sm leading-relaxed max-w-xs mb-10" style={{ color: '#6b6b6b' }}>
        Ethic Companion helps you make decisions, manage work, and stay focused — without dark patterns or engagement traps. Powered by an Ethical Safeguard Layer that puts your values first.
      </p>

      {/* CTA */}
      <Link
        href="/login"
        className="inline-flex items-center gap-2 w-full sm:w-auto justify-center h-12 px-8 rounded-2xl text-sm font-medium transition-all hover:opacity-90 active:scale-[0.98]"
        style={{ background: '#1a1a1a', color: '#ffffff' }}
      >
        Sign in
        <ArrowRight size={15} />
      </Link>

      {/* Trust note */}
      <p className="mt-6 text-xs" style={{ color: '#c4bcc8' }}>
        No password needed — we use magic links.
      </p>
    </div>
  )
}
