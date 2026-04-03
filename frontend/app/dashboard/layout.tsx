'use client'

import { useEffect, useState } from 'react'
import { SidebarNav } from '@/components/sidebar'
import { supabase } from '@/lib/supabase'
import { configureApiAuth } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { useRouter, usePathname } from 'next/navigation'
import { Menu, X } from 'lucide-react'

// Configure auth at module level so it's ready before any child component
// calls an API in its own useEffect (children's effects run before parent's).
configureApiAuth({
  getAccessToken: async () => {
    const { data: { session } } = await supabase.auth.getSession()
    return session?.access_token ?? null
  },
  onUnauthorized: () => {
    if (typeof window !== 'undefined') window.location.href = '/login'
  },
})

const PAGE_META: Record<string, { title: string; subtitle?: string }> = {
  '/dashboard':              { title: 'Dashboard',    subtitle: 'Overview of your activity' },
  '/dashboard/chat':         { title: 'Chat',         subtitle: 'Message your companion' },
  '/dashboard/values':       { title: 'Values',       subtitle: 'Manage your personal values' },
  '/dashboard/goals':        { title: 'Goals',        subtitle: 'Track your active goals' },
  '/dashboard/transparency': { title: 'Transparency', subtitle: 'ESL audit and decisions' },
  '/dashboard/integrations': { title: 'Integrations', subtitle: 'Connect your apps' },
  '/dashboard/settings':      { title: 'Settings',      subtitle: 'Preferences and privacy' },
  '/dashboard/profile':       { title: 'Profile',       subtitle: 'Your personal information' },
  '/dashboard/notifications': { title: 'Notifications', subtitle: 'Your activity and alerts' },
  '/dashboard/search':        { title: 'Search',        subtitle: 'Find anything' },
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const meta = (() => {
    if (PAGE_META[pathname]) return PAGE_META[pathname]
    if (pathname.startsWith('/dashboard/chat/')) return { title: 'Chat', subtitle: 'Message your companion' }
    return { title: 'Ethic Companion' }
  })()
  const isDev = process.env.NEXT_PUBLIC_ENVIRONMENT === 'development'

  useEffect(() => {
    if (!isDev && !loading && !isAuthenticated) {
      if (typeof window !== 'undefined') {
        localStorage.setItem('ec_lastRoute', window.location.pathname)
      }
      router.push('/login')
    }
  }, [loading, isAuthenticated, router, isDev])

  if (!isDev && loading) return null

  // Close mobile sidebar on route change
  useEffect(() => { setSidebarOpen(false) }, [pathname])

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--ec-page-bg)' }}>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setSidebarOpen(false)} />
          <div className="absolute left-0 top-0 h-full shadow-xl">
            <div className="relative">
              <button
                className="absolute top-3 right-[-40px] w-8 h-8 flex items-center justify-center rounded-full bg-white shadow"
                onClick={() => setSidebarOpen(false)}
                aria-label="Close menu"
              >
                <X size={14} style={{ color: '#1a1a1a' }} />
              </button>
              <SidebarNav onClose={() => setSidebarOpen(false)} />
            </div>
          </div>
        </div>
      )}

      {/* Static sidebar — desktop only */}
      <div className="hidden lg:flex shrink-0">
        <SidebarNav />
      </div>

      {/* Main area */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">

        {/* Top bar */}
        <header
          className="flex items-center gap-3 h-14 px-4 lg:px-6 shrink-0 border-b"
          style={{ background: 'var(--ec-card-bg)', borderColor: 'var(--ec-sidebar-border)' }}
        >
          {/* Mobile hamburger */}
          <button
            aria-label="menu"
            className="lg:hidden w-9 h-9 flex items-center justify-center rounded-lg transition-colors hover:bg-[#f5f5f5]"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={18} style={{ color: '#6b6b6b' }} />
          </button>

          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-semibold leading-none truncate" style={{ color: 'var(--ec-text)' }}>
              {meta.title}
            </h1>
            {meta.subtitle && (
              <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--ec-text-subtle)' }}>{meta.subtitle}</p>
            )}
          </div>

          {/* ESL shield badge */}
          <div
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
            style={{ background: 'var(--ec-surface-2)', color: 'var(--ec-text-muted)', border: '1px solid var(--ec-card-border)' }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#4A7C59]" />
            ESL Active
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1100px] mx-auto px-4 lg:px-6 py-5">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
