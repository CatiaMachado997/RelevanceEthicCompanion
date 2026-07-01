'use client'

import { Shield, ArrowRight } from 'lucide-react'
import Link from 'next/link'

export default function LandingPage() {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-4 sm:p-6 text-center"
      style={{ background: '#f2f2f2' }}
    >
      {/* Logo — matches login page */}
      <div className="flex items-center gap-2.5 mb-10">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ background: '#111111' }}
        >
          <Shield size={18} color="white" />
        </div>
        <span className="text-lg font-semibold tracking-tight" style={{ color: '#111111' }}>
          Ethic Companion
        </span>
      </div>

      {/* Tagline */}
      <h1
        className="text-3xl sm:text-4xl leading-tight mb-2 max-w-md"
        style={{ color: '#111111', fontWeight: 400, fontFamily: 'var(--font-fraunces)' }}
      >
        Your AI work companion
      </h1>
      <p
        className="text-lg sm:text-xl leading-snug mb-10 max-w-md"
        style={{ color: '#555555', fontFamily: 'var(--font-fraunces)', fontWeight: 300 }}
      >
        that respects your boundaries.
      </p>

      {/* CTA */}
      <Link
        href="/login"
        className="inline-flex items-center gap-2 h-11 px-8 rounded-lg text-sm font-medium transition-all hover:opacity-90 active:scale-[0.98]"
        style={{ background: '#4a7c59', color: '#ffffff' }}
      >
        Sign in
        <ArrowRight size={15} />
      </Link>

      {/* Trust note */}
      <p className="mt-5 text-xs max-w-xs" style={{ color: '#777777' }}>
        No passwords needed — we use integrations and magic links.
      </p>
    </div>
  )
}
