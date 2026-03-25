"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard, MessageSquare, Heart, Target,
  Eye, Plug, Settings, LogOut, Bell, User, Sun, Moon, Search,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/hooks/useAuth"
import { useTheme } from "next-themes"
import { useEffect, useState } from "react"

const NAV_ITEMS = [
  { href: "/dashboard",              label: "Dashboard",    icon: LayoutDashboard, exact: true },
  { href: "/dashboard/chat",         label: "Chat",         icon: MessageSquare },
  { href: "/dashboard/values",       label: "Values",       icon: Heart },
  { href: "/dashboard/goals",        label: "Goals",        icon: Target },
  { href: "/dashboard/transparency", label: "Transparency", icon: Eye },
  { href: "/dashboard/integrations", label: "Integrations", icon: Plug },
  { href: "/dashboard/notifications",label: "Notifications",icon: Bell },
  { href: "/dashboard/search",       label: "Search",        icon: Search },
]

interface SidebarNavProps {
  onClose?: () => void
}

export function SidebarNav({ onClose }: SidebarNavProps = {}) {
  const pathname = usePathname()
  const { signOut, user } = useAuth()
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => { setMounted(true) }, [])

  const initials = user?.email
    ? user.email.split('@')[0].substring(0, 2).toUpperCase()
    : 'U'

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + "/")

  const isDark = resolvedTheme === "dark"

  return (
    <aside
      className="flex flex-col h-screen w-[220px] shrink-0 border-r"
      style={{ background: "var(--ec-sidebar-bg)", borderColor: "var(--ec-sidebar-border)" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 h-14 px-4 border-b shrink-0" style={{ borderColor: "var(--ec-sidebar-border)" }}>
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-bold tracking-tight shrink-0"
          style={{ background: "var(--ec-text)", color: "var(--ec-sidebar-bg)" }}
        >
          EC
        </div>
        <span className="text-sm font-semibold tracking-tight" style={{ color: "var(--ec-text)" }}>
          Ethic Companion
        </span>
      </div>

      {/* Primary nav */}
      <nav className="flex-1 flex flex-col gap-0.5 px-2 py-3 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
          const active = isActive(href, exact)
          return (
            <Link
              key={href}
              href={href}
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 h-9 px-3 rounded-lg text-sm transition-colors duration-100",
                !active && "hover:opacity-80"
              )}
              style={{
                background: active ? "var(--ec-sidebar-active)" : undefined,
                color: active ? "var(--ec-sidebar-text)" : "var(--ec-sidebar-muted)",
                fontWeight: active ? 500 : undefined,
              }}
            >
              <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Bottom section */}
      <div className="px-2 pb-3 border-t pt-3" style={{ borderColor: "var(--ec-sidebar-border)" }}>
        <Link
          href="/dashboard/settings"
          onClick={onClose}
          className={cn(
            "flex items-center gap-3 h-9 px-3 rounded-lg text-sm transition-colors duration-100",
            pathname !== "/dashboard/settings" && "hover:opacity-80"
          )}
          style={{
            background: pathname === "/dashboard/settings" ? "var(--ec-sidebar-active)" : undefined,
            color: pathname === "/dashboard/settings" ? "var(--ec-sidebar-text)" : "var(--ec-sidebar-muted)",
            fontWeight: pathname === "/dashboard/settings" ? 500 : undefined,
          }}
        >
          <Settings size={16} strokeWidth={pathname === "/dashboard/settings" ? 2.2 : 1.8} />
          Settings
        </Link>

        {/* Theme toggle */}
        {mounted && (
          <button
            onClick={() => setTheme(isDark ? "light" : "dark")}
            className="flex items-center gap-3 h-9 px-3 rounded-lg text-sm w-full transition-colors hover:opacity-80"
            style={{ color: "var(--ec-sidebar-muted)" }}
          >
            {isDark ? <Sun size={16} strokeWidth={1.8} /> : <Moon size={16} strokeWidth={1.8} />}
            {isDark ? "Light mode" : "Dark mode"}
          </button>
        )}

        <button
          onClick={() => signOut().catch(console.error)}
          className="flex items-center gap-3 h-9 px-3 rounded-lg text-sm w-full transition-colors hover:opacity-80"
          style={{ color: "var(--ec-sidebar-muted)" }}
        >
          <LogOut size={16} strokeWidth={1.8} />
          Sign out
        </button>

        {/* User row — links to profile */}
        <Link
          href="/dashboard/profile"
          onClick={onClose}
          className="flex items-center gap-2.5 px-3 mt-2 pt-2 border-t transition-opacity hover:opacity-70"
          style={{ borderColor: "var(--ec-sidebar-border)" }}
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
            style={{ background: "var(--ec-text)", color: "var(--ec-sidebar-bg)" }}
          >
            {initials}
          </div>
          <div className="min-w-0">
            <p className="text-xs truncate" style={{ color: "var(--ec-text)" }}>
              {user?.email?.split('@')[0] ?? 'My Account'}
            </p>
            <p className="text-[10px] truncate" style={{ color: "var(--ec-text-subtle)" }}>View profile</p>
          </div>
          <User size={12} className="ml-auto shrink-0" style={{ color: "var(--ec-text-subtle)" }} />
        </Link>
      </div>
    </aside>
  )
}

export function MobileSidebarTrigger() { return null }
