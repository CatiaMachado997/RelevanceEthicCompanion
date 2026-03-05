"use client"

import { useEffect, useState } from "react"
import {
  SecondarySidebar,
  SecondarySidebarSection,
  SecondarySidebarNavItem,
  SecondarySidebarPromo,
} from "@/components/secondary-sidebar"
import { Button } from "@/components/ui/button"
import {
  Activity,
  CheckCircle2,
  ShieldAlert,
  FileEdit,
  MessageSquare,
  ArrowRight,
} from "lucide-react"
import Link from "next/link"
import { transparencyApi } from "@/lib/api"

interface Stats {
  total_decisions: number
  approved_count: number
  vetoed_count: number
  modified_count: number
}

export function DashboardSidebar() {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    const loadStats = async () => {
      try {
        const report = await transparencyApi.report(7)
        setStats({
          total_decisions: report.total_decisions,
          approved_count: Math.round(report.total_decisions * report.approval_rate),
          vetoed_count: report.vetoed_count,
          modified_count: report.modified_count,
        })
      } catch (error) {
        console.error("Failed to load stats:", error)
      }
    }
    loadStats()
  }, [])

  return (
    <SecondarySidebar
      title="Overview"
      action={
        <Link href="/dashboard/chat">
          <Button size="sm" className="rounded-full !bg-[#D2691E] hover:!bg-[#B85A19] text-white">
            <MessageSquare className="h-4 w-4 mr-2" />
            New Chat
          </Button>
        </Link>
      }
    >
      <SecondarySidebarSection title="Quick Stats (7 days)">
        <div className="space-y-2">
          <SecondarySidebarNavItem
            icon={Activity}
            label="Total Decisions"
            count={stats?.total_decisions || 0}
          />
          <SecondarySidebarNavItem
            icon={CheckCircle2}
            label="Approved"
            count={stats?.approved_count || 0}
          />
          <SecondarySidebarNavItem
            icon={ShieldAlert}
            label="Protected"
            count={stats?.vetoed_count || 0}
          />
          <SecondarySidebarNavItem
            icon={FileEdit}
            label="Modified"
            count={stats?.modified_count || 0}
          />
        </div>
      </SecondarySidebarSection>

      <SecondarySidebarSection title="Quick Actions">
        <div className="space-y-2">
          <Link href="/dashboard/values" className="block">
            <div className="p-3 rounded-lg border border-border hover:border-foreground hover:bg-foreground/5 transition-all">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
                  <ShieldAlert className="h-4 w-4 text-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">Manage Values</p>
                  <p className="text-xs text-foreground">Set your boundaries</p>
                </div>
              </div>
            </div>
          </Link>
          <Link href="/dashboard/goals" className="block">
            <div className="p-3 rounded-lg border border-border hover:border-foreground hover:bg-foreground/5 transition-all">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
                  <CheckCircle2 className="h-4 w-4 text-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">Track Goals</p>
                  <p className="text-xs text-foreground">Monitor progress</p>
                </div>
              </div>
            </div>
          </Link>
        </div>
      </SecondarySidebarSection>
    </SecondarySidebar>
  )
}
