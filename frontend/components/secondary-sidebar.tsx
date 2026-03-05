"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { Search } from "lucide-react"

interface SecondarySidebarProps {
  title: string
  action?: React.ReactNode
  searchPlaceholder?: string
  onSearch?: (value: string) => void
  showSearch?: boolean
  children: React.ReactNode
  footer?: React.ReactNode
  className?: string
}

export function SecondarySidebar({
  title,
  action,
  searchPlaceholder = "Search...",
  onSearch,
  showSearch = false,
  children,
  footer,
  className,
}: SecondarySidebarProps) {
  return (
    <aside
      className={cn(
        "hidden lg:flex flex-col h-screen w-80 bg-white border-r border-[#E5E5E5] shrink-0",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 h-20 border-b border-[#E5E5E5]">
        <h2 className="text-lg font-semibold text-[#171717]">{title}</h2>
        {action}
      </div>

      {/* Search */}
      {showSearch && (
        <div className="px-4 py-3 border-b border-[#E5E5E5]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#A3A3A3]" />
            <Input
              placeholder={searchPlaceholder}
              onChange={(e) => onSearch?.(e.target.value)}
              className="pl-10 bg-[#FAFAFA] border-[#E5E5E5] rounded-full h-10"
            />
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {children}
      </div>

      {/* Footer */}
      {footer && (
        <div className="px-4 py-4 border-t border-[#E5E5E5]">
          {footer}
        </div>
      )}
    </aside>
  )
}

// Reusable section header within secondary sidebar
export function SecondarySidebarSection({
  title,
  action,
  children,
  className,
}: {
  title?: string
  action?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("mb-6", className)}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-3">
          {title && (
            <h3 className="text-xs font-semibold text-[#171717] uppercase tracking-wider">
              {title}
            </h3>
          )}
          {action}
        </div>
      )}
      {children}
    </div>
  )
}

// Navigation item for secondary sidebar
export function SecondarySidebarNavItem({
  icon: Icon,
  label,
  count,
  isActive,
  onClick,
}: {
  icon?: React.ComponentType<{ className?: string }>
  label: string
  count?: number
  isActive?: boolean
  onClick?: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center justify-between w-full px-3 py-2.5 rounded-lg text-sm transition-all duration-150",
        isActive
          ? "bg-[#171717]/10 text-[#171717] font-medium"
          : "text-[#525252] hover:bg-[#F5F5F5]"
      )}
    >
      <div className="flex items-center gap-3">
        {Icon && <Icon className="h-4 w-4" />}
        <span>{label}</span>
      </div>
      {count !== undefined && (
        <span
          className={cn(
            "text-xs font-medium px-2 py-0.5 rounded-full",
            isActive ? "bg-[#171717] text-white" : "bg-[#F5F5F5] text-[#171717]"
          )}
        >
          {count}
        </span>
      )}
    </button>
  )
}

// Promo card for secondary sidebar footer
export function SecondarySidebarPromo({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="bg-gradient-to-br from-[#171717] to-[#171717] rounded-lg p-4 text-white">
      <h4 className="font-semibold text-sm mb-1">{title}</h4>
      <p className="text-xs text-white/80 mb-3">{description}</p>
      {action}
    </div>
  )
}
