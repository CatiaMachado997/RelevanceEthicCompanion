"use client"

import { createContext, useContext, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  MessageSquare,
  Heart,
  Target,
  Eye,
  ChevronLeft,
  ChevronRight,
  Menu,
} from "lucide-react"
import { cn } from "@/lib/utils"

// --- Context ---

type SidebarCtx = { collapsed: boolean; toggle: () => void }
const SidebarContext = createContext<SidebarCtx>({ collapsed: false, toggle: () => {} })
export const useSidebar = () => useContext(SidebarContext)

// --- Nav config ---

const NAV = [
  {
    section: "Main",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
      { href: "/dashboard/chat", label: "Chat", icon: MessageSquare },
    ],
  },
  {
    section: "Manage",
    items: [
      { href: "/dashboard/values", label: "Values", icon: Heart },
      { href: "/dashboard/goals", label: "Goals", icon: Target },
    ],
  },
  {
    section: "Insights",
    items: [
      { href: "/dashboard/transparency", label: "Transparency", icon: Eye },
    ],
  },
]

// --- Provider (wraps layout) ---

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  return (
    <SidebarContext.Provider value={{ collapsed, toggle: () => setCollapsed(v => !v) }}>
      {children}
    </SidebarContext.Provider>
  )
}

// --- Sidebar nav ---

export function SidebarNav() {
  const { collapsed, toggle } = useSidebar()
  const pathname = usePathname()

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + "/")

  return (
    <aside
      className={cn(
        "relative flex flex-col h-screen shrink-0 transition-all duration-200 ease-in-out",
        "border-r border-black/5",
        collapsed ? "w-16" : "w-60"
      )}
      style={{ background: "#F2EDE8" }}
    >
      {/* Logo */}
      <div
        className={cn(
          "flex items-center h-14 border-b border-black/5 shrink-0",
          collapsed ? "justify-center px-0" : "px-5"
        )}
      >
        {collapsed ? (
          <span className="text-sm font-bold" style={{ color: "#C2714F" }}>EC</span>
        ) : (
          <span className="text-sm font-semibold tracking-tight" style={{ color: "#1C1917" }}>
            Ethic Companion
          </span>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-3">
        {NAV.map(({ section, items }) => (
          <div key={section} className="mb-3">
            {!collapsed && (
              <p
                className="px-5 mb-1 text-[11px] font-medium uppercase tracking-[0.08em]"
                style={{ color: "#A8A29E" }}
              >
                {section}
              </p>
            )}
            {items.map(({ href, label, icon: Icon, exact }) => {
              const active = isActive(href, exact)
              return (
                <Link
                  key={href}
                  href={href}
                  title={collapsed ? label : undefined}
                  className={cn(
                    "flex items-center gap-3 mx-2 py-2 rounded-lg text-sm transition-colors duration-150",
                    collapsed ? "justify-center px-2" : "px-3",
                    active
                      ? "font-medium border-l-2 rounded-l-none"
                      : "hover:bg-black/5"
                  )}
                  style={
                    active
                      ? {
                          background: "rgba(194,113,79,0.10)",
                          borderColor: "#C2714F",
                          color: "#C2714F",
                        }
                      : { color: "#78716C" }
                  }
                >
                  <Icon size={17} className="shrink-0" />
                  {!collapsed && <span>{label}</span>}
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggle}
        className="absolute -right-3 top-[68px] z-10 w-6 h-6 rounded-full flex items-center justify-center transition-colors duration-150"
        style={{
          background: "#FFFFFF",
          border: "1px solid rgba(0,0,0,0.10)",
          boxShadow: "0 1px 3px rgba(0,0,0,0.12)",
        }}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed
          ? <ChevronRight size={11} style={{ color: "#78716C" }} />
          : <ChevronLeft size={11} style={{ color: "#78716C" }} />
        }
      </button>

      {/* User slot */}
      <div
        className={cn(
          "flex items-center gap-3 border-t border-black/5 shrink-0",
          collapsed ? "justify-center p-3" : "px-5 py-4"
        )}
      >
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold"
          style={{ background: "rgba(194,113,79,0.15)", color: "#C2714F" }}
        >
          U
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-sm font-medium truncate" style={{ color: "#1C1917" }}>User</p>
            <p className="text-xs truncate" style={{ color: "#78716C" }}>Active</p>
          </div>
        )}
      </div>
    </aside>
  )
}

// --- Mobile trigger ---

export function MobileSidebarTrigger() {
  return (
    <button className="md:hidden p-2 rounded-lg" style={{ color: "#78716C" }}>
      <Menu size={20} />
    </button>
  )
}
