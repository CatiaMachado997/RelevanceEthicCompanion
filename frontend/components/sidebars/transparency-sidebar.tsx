"use client"

import {
  SecondarySidebar,
  SecondarySidebarSection,
  SecondarySidebarNavItem,
  SecondarySidebarPromo,
} from "@/components/secondary-sidebar"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { CheckCircle2, XCircle, FileEdit, Activity } from "lucide-react"

interface TransparencySidebarProps {
  days: string
  onDaysChange: (days: string) => void
  statusFilter: string | null
  onStatusFilterChange: (status: string | null) => void
  counts?: {
    total: number
    approved: number
    vetoed: number
    modified: number
  }
}

export function TransparencySidebar({
  days,
  onDaysChange,
  statusFilter,
  onStatusFilterChange,
  counts = { total: 0, approved: 0, vetoed: 0, modified: 0 },
}: TransparencySidebarProps) {
  return (
    <SecondarySidebar
      title="Transparency"
      footer={
        <SecondarySidebarPromo
          title="Full Visibility"
          description="Every AI decision is logged and explained for your review."
        />
      }
    >
      <SecondarySidebarSection title="Time Period">
        <Select value={days} onValueChange={onDaysChange}>
          <SelectTrigger className="w-full bg-[#FAFAFA] border-[#E5E5E5]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="14">Last 14 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
          </SelectContent>
        </Select>
      </SecondarySidebarSection>

      <SecondarySidebarSection title="Filter by Status">
        <div className="space-y-1">
          <SecondarySidebarNavItem
            icon={Activity}
            label="All Decisions"
            count={counts.total}
            isActive={statusFilter === null}
            onClick={() => onStatusFilterChange(null)}
          />
          <SecondarySidebarNavItem
            icon={CheckCircle2}
            label="Approved"
            count={counts.approved}
            isActive={statusFilter === "APPROVED"}
            onClick={() => onStatusFilterChange("APPROVED")}
          />
          <SecondarySidebarNavItem
            icon={XCircle}
            label="Vetoed"
            count={counts.vetoed}
            isActive={statusFilter === "VETOED"}
            onClick={() => onStatusFilterChange("VETOED")}
          />
          <SecondarySidebarNavItem
            icon={FileEdit}
            label="Modified"
            count={counts.modified}
            isActive={statusFilter === "MODIFIED"}
            onClick={() => onStatusFilterChange("MODIFIED")}
          />
        </div>
      </SecondarySidebarSection>

      <SecondarySidebarSection title="About ESL">
        <div className="space-y-3 text-sm text-[#171717]">
          <p>
            <strong className="text-green-600">Approved</strong> - Action passed all ethical checks.
          </p>
          <p>
            <strong className="text-red-600">Vetoed</strong> - Action blocked to protect your boundaries.
          </p>
          <p>
            <strong className="text-yellow-600">Modified</strong> - Action adjusted to better align with your values.
          </p>
        </div>
      </SecondarySidebarSection>
    </SecondarySidebar>
  )
}
