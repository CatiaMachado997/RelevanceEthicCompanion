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
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { useAuth } from "@/hooks/useAuth"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

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

export function IconSidebar() {
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

  return (
    <TooltipProvider delayDuration={0}>
      <aside className="hidden md:flex flex-col h-screen w-20 bg-card border-r border-border shrink-0">
        {/* Logo */}
        <div className="flex items-center justify-center h-16 border-b border-border">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[#171717] to-[#525252] shadow-md shadow-none/10 hover:shadow-lg hover:shadow-none/20 transition-all duration-150 hover:scale-105 cursor-pointer">
            <Shield className="h-4 w-4 text-white" />
          </div>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 flex flex-col items-center py-3 space-y-0.5">
          {navItems.map((item) => {
            const active = isActive(item.url)
            return (
              <Tooltip key={item.title}>
                <TooltipTrigger asChild>
                  <Link
                    href={item.url}
                    className={cn(
                      "flex items-center justify-center w-11 h-11 rounded-lg transition-all duration-150 group",
                      active
                        ? "bg-gradient-to-br from-[#171717] to-[#525252] text-white shadow-md shadow-none/20"
                        : "text-foreground hover:bg-muted hover:text-foreground hover:scale-105"
                    )}
                  >
                    <item.icon className={cn(
                      "h-4 w-4 transition-all duration-150",
                      active ? "" : "group-hover:scale-105"
                    )} />
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right" className="font-medium bg-foreground text-white border-muted rounded-lg">
                  {item.title}
                </TooltipContent>
              </Tooltip>
            )
          })}
        </nav>

        {/* Bottom Navigation */}
        <div className="flex flex-col items-center py-3 space-y-0.5 border-t border-border">
          {bottomItems.map((item) => {
            const active = isActive(item.url)
            return (
              <Tooltip key={item.title}>
                <TooltipTrigger asChild>
                  <Link
                    href={item.url}
                    className={cn(
                      "flex items-center justify-center w-11 h-11 rounded-lg transition-all duration-150 group",
                      active
                        ? "bg-gradient-to-br from-[#171717] to-[#525252] text-white shadow-md shadow-none/20"
                        : "text-foreground hover:bg-muted hover:text-foreground hover:scale-105"
                    )}
                  >
                    <item.icon className={cn(
                      "h-4 w-4 transition-all duration-150",
                      active ? "" : "group-hover:scale-105"
                    )} />
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right" className="font-medium bg-foreground text-white border-muted rounded-lg">
                  {item.title}
                </TooltipContent>
              </Tooltip>
            )
          })}

          {/* User Avatar */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                href="/dashboard/profile"
                className="flex items-center justify-center w-11 h-11 rounded-lg transition-all duration-150 hover:bg-muted mt-0.5 hover:scale-105 group"
              >
                <Avatar className="h-8 w-8 ring-2 ring-transparent group-hover:ring-foreground transition-all duration-150">
                  <AvatarFallback className="bg-gradient-to-br from-[#171717] to-[#404040] text-white text-xs font-semibold">
                    {user?.email ? getInitials(user.email) : "U"}
                  </AvatarFallback>
                </Avatar>
              </Link>
            </TooltipTrigger>
            <TooltipContent side="right" className="font-medium bg-foreground text-white border-muted rounded-lg">
              Profile
            </TooltipContent>
          </Tooltip>
        </div>
      </aside>
    </TooltipProvider>
  )
}
