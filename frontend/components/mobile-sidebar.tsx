"use client"

import {
  LayoutDashboard,
  Search,
  MessageSquare,
  Shield,
  Target,
  TrendingUp,
  Settings,
  Bell,
  X,
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { useAuth } from "@/hooks/useAuth"

const navItems = [
  {
    title: "Dashboard",
    url: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    title: "Search",
    url: "/dashboard/search",
    icon: Search,
  },
  {
    title: "Chat",
    url: "/dashboard/chat",
    icon: MessageSquare,
  },
  {
    title: "Values",
    url: "/dashboard/values",
    icon: Shield,
  },
  {
    title: "Goals",
    url: "/dashboard/goals",
    icon: Target,
  },
  {
    title: "Transparency",
    url: "/dashboard/transparency",
    icon: TrendingUp,
  },
]

const bottomItems = [
  {
    title: "Notifications",
    url: "/dashboard/notifications",
    icon: Bell,
  },
  {
    title: "Settings",
    url: "/dashboard/settings",
    icon: Settings,
  },
]

interface MobileSidebarProps {
  open: boolean
  onClose: () => void
}

export function MobileSidebar({ open, onClose }: MobileSidebarProps) {
  const pathname = usePathname()
  const { user } = useAuth()

  const getInitials = (email: string) => {
    return email
      .split("@")[0]
      .substring(0, 2)
      .toUpperCase()
  }

  const isActive = (url: string) => {
    if (url === "/dashboard") {
      return pathname === "/dashboard"
    }
    return pathname.startsWith(url)
  }

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20 md:hidden"
        onClick={onClose}
      />

      {/* Sidebar */}
      <aside className="fixed left-0 top-0 z-50 h-screen w-64 bg-[var(--ec-sidebar-bg)] border-r border-[var(--ec-sidebar-border)] md:hidden">
        {/* Header */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-[var(--ec-sidebar-border)]">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#171717]">
              <Shield className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold text-[var(--ec-text)]">Ethic Companion</span>
          </div>
          <button
            onClick={onClose}
            className="flex items-center justify-center h-8 w-8 rounded-lg text-[var(--ec-text-muted)] hover:bg-[var(--ec-surface-2)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Main Navigation */}
        <nav className="flex flex-col p-4 space-y-1">
          {navItems.map((item) => {
            const active = isActive(item.url)
            return (
              <Link
                key={item.title}
                href={item.url}
                onClick={onClose}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                  active
                    ? "bg-[var(--ec-sidebar-active)] text-[var(--ec-sidebar-text)]"
                    : "text-[var(--ec-text-muted)] hover:bg-[var(--ec-surface-2)] hover:text-[var(--ec-text)]"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.title}
              </Link>
            )
          })}
        </nav>

        {/* Bottom Navigation */}
        <div className="absolute bottom-0 left-0 right-0 border-t border-[var(--ec-sidebar-border)] p-4 space-y-1">
          {bottomItems.map((item) => {
            const active = isActive(item.url)
            return (
              <Link
                key={item.title}
                href={item.url}
                onClick={onClose}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                  active
                    ? "bg-[var(--ec-sidebar-active)] text-[var(--ec-sidebar-text)]"
                    : "text-[var(--ec-text-muted)] hover:bg-[var(--ec-surface-2)] hover:text-[var(--ec-text)]"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.title}
              </Link>
            )
          })}

          {/* User Profile */}
          <Link
            href="/dashboard/profile"
            onClick={onClose}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
              pathname === "/dashboard/profile"
                ? "bg-[#171717] text-white"
                : "text-[#525252] hover:bg-[#FAFAFA] hover:text-[#171717]"
            )}
          >
            <Avatar className="h-6 w-6">
              <AvatarFallback className="bg-[#171717] text-white text-xs font-semibold">
                {user?.email ? getInitials(user.email) : "U"}
              </AvatarFallback>
            </Avatar>
            Profile
          </Link>
        </div>
      </aside>
    </>
  )
}
