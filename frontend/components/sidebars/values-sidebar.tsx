"use client"

import {
  SecondarySidebar,
  SecondarySidebarSection,
  SecondarySidebarNavItem,
} from "@/components/secondary-sidebar"
import { Button } from "@/components/ui/button"
import { Plus, Shield, Heart, Filter, Clock } from "lucide-react"

const VALUE_TYPES = [
  { type: "boundary", label: "Boundaries", icon: Shield },
  { type: "preference", label: "Preferences", icon: Heart },
  { type: "topic_filter", label: "Topic Filters", icon: Filter },
  { type: "time_window", label: "Time Windows", icon: Clock },
] as const

interface ValuesSidebarProps {
  filter: string | null
  onFilterChange: (filter: string | null) => void
  counts?: Record<string, number>
  onAddValue?: () => void
}

export function ValuesSidebar({
  filter,
  onFilterChange,
  counts = {},
  onAddValue,
}: ValuesSidebarProps) {
  const totalCount = Object.values(counts).reduce((a, b) => a + b, 0)

  return (
    <SecondarySidebar
      title="My Values"
      action={
        <Button
          size="sm"
          className="rounded-full bg-[#171717] hover:bg-[#4338CA]"
          onClick={onAddValue}
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Value
        </Button>
      }
      showSearch
      searchPlaceholder="Search values..."
    >
      <SecondarySidebarSection title="Categories">
        <div className="space-y-1">
          <SecondarySidebarNavItem
            label="All Values"
            count={totalCount}
            isActive={filter === null}
            onClick={() => onFilterChange(null)}
          />
          {VALUE_TYPES.map(({ type, label, icon }) => (
            <SecondarySidebarNavItem
              key={type}
              icon={icon}
              label={label}
              count={counts[type] || 0}
              isActive={filter === type}
              onClick={() => onFilterChange(type)}
            />
          ))}
        </div>
      </SecondarySidebarSection>

      <SecondarySidebarSection title="About Values">
        <div className="space-y-3 text-sm text-[#171717]">
          <p>
            <strong className="text-[#171717]">Boundaries</strong> are strict limits that the AI will never cross.
          </p>
          <p>
            <strong className="text-[#171717]">Preferences</strong> guide the AI&apos;s behavior but can be adjusted.
          </p>
          <p>
            <strong className="text-[#171717]">Topic Filters</strong> block specific subjects from conversations.
          </p>
          <p>
            <strong className="text-[#171717]">Time Windows</strong> define when certain actions are allowed.
          </p>
        </div>
      </SecondarySidebarSection>
    </SecondarySidebar>
  )
}
