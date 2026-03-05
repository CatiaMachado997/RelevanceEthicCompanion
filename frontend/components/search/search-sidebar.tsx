"use client"

import * as React from "react"
import {
  Search,
  Home,
  Compass,
  BookOpen,
  ChevronDown,
  ChevronUp,
  PenSquare,
  Smartphone,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

interface ChatHistoryItem {
  id: string
  title: string
  isActive?: boolean
}

const mockChatHistory: ChatHistoryItem[] = [
  { id: "1", title: "Hacking FBI server with raspberry pie" },
  { id: "2", title: "COMPsci SICP tutorial course" },
  { id: "3", title: "Proxy failure troubleshooting", isActive: true },
  { id: "4", title: "Wake me up when september ends chord" },
  { id: "5", title: "Best OASIS songs top 100 all time" },
  { id: "6", title: "Fix SSL/TLS Error" },
  { id: "7", title: "React component quick fix" },
  { id: "8", title: "Nextjs 18 documentations" },
  { id: "9", title: "How to get healthy in 1 hour" },
]

interface NavItemProps {
  icon: React.ElementType
  label: string
  isExpanded?: boolean
  onToggle?: () => void
  children?: React.ReactNode
}

function NavItem({ icon: Icon, label, isExpanded, onToggle, children }: NavItemProps) {
  const hasChildren = Boolean(children)

  if (!hasChildren) {
    return (
      <button
        onClick={() => console.log(`Navigate to ${label}`)}
        className="flex w-full items-center gap-3 px-6 py-4 text-lg font-bold text-[#404040] transition-colors hover:bg-[#F5F5F5]"
      >
        <Icon className="h-6 w-6 text-[#525252]" />
        <span className="flex-1 text-left">{label}</span>
        <ChevronDown className="h-6 w-6 text-[#A3A3A3]" />
      </button>
    )
  }

  return (
    <Collapsible open={isExpanded} onOpenChange={onToggle}>
      <CollapsibleTrigger className="flex w-full items-center gap-3 px-6 py-4 text-lg font-bold text-[#404040] transition-colors hover:bg-[#F5F5F5]">
        <Icon className="h-6 w-6 text-[#525252]" />
        <span className="flex-1 text-left">{label}</span>
        {isExpanded ? (
          <ChevronUp className="h-6 w-6 text-[#A3A3A3]" />
        ) : (
          <ChevronDown className="h-6 w-6 text-[#A3A3A3]" />
        )}
      </CollapsibleTrigger>
      <CollapsibleContent>{children}</CollapsibleContent>
    </Collapsible>
  )
}

export function SearchSidebar() {
  const [searchValue, setSearchValue] = React.useState("")
  const [isLibraryExpanded, setIsLibraryExpanded] = React.useState(true)

  return (
    <div className="flex h-full w-[320px] flex-col border-r border-[#E5E5E5] bg-[#FAFAFA]">
      {/* Header Section */}
      <div className="flex flex-col justify-center gap-4 border-b border-[#E5E5E5] px-6 py-8">
        {/* Title & New Chat Button */}
        <div className="flex items-center gap-2">
          <span className="flex-1 text-2xl font-bold tracking-tight text-[#404040]">
            Ethic Companion
          </span>
          <button className="flex h-10 w-10 items-center justify-center rounded-full border border-[#E5E5E5] transition-colors hover:bg-white">
            <PenSquare className="h-6 w-6 text-[#525252]" />
          </button>
        </div>

        {/* Search Input */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search..."
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            className="h-10 w-full rounded-full border border-[#E5E5E5] bg-white px-4 pr-10 text-base text-[#525252] placeholder:text-[#525252] focus:border-[#171717] focus:outline-none focus:ring-2 focus:ring-[#171717]/20"
          />
          <Search className="absolute right-3 top-1/2 h-5 w-5 -translate-y-1/2 text-[#525252]" />
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto pt-4">
        <NavItem icon={Home} label="Home" />
        <NavItem icon={Compass} label="Discover" />
        <NavItem
          icon={BookOpen}
          label="Library"
          isExpanded={isLibraryExpanded}
          onToggle={() => setIsLibraryExpanded(!isLibraryExpanded)}
        >
          <div className="flex flex-col py-2 pl-9 pr-6">
            {mockChatHistory.map((item) => (
              <button
                key={item.id}
                onClick={() => console.log(`Open chat: ${item.title}`)}
                className={cn(
                  "truncate border-l py-2 pl-4 text-left text-base font-medium text-[#525252] transition-colors hover:text-[#404040]",
                  item.isActive
                    ? "border-l-2 border-[#171717]"
                    : "border-[#A3A3A3]"
                )}
              >
                {item.title}
              </button>
            ))}
          </div>
        </NavItem>
      </nav>

      {/* Promo Card */}
      <div className="p-6">
        <div className="rounded-3xl border border-[#E5E5E5] bg-white p-4">
          <div className="mb-4 flex items-start gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#F5F5F5]">
              <Smartphone className="h-5 w-5 text-[#525252]" />
            </div>
            <button className="text-[#A3A3A3] hover:text-[#525252]">
              <X className="h-5 w-5" />
            </button>
          </div>
          <p className="mb-4 text-sm leading-relaxed text-[#525252]">
            Enjoy unlimited access to our app with only a small price monthly.
          </p>
          <div className="flex items-center gap-4">
            <button className="text-sm font-bold text-[#525252] hover:text-[#404040]">
              Dismiss
            </button>
            <button className="text-sm font-bold text-[#171717] hover:text-[#4338CA]">
              Subscribe now
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
