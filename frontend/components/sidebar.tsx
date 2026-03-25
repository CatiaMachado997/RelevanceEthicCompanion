"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard, MessageSquare, Heart, Target,
  Eye, Plug, Settings, LogOut, Bell, User,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/hooks/useAuth"

const NAV_ITEMS = [
  { href: "/dashboard",              label: "Dashboard",    icon: LayoutDashboard, exact: true },
  { href: "/dashboard/chat",         label: "Chat",         icon: MessageSquare },
  { href: "/dashboard/values",       label: "Values",       icon: Heart },
  { href: "/dashboard/goals",        label: "Goals",        icon: Target },
  { href: "/dashboard/transparency", label: "Transparency", icon: Eye },
  { href: "/dashboard/integrations", label: "Integrations", icon: Plug },
  { href: "/dashboard/notifications",label: "Notifications",icon: Bell },
]

interface SidebarNavProps {
  onClose?: () => void
}

export function SidebarNav({ onClose }: SidebarNavProps = {}) {
  const pathname = usePathname()
  const { signOut, user } = useAuth()

  const initials = user?.email
    ? user.email.split('@')[0].substring(0, 2).toUpperCase()
    : 'U'

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + "/")

  return (
    <aside
      className="flex flex-col h-screen w-[220px] shrink-0 border-r"
      style={{ background: "#ffffff", borderColor: "#e8e8e8" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 h-14 px-4 border-b shrink-0" style={{ borderColor: "#e8e8e8" }}>
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-bold tracking-tight shrink-0"
          style={{ background: "#1a1a1a", color: "#ffffff" }}
        >
          EC
        </div>
        <span className="text-sm font-semibold tracking-tight" style={{ color: "#1a1a1a" }}>
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
                active
                  ? "font-medium"
                  : "hover:bg-[#f5f5f5]"
              )}
              style={{
                background: active ? "#f0f0f0" : undefined,
                color: active ? "#1a1a1a" : "#6b6b6b",
              }}
            >
              <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Bottom section */}
      <div className="px-2 pb-3 border-t pt-3" style={{ borderColor: "#e8e8e8" }}>
        <Link
          href="/dashboard/settings"
          onClick={onClose}
          className={cn(
            "flex items-center gap-3 h-9 px-3 rounded-lg text-sm transition-colors duration-100",
            pathname === "/dashboard/settings" ? "font-medium" : "hover:bg-[#f5f5f5]"
          )}
          style={{
            background: pathname === "/dashboard/settings" ? "#f0f0f0" : undefined,
            color: pathname === "/dashboard/settings" ? "#1a1a1a" : "#6b6b6b",
          }}
        >
          <Settings size={16} strokeWidth={pathname === "/dashboard/settings" ? 2.2 : 1.8} />
          Settings
        </Link>
        <button
          onClick={() => signOut().catch(console.error)}
          className="flex items-center gap-3 h-9 px-3 rounded-lg text-sm w-full transition-colors hover:bg-[#f5f5f5]"
          style={{ color: "#6b6b6b" }}
        >
          <LogOut size={16} strokeWidth={1.8} />
          Sign out
        </button>

        {/* User row — links to profile */}
        <Link
          href="/dashboard/profile"
          onClick={onClose}
          className="flex items-center gap-2.5 px-3 mt-2 pt-2 border-t transition-opacity hover:opacity-70"
          style={{ borderColor: "#e8e8e8" }}
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
            style={{ background: "#1a1a1a", color: "#ffffff" }}
          >
            {initials}
          </div>
          <div className="min-w-0">
            <p className="text-xs truncate" style={{ color: "#1a1a1a" }}>
              {user?.email?.split('@')[0] ?? 'My Account'}
            </p>
            <p className="text-[10px] truncate" style={{ color: "#9e9e9e" }}>View profile</p>
          </div>
          <User size={12} className="ml-auto shrink-0" style={{ color: "#c0c0c0" }} />
        </Link>
      </div>
    </aside>
  )
}

export function MobileSidebarTrigger() { return null }
