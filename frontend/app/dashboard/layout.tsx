'use client'

import { useEffect, useState } from 'react'
import { SidebarNav } from '@/components/sidebar'
import { TopBar } from '@/components/top-bar'
import { supabase } from '@/lib/supabase'
import { configureApiAuth } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { useRouter } from 'next/navigation'
import { Menu } from 'lucide-react'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { isAuthenticated, loading } = useAuth()
  const router = useRouter()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    configureApiAuth({
      getAccessToken: async () => {
        const { data: { session } } = await supabase.auth.getSession()
        return session?.access_token ?? null
      },
      onUnauthorized: () => {
        window.location.href = '/login'
      },
    })
  }, [])

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/login')
    }
  }, [loading, isAuthenticated, router])

  if (loading) return null

  return (
    <div className="flex h-screen" style={{ background: '#ffffff' }}>
      {/* Mobile overlay sidebar */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setSidebarOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-64 bg-white shadow-xl">
            <SidebarNav onClose={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}

      {/* Static sidebar — hidden on mobile */}
      <div className="hidden lg:flex">
        <SidebarNav />
      </div>

      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        {/* Mobile hamburger button */}
        <div className="lg:hidden flex items-center px-4 py-2 border-b border-black/5">
          <button
            aria-label="menu"
            className="lg:hidden p-2 rounded-lg hover:bg-black/5"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={20} />
          </button>
        </div>
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1100px] mx-auto px-8 py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
