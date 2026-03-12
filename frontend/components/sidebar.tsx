"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  MessageSquare,
  Heart,
  Target,
  Eye,
  Shield,
} from "lucide-react"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/chat", label: "Chat", icon: MessageSquare },
  { href: "/dashboard/values", label: "Values", icon: Heart },
  { href: "/dashboard/goals", label: "Goals", icon: Target },
  { href: "/dashboard/transparency", label: "Transparency", icon: Eye },
]

export function SidebarNav() {
  const pathname = usePathname()
  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + "/")

  return (
    <aside
      className="flex flex-col h-screen w-16 shrink-0 border-r"
      style={{ background: "#fafafa", borderColor: "rgba(0,0,0,0.08)" }}
    >
      {/* Logo */}
      <div
        className="flex items-center justify-center h-14 shrink-0 border-b"
        style={{ borderColor: "rgba(0,0,0,0.08)" }}
      >
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold"
          style={{
            background: "#000000",
            color: "#ffffff",
          }}
        >
          EC
        </div>
      </div>

      {/* Nav items */}
      <nav className="flex-1 flex flex-col items-center gap-1 py-3">
        {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
          const active = isActive(href, exact)
          return (
            <Link
              key={href}
              href={href}
              title={label}
              className={cn(
                "w-11 h-11 rounded-xl flex items-center justify-center transition-colors duration-150",
                active ? "" : "hover:bg-black/5"
              )}
              style={{
                background: active ? "rgba(0,0,0,0.08)" : undefined,
                color: active ? "#000000" : "#9e9e9e",
              }}
            >
              <Icon size={18} />
            </Link>
          )
        })}
      </nav>

      {/* Bottom */}
      <div
        className="flex flex-col items-center gap-3 pb-4 border-t pt-3"
        style={{ borderColor: "rgba(0,0,0,0.08)" }}
      >
        <button
          title="Security"
          className="w-11 h-11 rounded-xl flex items-center justify-center hover:bg-black/5 transition-colors"
          style={{ color: "#9e9e9e" }}
        >
          <Shield size={18} />
        </button>
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold"
          style={{ background: "#0a0a0a", color: "#ffffff" }}
        >
          U
        </div>
      </div>
    </aside>
  )
}

export function MobileSidebarTrigger() {
  return null
}
