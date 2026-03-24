'use client'

import { useEffect } from 'react'
import { SidebarNav } from '@/components/sidebar'
import { TopBar } from '@/components/top-bar'
import { supabase } from '@/lib/supabase'
import { configureApiAuth } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'
import { useRouter } from 'next/navigation'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { isAuthenticated, loading } = useAuth()
  const router = useRouter()

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
      <SidebarNav />
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
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
