"use client"

import {
  SecondarySidebar,
  SecondarySidebarSection,
  SecondarySidebarNavItem,
} from "@/components/secondary-sidebar"
import { Button } from "@/components/ui/button"
import { Plus, Target, CheckCircle2, Pause, Archive } from "lucide-react"

const STATUS_OPTIONS = [
  { status: "active", label: "Active", icon: Target },
  { status: "completed", label: "Completed", icon: CheckCircle2 },
  { status: "paused", label: "Paused", icon: Pause },
  { status: "archived", label: "Archived", icon: Archive },
] as const

interface GoalsSidebarProps {
  filter: string | null
  onFilterChange: (filter: string | null) => void
  counts?: Record<string, number>
  onAddGoal?: () => void
}

export function GoalsSidebar({
  filter,
  onFilterChange,
  counts = {},
  onAddGoal,
}: GoalsSidebarProps) {
  const totalCount = Object.values(counts).reduce((a, b) => a + b, 0)

  return (
    <SecondarySidebar
      title="Goals"
      action={
        <Button
          size="sm"
          className="rounded-full bg-[#171717] hover:bg-[#4338CA]"
          onClick={onAddGoal}
        >
          <Plus className="h-4 w-4 mr-2" />
          New Goal
        </Button>
      }
      showSearch
      searchPlaceholder="Search goals..."
    >
      <SecondarySidebarSection title="Status">
        <div className="space-y-1">
          <SecondarySidebarNavItem
            label="All Goals"
            count={totalCount}
            isActive={filter === null}
            onClick={() => onFilterChange(null)}
          />
          {STATUS_OPTIONS.map(({ status, label, icon }) => (
            <SecondarySidebarNavItem
              key={status}
              icon={icon}
              label={label}
              count={counts[status] || 0}
              isActive={filter === status}
              onClick={() => onFilterChange(status)}
            />
          ))}
        </div>
      </SecondarySidebarSection>

      <SecondarySidebarSection title="Tips">
        <div className="space-y-3 text-sm text-[#171717]">
          <p>
            Set <strong className="text-[#171717]">clear, measurable goals</strong> with specific target dates.
          </p>
          <p>
            Use <strong className="text-[#171717]">priority levels</strong> to focus on what matters most.
          </p>
          <p>
            <strong className="text-[#171717]">Archive</strong> completed goals to keep your list focused.
          </p>
        </div>
      </SecondarySidebarSection>
    </SecondarySidebar>
  )
}
