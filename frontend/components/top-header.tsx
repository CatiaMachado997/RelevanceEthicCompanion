"use client"

import { useState } from "react"
import { usePathname } from "next/navigation"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/useAuth"
import { Share2, ChevronRight, Menu } from "lucide-react"
import Link from "next/link"
import { MobileSidebar } from "./mobile-sidebar"

const breadcrumbMap: Record<string, { label: string; parent?: string }> = {
  "/dashboard": { label: "Dashboard" },
  "/dashboard/search": { label: "Search", parent: "/dashboard" },
  "/dashboard/chat": { label: "Chat", parent: "/dashboard" },
  "/dashboard/values": { label: "My Values", parent: "/dashboard" },
  "/dashboard/goals": { label: "Goals", parent: "/dashboard" },
  "/dashboard/transparency": { label: "Transparency", parent: "/dashboard" },
  "/dashboard/settings": { label: "Settings", parent: "/dashboard" },
  "/dashboard/profile": { label: "Profile", parent: "/dashboard" },
  "/dashboard/notifications": { label: "Notifications", parent: "/dashboard" },
}

function getBreadcrumbs(pathname: string) {
  const crumbs: { label: string; href: string }[] = []
  let current = pathname

  while (current && breadcrumbMap[current]) {
    const { label, parent } = breadcrumbMap[current]
    crumbs.unshift({ label, href: current })
    current = parent || ""
  }

  return crumbs
}

export function TopHeader() {
  const pathname = usePathname()
  const { user } = useAuth()
  const breadcrumbs = getBreadcrumbs(pathname)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const getInitials = (email: string) => {
    return email
      .split("@")[0]
      .substring(0, 2)
      .toUpperCase()
  }

  const now = new Date()
  const timeString = now.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  })

  return (
    <>
      <header className="flex items-center justify-between h-16 px-4 md:px-6 bg-card border-b border-border">
        {/* Mobile Menu Button */}
        <button
          onClick={() => setMobileMenuOpen(true)}
          className="md:hidden flex items-center justify-center h-8 w-8 rounded-lg text-muted-foreground hover:bg-muted"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Left: User greeting and breadcrumbs */}
        <div className="flex items-center gap-3 md:gap-4">
          <Avatar className="hidden md:flex h-9 w-9">
            <AvatarFallback className="bg-foreground text-white text-sm font-semibold">
              {user?.email ? getInitials(user.email) : "U"}
            </AvatarFallback>
          </Avatar>
          <div className="flex flex-col">
            <span className="text-sm font-medium text-foreground">
              {user?.email?.split("@")[0] || "User"}
            </span>
            {/* Breadcrumbs - hidden on mobile */}
            <nav className="hidden md:flex items-center text-xs text-muted-foreground">
              {breadcrumbs.map((crumb, index) => (
                <span key={crumb.href} className="flex items-center">
                  {index > 0 && <ChevronRight className="h-3 w-3 mx-1" />}
                  {index === breadcrumbs.length - 1 ? (
                    <span className="text-foreground font-medium">{crumb.label}</span>
                  ) : (
                    <Link href={crumb.href} className="hover:text-foreground transition-colors">
                      {crumb.label}
                    </Link>
                  )}
                </span>
              ))}
            </nav>
          </div>
        </div>

        {/* Right: Time and ESL status */}
        <div className="flex items-center gap-2 md:gap-4">
          <span className="hidden sm:block text-sm text-muted-foreground">{timeString}</span>
          <span className="inline-flex items-center rounded-full border border-[#BFDBFE] bg-gradient-to-r from-[#EFF6FF] to-[#DBEAFE] px-2 md:px-2.5 py-1 text-xs font-semibold text-muted-foreground shadow-md hover:shadow-md transition-all duration-150">
            <span className="mr-1 md:mr-1.5 h-1.5 w-1.5 rounded-full bg-foreground animate-pulse shadow-md shadow-none/50" />
            <span className="hidden sm:inline">ESL Active</span>
            <span className="sm:hidden">ESL</span>
          </span>
        </div>
      </header>

      {/* Mobile Sidebar */}
      <MobileSidebar open={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} />
    </>
  )
}
